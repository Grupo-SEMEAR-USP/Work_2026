#!/usr/bin/env python3
import math
import threading

import actionlib
import rospy
from actionlib_msgs.msg import GoalStatus
from robot_communication.msg import (
    AprilTagDetectionArray, ContainerDetectionArray, MoveSegmentAction, MoveSegmentGoal,
    SchedulerCommand, SchedulerResponse, ultrasonic_comm,
)
from robot_movement.motion import fresh
from robot_movement.table_edge import DIRECTION_SIGN, TableEdge
from robot_movement.targets import block_position, container_position, parse_tag_id


class SearchItem:
    def __init__(self):
        self.motion = actionlib.SimpleActionClient("/move_segment", MoveSegmentAction)
        self.feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)
        self.edge = TableEdge()
        self.lock = threading.RLock()
        self.seen = set()
        self.uid = None
        self.movement_active = False
        self.outcome = None
        self.since = None
        self.lateral_s = rospy.get_param("~lateral_segment_s", 0.7)
        self.depth_s = rospy.get_param("~depth_segment_s", 0.7)
        self.lateral_speed = rospy.get_param("~lateral_speed_m_s", 0.05)
        self.depth_speed = rospy.get_param("~depth_speed_m_s", 0.05)
        self.distance_limit = rospy.get_param("~max_lateral_m", 1.20)
        self.vision_age = rospy.get_param("~vision_max_age_s", 0.30)
        self.stop_wait = rospy.get_param("~segment_result_grace_s", 3.0)
        params = (self.lateral_s, self.depth_s, self.lateral_speed, self.depth_speed,
                  self.distance_limit, self.vision_age, self.stop_wait)
        if any(not math.isfinite(value) or value <= 0 for value in params):
            raise ValueError("Parâmetros da busca precisam ser positivos")
        self.subscriptions = [
            rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.on_command),
            rospy.Subscriber("/scheduler/cancel", SchedulerCommand, self.on_cancel),
            rospy.Subscriber("/tag_detections", AprilTagDetectionArray, self.on_tags, queue_size=1),
            rospy.Subscriber("/container_detections", ContainerDetectionArray, self.on_colors, queue_size=1),
            rospy.Subscriber("/ultrasonic_distances", ultrasonic_comm, self.on_range, queue_size=1),
        ]

    def on_command(self, msg):
        if msg.target != "search_item":
            return
        with self.lock:
            if msg.uid in self.seen:
                return
            self.seen.add(msg.uid)
            try:
                mode, key, direction = (part.strip().lower() for part in msg.payload.split(","))
                if (self.uid is not None or mode not in ("block", "container") or not key
                        or direction not in DIRECTION_SIGN or not math.isfinite(msg.timeout)
                        or msg.timeout <= 0):
                    raise ValueError("Busca indisponível ou comando inválido")
                target = parse_tag_id(key) if mode == "block" else key
            except ValueError as exc:
                rospy.logwarn("[search_item] %s", exc)
                self.respond(msg.uid, "FAIL")
                return
            self.uid, self.mode, self.target, self.direction = msg.uid, mode, target, direction
            self.since = rospy.Time.now()
            self.deadline = self.since + rospy.Duration(msg.timeout)
            self.edge.reset()
            self.outcome = None
            self.movement_active = True
        threading.Thread(target=self.run, args=(msg.uid,), daemon=True).start()

    def finish(self, outcome):
        self.outcome = outcome
        self.movement_active = False

    def on_cancel(self, msg):
        if msg.target == "search_item":
            with self.lock:
                self.seen.add(msg.uid)
                if msg.uid == self.uid:
                    self.finish("CANCELLED")

    def on_tags(self, msg):
        with self.lock:
            self.check_deadline()
            if (self.movement_active and self.mode == "block"
                    and fresh(msg.header.stamp, self.since, self.vision_age)
                    and block_position(msg, self.target) is not None):
                self.finish("OK")

    def on_colors(self, msg):
        with self.lock:
            self.check_deadline()
            if (self.movement_active and self.mode == "container"
                    and fresh(msg.header.stamp, self.since, self.vision_age)
                    and container_position(msg, self.target) is not None):
                self.finish("OK")

    def on_range(self, msg):
        with self.lock:
            self.check_deadline()
            if self.movement_active:
                self.edge.on_range(msg, self.direction)
                if self.edge.state(self.since)[1]:
                    self.finish("LIMIT")

    def check_deadline(self):
        if self.movement_active and rospy.Time.now() >= self.deadline:
            self.finish("TIMEOUT")

    def segment(self, direction, duration, speed, stop_only=False):
        with self.lock:
            self.check_deadline()
            if not stop_only and not self.movement_active:
                return False, True
            # A detecção e o envio do próximo segmento compartilham este lock.
            self.motion.send_goal(MoveSegmentGoal(direction=direction, duration=duration, speed=speed))
        cancelled = False
        until = rospy.Time.now() + rospy.Duration(duration + self.stop_wait)
        while not rospy.is_shutdown():
            if self.motion.wait_for_result(rospy.Duration(0.025)):
                result = self.motion.get_result()
                stopped = bool(result and result.stopped)
                state = self.motion.get_state()
                expected = state == GoalStatus.SUCCEEDED or (cancelled and state == GoalStatus.PREEMPTED)
                return True, stopped and expected
            with self.lock:
                self.check_deadline()
                if not stop_only and not self.edge.state(self.since)[0] and self.movement_active:
                    self.finish("FAIL")
                cancel = not stop_only and not self.movement_active
            if cancel and not cancelled:
                self.motion.cancel_goal()
                cancelled = True
                until = rospy.Time.now() + rospy.Duration(self.stop_wait)
            if rospy.Time.now() >= until:
                self.motion.cancel_goal()
                return True, False
        self.motion.cancel_goal()
        return True, False

    def scan(self):
        # Even a detection before the first segment must get a confirmed stop.
        _, stopped = self.segment("parar", 0.04, 0.0, stop_only=True)
        if not stopped:
            return "FAIL"
        # Wait stationary for a fresh reading before starting any lateral travel.
        rate = rospy.Rate(25)
        while not rospy.is_shutdown():
            with self.lock:
                self.check_deadline()
                if not self.movement_active:
                    return self.outcome
                if self.edge.state(self.since)[0]:
                    break
            rate.sleep()
        traveled = 0.0
        pattern = ((self.direction, self.lateral_s, self.lateral_speed),
                   ("tras", self.depth_s, self.depth_speed),
                   (self.direction, self.lateral_s, self.lateral_speed),
                   ("frente", self.depth_s, self.depth_speed))
        while not rospy.is_shutdown():
            for direction, duration, speed in pattern:
                with self.lock:
                    if not self.movement_active:
                        return self.outcome
                    if traveled >= self.distance_limit - 1e-6:
                        return "LIMIT"
                    lateral = direction == self.direction
                    if lateral:
                        duration = min(duration, (self.distance_limit - traveled) / speed)
                        if duration <= 1e-6:
                            return "LIMIT"
                    if not self.edge.state(self.since)[0]:
                        return "FAIL"
                sent, stopped = self.segment(direction, duration, speed)
                if not stopped:
                    return "FAIL"
                if sent and lateral:
                    traveled += duration * speed
        return "CANCELLED"

    def run(self, uid):
        status = "FAIL"
        try:
            if self.motion.wait_for_server(rospy.Duration(2.0)):
                status = self.scan()
        except Exception as exc:
            rospy.logerr("[search_item] Busca interrompida: %s", exc)
            self.motion.cancel_goal()
            self.motion.wait_for_result(rospy.Duration(self.stop_wait))
        finally:
            with self.lock:
                if self.outcome == "CANCELLED" and status != "FAIL":
                    status = "CANCELLED"
                self.movement_active = False
                self.uid = None
            self.respond(uid, status)

    def respond(self, uid, status):
        self.feedback.publish(SchedulerResponse(uid=uid, target="search_item", status=status))


if __name__ == "__main__":
    rospy.init_node("search_item")
    SearchItem()
    rospy.spin()
