#!/usr/bin/env python3
import math
from collections import deque

import rospy
from robot_communication.msg import ultrasonic_comm
from sensor_msgs.msg import Imu
from tf.transformations import euler_from_quaternion

from robot_movement.motion import MotionTask, fresh, velocity


SENSORS = {
    "front": ("us_front_left", "us_front_right"),
    "right": ("us_right_2", "us_right_1"),
    "left": ("us_left_1", "us_left_2"),
}


class ApproachTable(MotionTask):
    def __init__(self):
        super().__init__("approach_table")
        self.readings = deque(maxlen=rospy.get_param("~range_samples", 5))
        self.range_age = rospy.get_param("~range_max_age_s", 0.30)
        self.max_range = rospy.get_param("~max_range_cm", 120.0)
        self.diff_max = rospy.get_param("~parallel_tolerance_cm", 0.5)
        self.distance_tolerance = rospy.get_param("~distance_tolerance_cm", 1.0)
        self.linear_speed = rospy.get_param("~linear_speed_m_s", 0.05)
        self.angular_speed = rospy.get_param("~angular_speed_rad_s", 0.10)
        self.pre_align_speed = rospy.get_param("~pre_align_speed_rad_s", 0.15)
        self.last_yaw = None
        self.imu_time = None
        self.range_sub = rospy.Subscriber("/ultrasonic_distances", ultrasonic_comm, self.on_range, queue_size=1)
        self.imu_sub = rospy.Subscriber("/imu/data_filtered", Imu, self.on_imu, queue_size=1)
        self.start()

    def reset(self, payload):
        first, second = (part.strip().lower() for part in payload.split(","))
        self.side, distance = (first, second) if first in SENSORS else (second, first)
        self.distance = float(distance)
        if self.side not in SENSORS or not 0 < self.distance <= self.max_range:
            raise ValueError("Esperado: distância em cm e front, left ou right")
        self.readings.clear()
        self.turning = self.side != "front"
        self.yaw = 0.0

    def on_imu(self, msg):
        q = msg.orientation
        _, _, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])
        if not math.isfinite(yaw):
            return
        with self.lock:
            now = rospy.Time.now()
            if (self.uid is not None and self.turning and self.imu_time is not None
                    and fresh(self.imu_time, self.started, 0.5)):
                self.yaw += math.atan2(math.sin(yaw - self.last_yaw), math.cos(yaw - self.last_yaw))
            self.last_yaw, self.imu_time = yaw, now

    def on_range(self, msg):
        with self.lock:
            if self.uid is None or self.stopping is not None or self.turning:
                return
            now = rospy.Time.now()
            first, second = (getattr(msg, name) for name in SENSORS[self.side])
            if (not all(0 < value <= self.max_range for value in (first, second))
                    or (self.readings and not fresh(self.readings[-1][0], self.started, self.range_age))):
                self.readings.clear()
            if all(0 < value <= self.max_range for value in (first, second)):
                self.readings.append((now, first, second))

    def update(self):
        if self.turning:
            direction = 1 if self.side == "right" else -1
            if direction * self.yaw >= math.radians(88):
                self.turning = False
            elif self.imu_time is not None and fresh(self.imu_time, self.started, 0.5):
                self.velocity_pub.publish(velocity(yaw=direction * self.pre_align_speed))
                return
            self.velocity_pub.publish(velocity())
            return

        if (not self.readings or len(self.readings) < self.readings.maxlen
                or not fresh(self.readings[-1][0], self.started, self.range_age)):
            self.velocity_pub.publish(velocity())
            return

        count = len(self.readings)
        first = sum(sample[1] for sample in self.readings) / count
        second = sum(sample[2] for sample in self.readings) / count
        difference = first - second
        if abs(difference) > self.diff_max:
            self.velocity_pub.publish(velocity(yaw=-math.copysign(self.angular_speed, difference)))
            return
        error = min(first, second) - self.distance
        if abs(error) <= self.distance_tolerance:
            self.finish("OK")
            return
        move = math.copysign(self.linear_speed, error)
        self.velocity_pub.publish(
            velocity(x=move) if self.side == "front"
            else velocity(y=move if self.side == "left" else -move)
        )


if __name__ == "__main__":
    rospy.init_node("approach_table")
    ApproachTable()
    rospy.spin()
