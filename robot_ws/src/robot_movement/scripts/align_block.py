#!/usr/bin/env python3
import math

import rospy
from robot_communication.msg import AprilTagDetectionArray, ContainerDetectionArray

from robot_movement.motion import MotionTask, fresh, velocity
from robot_movement.targets import block_position, container_position, parse_tag_id


class VisualAlignment(MotionTask):
    def __init__(self):
        kind = rospy.get_param("~kind", "block")
        if kind not in ("block", "container"):
            raise ValueError("kind deve ser block ou container")
        super().__init__("align_" + kind)
        self.is_block = kind == "block"
        self.vision_age = rospy.get_param("~vision_max_age_s", 0.25)
        self.goal_x = rospy.get_param("~goal_x", 0.0 if self.is_block else 0.5)
        self.goal_depth = rospy.get_param("~goal_depth", 0.30 if self.is_block else 0.5)
        self.tolerance_x = rospy.get_param("~lateral_tolerance", 0.01 if self.is_block else 0.025)
        self.tolerance_depth = rospy.get_param("~depth_tolerance", 0.025 if self.is_block else 0.03)
        self.lateral_sign = rospy.get_param("~lateral_sign", -1.0)
        self.depth_sign = rospy.get_param("~depth_sign", 1.0 if self.is_block else -1.0)
        self.max_speed = rospy.get_param("~max_speed_m_s", 0.05)
        self.min_speed = rospy.get_param("~min_speed_m_s", 0.02)
        self.stable_frames = rospy.get_param("~stable_frames", 3)
        topic = "/tag_detections" if self.is_block else "/container_detections"
        msg_type = AprilTagDetectionArray if self.is_block else ContainerDetectionArray
        self.vision_sub = rospy.Subscriber(topic, msg_type, self.on_detection, queue_size=1)
        self.start()

    def reset(self, payload):
        key = payload.strip().lower()
        if not key:
            raise ValueError("Alvo visual vazio")
        self.key = parse_tag_id(key) if self.is_block else key
        self.stamp = None
        self.position = None
        self.converged = 0

    def on_detection(self, msg):
        stamp = msg.header.stamp
        with self.lock:
            if (self.uid is None or self.stopping is not None or
                    not fresh(stamp, self.started, self.vision_age) or
                    (self.stamp is not None and stamp <= self.stamp)):
                return
            self.stamp = stamp
            self.position = block_position(msg, self.key) if self.is_block else container_position(msg, self.key)
            if self.position is None:
                self.converged = 0
                self.velocity_pub.publish(velocity())
                return
            x, depth = self.position
            if abs(x - self.goal_x) <= self.tolerance_x and abs(depth - self.goal_depth) <= self.tolerance_depth:
                self.converged += 1
            else:
                self.converged = 0

    def correction(self, error, tolerance, sign):
        if abs(error) <= tolerance:
            return 0.0
        speed = min(self.max_speed, max(self.min_speed, abs(error) * 0.5))
        return sign * math.copysign(speed, error)

    def update(self):
        if self.position is None or not fresh(self.stamp, self.started, self.vision_age):
            self.converged = 0
            self.velocity_pub.publish(velocity())
            return
        if self.converged >= self.stable_frames:
            self.finish("OK")
            return
        x, depth = self.position
        lateral = self.correction(x - self.goal_x, self.tolerance_x, self.lateral_sign)
        forward = self.correction(depth - self.goal_depth, self.tolerance_depth, self.depth_sign)
        self.velocity_pub.publish(velocity(x=0.0 if lateral else forward, y=lateral))


if __name__ == "__main__":
    rospy.init_node("align_block")
    VisualAlignment()
    rospy.spin()
