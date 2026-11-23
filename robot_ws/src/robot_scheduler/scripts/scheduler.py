#!/usr/bin/env python3
import math
import threading
import time

import rospy
from robot_communication.msg import SchedulerCommand, SchedulerResponse
from std_msgs.msg import UInt8MultiArray


class MissionError(RuntimeError):
    pass


def load_deliveries(config):
    deliveries = []
    for entry in config:
        tag, slot, color = entry["tag_id"], entry["deposit"], entry["color"]
        if (type(tag) is not int or not 0 <= tag <= 2**31 - 1 or type(slot) is not int
                or not isinstance(color, str) or not color.strip() or "," in color):
            raise ValueError("Entrega precisa de tag_id, deposit e color válidos")
        deliveries.append((tag, slot, color.strip().lower()))
    if sorted(slot for _, slot, _ in deliveries) != [1, 2, 3]:
        raise ValueError("A missão exige exatamente uma entrega por depósito 1, 2 e 3")
    if len({tag for tag, _, _ in deliveries}) != 3 or len({color for _, _, color in deliveries}) != 3:
        raise ValueError("A missão exige três IDs e três cores distintos")
    return deliveries


class Scheduler:
    def __init__(self):
        self.deliveries = load_deliveries(rospy.get_param("~deliveries"))
        self.deposits = {int(slot): pose for slot, pose in rospy.get_param("~deposits").items()}
        self.tables = rospy.get_param("~tables")
        self.timeouts = rospy.get_param("~timeouts")
        self.startup = rospy.get_param("~startup_delay_s", 30.0)
        self.grace = rospy.get_param("~feedback_grace_s", 5.0)
        self.occupied = set()
        self.lock = threading.Lock()
        self.pending = None
        self.result = None
        self.event = threading.Event()
        self.validate()
        self.commands = rospy.Publisher("/scheduler/commands", SchedulerCommand, queue_size=10)
        self.cancel = rospy.Publisher("/scheduler/cancel", SchedulerCommand, queue_size=10)
        self.deposit_state = rospy.Publisher("/scheduler/deposits", UInt8MultiArray, queue_size=1, latch=True)
        self.subscriber = rospy.Subscriber("/scheduler/feedback", SchedulerResponse, self.on_feedback, queue_size=30)

    def validate(self):
        if not rospy.get_param("~calibrated", False) and not rospy.get_param("~allow_uncalibrated", False):
            raise ValueError("Confirme os parâmetros de campo em mission.yaml antes de iniciar no robô")
        if set(self.deposits) != {1, 2, 3} or set(self.deposits.values()) != {
            "deposit_left", "deposit_middle", "deposit_right",
        }:
            raise ValueError("Configure as três posições de depósito")
        for table in (self.tables["blocks"], self.tables["containers"]):
            if (table["start_edge"] not in ("esquerda", "direita") or not table["waypoint"]
                    or not math.isfinite(table["distance_cm"]) or table["distance_cm"] <= 0):
                raise ValueError("Configure waypoint, distância e borda inicial para cada mesa")
        for target in ("navigation", "approach_table", "border_detect", "search_item",
                       "align_block", "align_container", "manipulation"):
            if not math.isfinite(self.timeouts[target]) or self.timeouts[target] <= 0:
                raise ValueError("Timeout inválido: " + target)

    def on_feedback(self, response):
        with self.lock:
            if self.pending == (response.uid, response.target) and self.result is None:
                self.result = response.status.upper()
                self.event.set()

    def step(self, target, payload):
        timeout = self.timeouts[target]
        command = SchedulerCommand(uid=time.time_ns() // 1000, target=target, payload=str(payload),
                                   need_ack=True, timeout=timeout)
        with self.lock:
            self.pending = command.uid, target
            self.result = None
            self.event.clear()
        rospy.loginfo("[scheduler] %s %s (UID %s)", target, payload, command.uid)
        deadline = time.monotonic() + timeout + self.grace
        try:
            for _ in range(8):
                if rospy.is_shutdown() or self.event.is_set():
                    break
                self.commands.publish(command)
                self.event.wait(0.10)
            while not self.event.is_set() and not rospy.is_shutdown():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.event.wait(min(0.10, remaining))
            with self.lock:
                status = self.result
            if status != "OK":
                if not status or rospy.is_shutdown():
                    self.cancel.publish(command)
                    status = status or ("CANCELLED" if rospy.is_shutdown() else "TIMEOUT")
                raise MissionError(f"{target} {payload}: {status} (UID {command.uid})")
        finally:
            with self.lock:
                self.pending = None

    def publish_deposits(self):
        self.deposit_state.publish(UInt8MultiArray(data=[int(slot in self.occupied) for slot in (1, 2, 3)]))

    def arm(self, *commands):
        for payload in commands:
            self.step("manipulation", payload)

    def find(self, table, mode, key):
        # Voltar para a borda inicial antes de cada ciclo também cobre os itens
        # que ficaram atrás do ponto de parada do ciclo anterior.
        self.step("approach_table", f"{table['distance_cm']},front")
        start = table["start_edge"]
        sweep = "direita" if start == "esquerda" else "esquerda"
        self.step("border_detect", start)
        self.step("search_item", f"{mode},{key},{sweep}")
        self.step("align_" + mode, key)

    def collect(self, table, tag, slot):
        self.find(table, "block", tag)
        self.arm("rotatory_base,front", "gripper,open", "arm,table_pick", "gripper,close",
                 "arm,home", f"rotatory_base,{self.deposits[slot]}", "arm,deposit_put", "gripper,open")
        self.occupied.add(slot)
        self.publish_deposits()
        self.arm("arm,home", "rotatory_base,front")

    def deliver(self, table, slot, color):
        if slot not in self.occupied:
            raise MissionError(f"Depósito {slot} vazio")
        self.find(table, "container", color)
        self.arm(f"rotatory_base,{self.deposits[slot]}", "arm,deposit_pick", "gripper,close",
                 "arm,home", "rotatory_base,front", "arm,container_drop", "gripper,open")
        self.occupied.remove(slot)
        self.publish_deposits()
        self.arm("arm,home")

    def run(self):
        rospy.sleep(self.startup)
        self.publish_deposits()
        self.arm("arm,home", "rotatory_base,front", "wrist,center")
        blocks, containers = self.tables["blocks"], self.tables["containers"]
        self.step("navigation", blocks["waypoint"])
        for tag, slot, _ in self.deliveries:
            self.collect(blocks, tag, slot)
        self.step("navigation", containers["waypoint"])
        for _, slot, color in self.deliveries:
            self.deliver(containers, slot, color)
        rospy.loginfo("[scheduler] Três blocos entregues")


if __name__ == "__main__":
    rospy.init_node("scheduler")
    try:
        Scheduler().run()
    except (KeyError, TypeError, ValueError, MissionError) as exc:
        rospy.logerr("[scheduler] Missão abortada: %s", exc)
        raise SystemExit(1)
