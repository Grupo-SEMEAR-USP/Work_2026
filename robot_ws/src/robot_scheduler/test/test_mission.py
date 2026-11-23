"""Contract tests with controlled messages. Run with python3 test/test_mission.py."""
import importlib.util
import math
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SRC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC / "robot_movement" / "src"))
Msg = types.SimpleNamespace


class Clock(float):
    now_s = 100

    @classmethod
    def now(cls):
        return cls(cls.now_s)

    def __add__(self, value):
        return Clock(float(self) + value)

    def __sub__(self, value):
        return Clock(float(self) - value)

    def to_sec(self):
        return float(self)


def module(name, **fields):
    instance = types.ModuleType(name)
    instance.__dict__.update(fields)
    sys.modules[name] = instance
    return instance


def twist():
    return Msg(linear=Msg(x=0.0, y=0.0), angular=Msg(z=0.0))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, SRC / path)
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


rospy = module("rospy", Time=Clock, Duration=Clock, is_shutdown=lambda: False,
               get_param=lambda _, default=None: default, loginfo=Mock(), logwarn=Mock(),
               logerr=Mock(), Rate=lambda _: Msg(sleep=lambda: None))
module("actionlib")
module("actionlib_msgs.msg", GoalStatus=Msg(SUCCEEDED=3, PREEMPTED=2))
module("geometry_msgs.msg", Twist=twist)
module("std_msgs.msg", UInt8MultiArray=Msg)
names = ("SchedulerCommand", "SchedulerResponse", "AprilTagDetectionArray",
         "ContainerDetectionArray", "MoveSegmentAction", "MoveSegmentGoal",
         "MoveSegmentResult", "ultrasonic_comm", "encoder_comm")
module("robot_communication.msg", **dict.fromkeys(names, Msg))
scheduler = load("robot_scheduler/scripts/scheduler.py", "_scheduler")
search = load("robot_movement/scripts/search_item.py", "_search")
align = load("robot_movement/scripts/align_block.py", "_align")
from robot_movement.table_edge import TableEdge


def tags(timestamp, identifier):
    point = Msg(x=0.2, y=0.0, z=0.3)
    pose = Msg(pose=Msg(pose=Msg(position=point)))
    return Msg(header=Msg(stamp=Clock(timestamp)), detections=[Msg(id=[identifier], pose=pose)])


def colors(timestamp, color):
    detection = Msg(center_x=40, center_y=40, color=color, area_px=500)
    return Msg(header=Msg(stamp=Clock(timestamp)), detections=[detection],
               image_width=640, image_height=480)


class TestMission(unittest.TestCase):
    def find(self, mode="block", target=4):
        node = search.SearchItem.__new__(search.SearchItem)
        node.lock = threading.RLock()
        node.seen = set()
        node.uid = 1
        node.mode, node.target, node.direction = mode, target, "direita"
        node.movement_active, node.outcome = True, None
        node.since, node.deadline = Clock(99.9), Clock(102)
        node.vision_age, node.stop_wait = 0.3, 3.0
        node.edge = TableEdge()
        node.on_range(Msg(us_front_left=10.0, us_front_right=10.0))
        return node

    def test_block_filters_mode_id_and_age(self):
        node = self.find()
        node.on_colors(colors(100, "red"))
        node.on_tags(tags(99, 4))
        node.on_tags(tags(100, 5))
        self.assertTrue(node.movement_active)
        node.on_tags(tags(100, 4))
        self.assertEqual(node.outcome, "OK")
        self.assertFalse(node.movement_active)

    def test_next_command_resets_target_and_deduplicates(self):
        node = self.find()
        node.on_tags(tags(100, 4))
        node.seen.add(1)
        node.uid = None
        command = Msg(target="search_item", uid=2, timeout=5, payload="container,red,direita")
        with patch.object(search.threading, "Thread") as thread:
            node.on_command(command)
            node.on_command(command)
            thread.assert_called_once()
        self.assertIsNone(node.outcome)
        node.on_tags(tags(100, 4))
        node.on_colors(colors(99, "red"))
        node.on_colors(colors(100, "blue"))
        self.assertTrue(node.movement_active)
        node.on_colors(colors(100, "red"))
        self.assertEqual(node.outcome, "OK")

    def test_detection_cancels_segment_before_handoff(self):
        node = self.find()
        calls = []

        def wait(_):
            if not calls:
                node.on_tags(tags(100, 4))
                return False
            return True

        node.motion = Msg(send_goal=Mock(), wait_for_result=wait,
                          cancel_goal=lambda: calls.append("cancel"),
                          get_state=lambda: 2, get_result=lambda: Msg(stopped=True))
        self.assertEqual(node.segment("direita", 0.7, 0.05), (True, True))
        self.assertEqual(node.outcome, "OK")
        self.assertEqual(calls, ["cancel"])
        self.assertEqual(node.segment("tras", 0.7, 0.05), (False, True))
        node.motion.send_goal.assert_called_once()

    def test_directional_edge_timeout_and_alignment_loss(self):
        node = self.find()
        for _ in range(2):
            node.on_range(Msg(us_front_left=math.nan, us_front_right=10))
        self.assertTrue(node.movement_active)
        for _ in range(2):
            node.on_range(Msg(us_front_left=10, us_front_right=math.nan))
        self.assertEqual(node.outcome, "LIMIT")
        node = self.find()
        node.deadline = Clock(100)
        node.on_tags(tags(100, 4))
        self.assertEqual(node.outcome, "TIMEOUT")
        alignment = align.VisualAlignment.__new__(align.VisualAlignment)
        alignment.uid, alignment.stopping = 1, None
        alignment.lock = threading.RLock()
        alignment.is_block = False
        alignment.vision_age, alignment.started, alignment.stamp = 0.3, Clock(99.9), None
        alignment.key, alignment.converged = "red", 1
        alignment.velocity_pub = Mock()
        alignment.on_detection(colors(100, "blue"))
        self.assertIsNone(alignment.position)
        self.assertEqual(alignment.velocity_pub.publish.call_args.args[0].linear.y, 0)

    def test_full_mission_and_immediate_uid_feedback(self):
        machine = scheduler.Scheduler.__new__(scheduler.Scheduler)
        machine.startup, machine.grace = 0, 0.1
        machine.occupied = set()
        machine.deposits = {1: "deposit_left", 2: "deposit_middle", 3: "deposit_right"}
        machine.deliveries = [(4, 1, "red"), (5, 2, "blue"), (6, 3, "green")]
        table = {"distance_cm": 10, "start_edge": "esquerda"}
        machine.tables = {"blocks": dict(table, waypoint="WS1"),
                          "containers": dict(table, waypoint="WS2")}
        machine.timeouts = dict.fromkeys(("navigation", "approach_table", "border_detect",
                                         "search_item", "align_block", "align_container",
                                         "manipulation"), 2)
        machine.lock = threading.Lock()
        machine.event = threading.Event()
        machine.pending = None
        machine.result = None
        states, commands = [], []
        machine.cancel = Mock()
        machine.deposit_state = Msg(publish=lambda state: states.append(state.data))

        def feedback(command):
            commands.append((command.target, command.payload))
            machine.on_feedback(Msg(uid=command.uid, target="unrelated", status="FAIL"))
            machine.on_feedback(Msg(uid=command.uid, target=command.target, status="OK"))

        machine.commands = Msg(publish=feedback)
        with patch.object(rospy, "sleep", create=True):
            machine.run()
        self.assertEqual(states, [[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 1, 1],
                                  [0, 1, 1], [0, 0, 1], [0, 0, 0]])
        second = commands[commands.index(("navigation", "WS2")) + 1:]
        self.assertNotIn("align_block", [target for target, _ in second])
        self.assertEqual([payload for target, payload in second if target == "search_item"],
                         ["container,red,direita", "container,blue,direita", "container,green,direita"])
        self.assertEqual([payload for target, payload in second if payload.startswith("rotatory_base,deposit")],
                         ["rotatory_base,deposit_left", "rotatory_base,deposit_middle", "rotatory_base,deposit_right"])
        self.assertEqual(commands.count(("border_detect", "esquerda")), 6)
        machine.commands = Msg(publish=lambda cmd: machine.on_feedback(
            Msg(uid=cmd.uid, target=cmd.target, status="FAIL")))
        with self.assertRaises(scheduler.MissionError):
            machine.step("navigation", "WS1")


if __name__ == "__main__":
    unittest.main()
