#!/usr/bin/env python3
import math
import threading

import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import (
    ManipulatorCommand, SchedulerCommand, SchedulerResponse, manipulation_comm,
)
from robot_movement.motion import BaseStop


MASKS = {
    "arm": (ManipulatorCommand.ELEVATOR, "elevator_cm"),
    "rotatory_base": (ManipulatorCommand.BASE, "base_angle_deg"),
    "wrist": (ManipulatorCommand.WRIST, "wrist_angle_deg"),
    "gripper": (ManipulatorCommand.GRIPPER, "gripper_angle_deg"),
}


class ManipulationInterface:
    def __init__(self):
        self.values = {component: rospy.get_param("~" + component) for component in MASKS}
        self.max_travel_cm = rospy.get_param("~max_elevator_travel_cm")
        self.servo_settle = rospy.get_param("~servo_settle_s", 0.75)
        self.lock = threading.RLock()
        self.current = None
        self.seen = set()
        self.homed = False
        self.latest = None
        self.stop = BaseStop()
        self.vel = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.motors = rospy.Publisher("/manipulator_command", ManipulatorCommand, queue_size=1)
        self.feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)
        self.subscriptions = [
            rospy.Subscriber("/manipulator_state", manipulation_comm, self.on_state, queue_size=1),
            rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.on_command),
            rospy.Subscriber("/scheduler/cancel", SchedulerCommand, self.on_cancel),
        ]
        self.timer = rospy.Timer(rospy.Duration(0.04), self.tick)

    def on_command(self, msg):
        if msg.target != "manipulation":
            return
        with self.lock:
            if msg.uid in self.seen:
                return
            self.seen.add(msg.uid)
            try:
                component, action = (part.strip().lower() for part in msg.payload.split(","))
                mask, field = MASKS[component]
                value = float(self.values[component][action])
                valid = math.isfinite(value) and math.isfinite(msg.timeout) and msg.timeout > 0
                if component == "arm":
                    valid &= (0 < value <= self.max_travel_cm if action == "home"
                              else -self.max_travel_cm <= value < 0 and self.homed)
                if component == "rotatory_base":
                    valid &= self.homed and 0 <= value <= 360
                if component in ("wrist", "gripper"):
                    valid &= 0 <= value <= 180
                if not valid or self.current is not None:
                    raise ValueError("comando inválido, ocupado ou elevador fora da referência")
            except (KeyError, ValueError) as exc:
                rospy.logwarn("[manipulation] %s", exc)
                self.respond(msg.uid, "FAIL")
                return
            start = rospy.Time.now()
            self.current = ManipulatorCommand(uid=msg.uid, motor_mask=mask, **{field: value})
            self.action = action
            self.started = start
            self.deadline = start + rospy.Duration(msg.timeout)
            self.sent = False
            self.completed = None

    def on_cancel(self, msg):
        if msg.target == "manipulation":
            with self.lock:
                self.seen.add(msg.uid)
                if self.current and self.current.uid == msg.uid:
                    self.finish("CANCELLED")

    def on_state(self, msg):
        with self.lock:
            now = rospy.Time.now()
            self.latest = now, msg
            if self.current is None or not self.sent or msg.command_uid != self.current.uid:
                return
            if msg.manip_feedback == 2:
                self.finish("FAIL")
            elif msg.manip_feedback == 1:
                if self.action == "home" and not msg.upper_limit_active:
                    self.finish("FAIL")
                elif self.completed is None:
                    self.completed = now

    def tick(self, _):
        with self.lock:
            if self.current is None:
                return
            self.vel.publish(Twist())
            now = rospy.Time.now()
            if now >= self.deadline:
                self.finish("TIMEOUT")
                return
            if not self.stop.confirmed(self.started):
                if self.sent or (now - self.started).to_sec() >= self.stop.timeout:
                    self.finish("FAIL")
                return
            if not self.sent:
                if self.motors.get_num_connections() == 0 or self.latest is None:
                    return
                stamp, state = self.latest
                if (now - stamp).to_sec() > 0.5:
                    return
                if (self.current.motor_mask == ManipulatorCommand.BASE
                        and not (state.upper_limit_active and state.encoder_valid)):
                    self.finish("FAIL")
                    return
                self.sent = True
                if self.current.motor_mask == ManipulatorCommand.ELEVATOR:
                    self.homed = False
                self.motors.publish(self.current)
            elif self.completed is not None:
                servo = self.current.motor_mask in (ManipulatorCommand.WRIST, ManipulatorCommand.GRIPPER)
                if not servo or (now - self.completed).to_sec() >= self.servo_settle:
                    self.finish("OK")

    def finish(self, status):
        if self.action == "home":
            self.homed = status == "OK"
        uid = self.current.uid
        self.current = None
        self.sent = False
        self.respond(uid, status)

    def respond(self, uid, status):
        self.feedback.publish(SchedulerResponse(uid=uid, target="manipulation", status=status))


if __name__ == "__main__":
    rospy.init_node("manipulation")
    ManipulationInterface()
    rospy.spin()
