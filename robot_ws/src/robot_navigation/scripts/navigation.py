#!/usr/bin/env python3
import math
import os
import threading

import actionlib
import rospkg
import rospy
import yaml
from actionlib_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from robot_communication.msg import SchedulerCommand, SchedulerResponse
from robot_movement.motion import BaseStop


class NavigationNode:
    def __init__(self):
        directory = rospkg.RosPack().get_path("robot_scheduler")
        path = rospy.get_param("~waypoint_file", os.path.join(directory, "config", "points.yaml"))
        with open(path, encoding="utf-8") as stream:
            self.waypoints = yaml.safe_load(stream)
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        self.feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)
        self.initial_pose = rospy.Publisher("/initialpose", PoseWithCovarianceStamped, queue_size=1, latch=True)
        self.velocity = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.stop = BaseStop()
        self.lock = threading.Lock()
        self.seen = set()
        self.active = None
        self.set_initial_pose(rospy.get_param("~initial_waypoint", "Start"))
        self.command_sub = rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.on_command)
        self.cancel_sub = rospy.Subscriber("/scheduler/cancel", SchedulerCommand, self.on_cancel)

    def set_pose(self, pose, name):
        point = self.waypoints[name]
        pose.position.x, pose.position.y, pose.position.z = (point[a] for a in ("x", "y", "z"))
        (pose.orientation.x, pose.orientation.y, pose.orientation.z,
         pose.orientation.w) = (point[a] for a in ("qx", "qy", "qz", "qw"))

    def set_initial_pose(self, waypoint):
        if not waypoint:
            return
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = "map"
        self.set_pose(msg.pose.pose, waypoint)
        msg.pose.covariance[0] = msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.06
        self.initial_pose.publish(msg)

    def on_command(self, msg):
        if msg.target != "navigation":
            return
        with self.lock:
            if msg.uid in self.seen:
                return
            self.seen.add(msg.uid)
            if (self.active is not None or msg.payload not in self.waypoints
                    or not math.isfinite(msg.timeout) or msg.timeout <= 0):
                self.respond(msg.uid, "FAIL")
                return
            cancel = threading.Event()
            self.active = msg.uid, cancel
            deadline = rospy.Time.now() + rospy.Duration(msg.timeout)
        threading.Thread(target=self.navigate, args=(msg, cancel, deadline), daemon=True).start()

    def on_cancel(self, msg):
        if msg.target == "navigation":
            with self.lock:
                self.seen.add(msg.uid)
                if self.active and self.active[0] == msg.uid:
                    self.active[1].set()

    def run_goal(self, msg, cancel, deadline):
        def unfinished_status():
            if cancel.is_set() or rospy.is_shutdown():
                return "CANCELLED"
            return "TIMEOUT" if rospy.Time.now() >= deadline else None

        while not self.client.wait_for_server(rospy.Duration(0.10)):
            status = unfinished_status()
            if status:
                return status
        status = unfinished_status()
        if status:
            return status
        goal = MoveBaseGoal()
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.header.frame_id = "map"
        self.set_pose(goal.target_pose.pose, msg.payload)
        self.client.send_goal(goal)
        while True:
            status = unfinished_status()
            if status:
                self.client.cancel_goal()
                if not self.client.wait_for_result(rospy.Duration(2.0)):
                    rospy.logerr("[navigation] Cancelamento do move_base sem confirmação")
                    return "FAIL"
                return status
            if self.client.wait_for_result(rospy.Duration(0.10)):
                return "OK" if self.client.get_state() == GoalStatus.SUCCEEDED else "FAIL"

    def navigate(self, msg, cancel, deadline):
        status = "FAIL"
        try:
            status = self.run_goal(msg, cancel, deadline)
        except Exception as exc:
            self.client.cancel_goal()
            rospy.logerr("[navigation] %s", exc)
        finally:
            if not self.stop.stop(self.velocity):
                status = "FAIL"
            with self.lock:
                self.active = None
            self.respond(msg.uid, status)

    def respond(self, uid, status):
        self.feedback.publish(SchedulerResponse(uid=uid, target="navigation", status=status))


if __name__ == "__main__":
    rospy.init_node("navigation_node")
    NavigationNode()
    rospy.spin()
