import math
import threading

import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import SchedulerCommand, SchedulerResponse, encoder_comm


def fresh(stamp, since, maximum_age):
    age = (rospy.Time.now() - stamp).to_sec()
    return stamp >= since and 0.0 <= age <= maximum_age and stamp != rospy.Time(0)


def velocity(x=0.0, y=0.0, yaw=0.0):
    command = Twist()
    command.linear.x = x
    command.linear.y = y
    command.angular.z = yaw
    return command


class BaseStop:
    """Require fresh, sustained near-zero wheel speeds after commanding zero."""

    def __init__(self):
        self.lock = threading.Lock()
        self.last_sample = None
        self.still_since = None
        self.limit = rospy.get_param("~stop_wheel_rad_s", 0.20)
        self.settle = rospy.get_param("~stop_settle_s", 0.20)
        self.max_age = rospy.get_param("~encoder_max_age_s", 0.25)
        self.timeout = rospy.get_param("~stop_timeout_s", 2.0)
        self.sub = rospy.Subscriber("/encoder_data", encoder_comm, self.on_encoder, queue_size=1)

    def on_encoder(self, msg):
        now = rospy.Time.now()
        values = (msg.front_left, msg.front_right, msg.rear_left, msg.rear_right)
        with self.lock:
            gap = self.last_sample is None or (now - self.last_sample).to_sec() > self.max_age
            self.last_sample = now
            if not all(math.isfinite(v) and abs(v) <= self.limit for v in values):
                self.still_since = None
            elif gap or self.still_since is None:
                self.still_since = now

    def confirmed(self, requested_at):
        with self.lock:
            if self.still_since is None or not fresh(self.last_sample, requested_at, self.max_age):
                return False
            return (self.last_sample - max(self.still_since, requested_at)).to_sec() >= self.settle

    def stop(self, publisher):
        start = rospy.Time.now()
        rate = rospy.Rate(25)
        while not rospy.is_shutdown() and (rospy.Time.now() - start).to_sec() < self.timeout:
            publisher.publish(Twist())
            if self.confirmed(start):
                return True
            rate.sleep()
        return False


class MotionTask:
    def __init__(self, target):
        self.target = target
        self.lock = threading.RLock()
        self.seen = set()
        self.uid = None
        self.started = None
        self.deadline = None
        self.stopping = None
        self.velocity_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.feedback_pub = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)
        self.base_stop = BaseStop()

    def start(self):
        self.command_sub = rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.on_command)
        self.cancel_sub = rospy.Subscriber("/scheduler/cancel", SchedulerCommand, self.on_cancel)
        self.timer = rospy.Timer(rospy.Duration(0.04), self.tick)

    def respond(self, uid, status):
        self.feedback_pub.publish(SchedulerResponse(uid=uid, target=self.target, status=status))

    def on_command(self, msg):
        if msg.target != self.target:
            return
        with self.lock:
            if msg.uid in self.seen:
                return
            self.seen.add(msg.uid)
            if self.uid is not None:
                self.respond(msg.uid, "FAIL")
                return
            try:
                if not math.isfinite(msg.timeout) or msg.timeout <= 0:
                    raise ValueError("timeout precisa ser positivo")
                self.reset(msg.payload)
            except ValueError as exc:
                rospy.logwarn("[%s] %s", self.target, exc)
                self.respond(msg.uid, "FAIL")
                return
            self.uid = msg.uid
            self.started = rospy.Time.now()
            self.deadline = self.started + rospy.Duration(msg.timeout)

    def on_cancel(self, msg):
        with self.lock:
            if msg.target != self.target:
                return
            self.seen.add(msg.uid)
            if msg.uid == self.uid:
                self.finish("CANCELLED")

    def finish(self, status):
        self.stopping = (status, rospy.Time.now())
        self.velocity_pub.publish(Twist())

    def tick(self, _):
        with self.lock:
            if self.uid is None:
                return
            if self.stopping is None and rospy.Time.now() >= self.deadline:
                self.finish("TIMEOUT")
            if self.stopping is None:
                try:
                    self.update()
                except Exception as exc:
                    rospy.logerr("[%s] Erro no controle: %s", self.target, exc)
                    self.finish("FAIL")
                return
            self.velocity_pub.publish(Twist())
            status, started = self.stopping
            if not self.base_stop.confirmed(started):
                if (rospy.Time.now() - started).to_sec() < self.base_stop.timeout:
                    return
                rospy.logerr("[%s] Parada da base não confirmada pelos encoders", self.target)
                status = "FAIL"
            uid = self.uid
            self.uid = None
            self.stopping = None
            self.respond(uid, status)
