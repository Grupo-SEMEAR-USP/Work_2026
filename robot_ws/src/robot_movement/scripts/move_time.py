#!/usr/bin/env python3
import math
import threading

import actionlib
import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import (
    MoveSegmentAction, MoveSegmentResult, SchedulerCommand, SchedulerResponse,
)
from robot_movement.motion import BaseStop, velocity


DIRECTIONS = {
    "frente": (1, 0, 0), "tras": (-1, 0, 0),
    "esquerda": (0, 1, 0), "direita": (0, -1, 0),
    "horario": (0, 0, -1), "antihorario": (0, 0, 1),
    "parar": (0, 0, 0),
}


class MoveTime:
    def __init__(self):
        self.default_speeds = (
            rospy.get_param("~linear_x", 0.2), rospy.get_param("~linear_y", 0.2),
            rospy.get_param("~angular_z", 0.6),
        )
        self.output = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)
        self.base_stop = BaseStop()
        self.owner = threading.Lock()
        self.command_lock = threading.Lock()
        self.seen = set()
        self.active = None
        self.server = actionlib.SimpleActionServer(
            "/move_segment", MoveSegmentAction, execute_cb=self.on_goal, auto_start=False,
        )
        self.command_sub = rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.on_command)
        self.cancel_sub = rospy.Subscriber("/scheduler/cancel", SchedulerCommand, self.on_cancel)
        self.server.start()

    def run_segment(self, direction, duration, speed, is_cancelled):
        if (direction not in DIRECTIONS or not math.isfinite(duration) or duration <= 0
                or not math.isfinite(speed) or speed < 0):
            return "FAIL", False
        axes = DIRECTIONS[direction]
        if any(axis and speed > maximum for axis, maximum in zip(axes, self.default_speeds)):
            return "FAIL", False
        if not self.owner.acquire(blocking=False):
            return "FAIL", False
        try:
            command = velocity(*(axis * (speed or default)
                                 for axis, default in zip(axes, self.default_speeds)))
            until = rospy.Time.now() + rospy.Duration(duration)
            rate = rospy.Rate(50)
            while not rospy.is_shutdown() and not is_cancelled() and rospy.Time.now() < until:
                self.output.publish(command)
                rate.sleep()
            stopped = self.base_stop.stop(self.output)
            if not stopped:
                return "FAIL", False
            return ("CANCELLED" if is_cancelled() else "OK"), True
        finally:
            self.owner.release()

    def on_goal(self, goal):
        status, stopped = self.run_segment(
            goal.direction, goal.duration, goal.speed, self.server.is_preempt_requested,
        )
        result = MoveSegmentResult(stopped=stopped)
        if status == "OK":
            self.server.set_succeeded(result)
        elif status == "CANCELLED":
            self.server.set_preempted(result)
        else:
            self.server.set_aborted(result)

    def on_command(self, command):
        if command.target != "move":
            return
        with self.command_lock:
            if command.uid in self.seen:
                return
            self.seen.add(command.uid)
            if self.active is not None:
                self.respond(command, "FAIL")
                return
            cancelled = threading.Event()
            self.active = command.uid, cancelled
        threading.Thread(target=self.execute_command, args=(command, cancelled), daemon=True).start()

    def on_cancel(self, command):
        if command.target == "move":
            with self.command_lock:
                self.seen.add(command.uid)
                if self.active and self.active[0] == command.uid:
                    self.active[1].set()

    def execute_command(self, command, cancelled):
        status, _ = self.run_segment(command.payload.strip().lower(), command.timeout, 0.0,
                                     cancelled.is_set)
        with self.command_lock:
            self.active = None
        self.respond(command, status)

    def respond(self, command, status):
        if command.need_ack:
            self.feedback.publish(SchedulerResponse(uid=command.uid, target="move", status=status))


if __name__ == "__main__":
    rospy.init_node("move_time")
    MoveTime()
    rospy.spin()
