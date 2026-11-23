#!/usr/bin/env python3
import math

import rospy
from robot_communication.msg import ultrasonic_comm
from robot_movement.motion import MotionTask, velocity
from robot_movement.table_edge import DIRECTION_SIGN, TableEdge


class BorderDetect(MotionTask):
    def __init__(self):
        super().__init__("border_detect")
        self.edge = TableEdge()
        self.speed = rospy.get_param("~lateral_speed_m_s", 0.05)
        self.travel_limit = rospy.get_param("~max_lateral_m", 1.20)
        if not all(math.isfinite(value) and value > 0 for value in (self.speed, self.travel_limit)):
            raise ValueError("Velocidade e limite da busca de borda precisam ser positivos")
        self.range_sub = rospy.Subscriber("/ultrasonic_distances", ultrasonic_comm, self.on_range, queue_size=1)
        self.start()

    def reset(self, payload):
        self.direction = payload.strip().lower()
        if self.direction not in DIRECTION_SIGN:
            raise ValueError("Borda espera esquerda ou direita")
        self.edge.reset()
        self.first_movement = None

    def on_range(self, msg):
        with self.lock:
            if self.uid is not None and self.stopping is None:
                self.edge.on_range(msg, self.direction)

    def update(self):
        near, edge = self.edge.state(self.started)
        if edge:
            self.finish("OK")
        elif self.first_movement is not None and (
                rospy.Time.now() - self.first_movement).to_sec() * self.speed >= self.travel_limit:
            self.finish("LIMIT")
        elif near:
            if self.first_movement is None:
                self.first_movement = rospy.Time.now()
            self.velocity_pub.publish(velocity(y=DIRECTION_SIGN[self.direction] * self.speed))
        else:
            self.velocity_pub.publish(velocity())


if __name__ == "__main__":
    rospy.init_node("border_detect")
    BorderDetect()
    rospy.spin()
