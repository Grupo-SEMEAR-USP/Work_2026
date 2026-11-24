#!/usr/bin/env python3
"""Detecta o contêiner por cor e centraliza sua caixa no eixo horizontal."""

from collections import deque
from math import isfinite
from threading import RLock
from time import monotonic, sleep

import cv2
import rospy
from cv_bridge import CvBridge, CvBridgeError
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray, String


class SearchForContainer:
    def __init__(self):
        rospy.init_node("search_for_container", anonymous=True)

        self.camera_topic = rospy.get_param("~camera_topic", "/usb_cam_logitech/image_raw")
        self.target_color = rospy.get_param("~target_color", "any").strip().lower()
        if self.target_color not in ("red", "blue", "any"):
            raise ValueError("~target_color deve ser red, blue ou any")

        self.min_area = float(rospy.get_param("~min_area", 500.0))
        self.deadband_px = float(rospy.get_param("~deadband_px", 5.0))
        self.kp = float(rospy.get_param("~kp", 0.15))
        self.max_speed = float(rospy.get_param("~max_speed", 0.10))
        self.frame_timeout = float(rospy.get_param("~frame_timeout", 0.5))
        if not all(isfinite(value) and value > 0 for value in (
            self.min_area, self.kp, self.max_speed, self.frame_timeout
        )) or not (isfinite(self.deadband_px) and self.deadband_px >= 0):
            raise ValueError("Parâmetros de detecção e controle fora dos limites")
        self.bridge = CvBridge()

        self.color_pub = rospy.Publisher("/container_color", String, queue_size=1)
        self.position_pub = rospy.Publisher(
            "/container_position", Float32MultiArray, queue_size=1
        )
        self.offset_pub = rospy.Publisher(
            "/container_offset", Float32MultiArray, queue_size=1
        )
        self.image_pub = rospy.Publisher("/container_detection_image", Image, queue_size=1)
        self.vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.detection_publishers = (
            self.color_pub, self.position_pub, self.offset_pub, self.image_pub
        )

        self.camera_sub = None
        self.frames = None
        self.command_lock = RLock()
        self.moving = False
        self.closing = False
        self.last_motion_frame = 0.0
        rospy.on_shutdown(self.shutdown)

    def has_readers(self):
        return any(pub.get_num_connections() for pub in self.detection_publishers)

    @staticmethod
    def remember_frame(message, frames):
        frames.append((monotonic(), message))

    def find_container(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        masks = {}
        if self.target_color in ("red", "any"):
            # O matiz do vermelho aparece nas duas pontas do intervalo HSV.
            red_low = cv2.inRange(hsv, (0, 188, 32), (10, 255, 151))
            red_high = cv2.inRange(hsv, (170, 188, 32), (179, 255, 151))
            masks["red"] = cv2.bitwise_or(red_low, red_high)
        if self.target_color in ("blue", "any"):
            masks["blue"] = cv2.inRange(hsv, (90, 21, 0), (122, 185, 123))

        largest_area = 0.0
        detection = None
        for color, mask in masks.items():
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(contour)
                if area >= self.min_area and area > largest_area:
                    largest_area = area
                    detection = color, cv2.boundingRect(contour)
        return detection

    def publish_detection(self, frame, header, color, box, center, offset):
        self.color_pub.publish(String(data=color))
        self.position_pub.publish(Float32MultiArray(data=list(center)))
        self.offset_pub.publish(Float32MultiArray(data=list(offset)))

        if self.image_pub.get_num_connections():
            frame = frame.copy()
            x, y, width, height = box
            image_center_x = round((frame.shape[1] - 1) / 2.0)
            cv2.line(frame, (image_center_x, 0), (image_center_x, frame.shape[0] - 1),
                     (255, 255, 0), 1)
            cv2.rectangle(frame, (x, y), (x + width - 1, y + height - 1), (0, 255, 0), 2)
            cv2.circle(frame, (round(center[0]), round(center[1])), 4, (0, 0, 255), -1)
            debug_image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
            debug_image.header = header
            self.image_pub.publish(debug_image)

    def stop_motion(self):
        if self.moving:
            self.vel_pub.publish(Twist())
            self.moving = False

    def command_motion(self, error_x, half_width, received_at):
        with self.command_lock:
            if self.closing or not self.has_readers() or not self.is_fresh(received_at):
                self.stop_motion()
            elif abs(error_x) <= self.deadband_px:
                self.stop_motion()
            else:
                command = Twist()
                # A direita na imagem corresponde a linear.y negativo no robô.
                speed = -self.kp * error_x / half_width
                command.linear.y = max(-self.max_speed, min(speed, self.max_speed))
                self.vel_pub.publish(command)
                self.moving = True
                self.last_motion_frame = received_at

    def is_fresh(self, received_at):
        return monotonic() - received_at < self.frame_timeout

    def process_frame(self, received_at, message):
        try:
            frame = self.bridge.imgmsg_to_cv2(message, "bgr8")
            detection = self.find_container(frame)
            if detection is not None and self.has_readers() and self.is_fresh(received_at):
                color, box = detection
                x, y, width, height = box
                center = x + (width - 1) / 2.0, y + (height - 1) / 2.0
                half_width = (frame.shape[1] - 1) / 2.0
                half_height = (frame.shape[0] - 1) / 2.0
                offset = center[0] - half_width, center[1] - half_height
                self.publish_detection(frame, message.header, color, box, center, offset)
                self.command_motion(offset[0], max(1.0, half_width), received_at)
                return
        except (CvBridgeError, cv2.error, ValueError) as exc:
            rospy.logwarn_throttle(5.0, "Erro ao processar imagem: %s", exc)

        with self.command_lock:
            self.stop_motion()

    def update_camera_subscription(self):
        if self.has_readers():
            if self.camera_sub is None:
                self.frames = deque(maxlen=1)
                self.camera_sub = rospy.Subscriber(
                    self.camera_topic, Image, self.remember_frame,
                    callback_args=self.frames, queue_size=1, buff_size=2**24
                )
        elif self.camera_sub is not None:
            with self.command_lock:
                self.stop_motion()
            self.camera_sub.unregister()
            self.camera_sub = None
            self.frames = None

    def shutdown(self):
        with self.command_lock:
            self.closing = True
            self.stop_motion()

    def run(self):
        try:
            while not rospy.is_shutdown():
                self.update_camera_subscription()
                with self.command_lock:
                    if self.moving and not self.is_fresh(self.last_motion_frame):
                        self.stop_motion()
                if self.frames:
                    received_at, frame = self.frames.popleft()
                    if self.is_fresh(received_at):
                        self.process_frame(received_at, frame)
                sleep(0.05)
        finally:
            self.shutdown()


if __name__ == "__main__":
    try:
        SearchForContainer().run()
    except rospy.ROSInterruptException:
        pass
