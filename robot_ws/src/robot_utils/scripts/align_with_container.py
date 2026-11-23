#!/usr/bin/env python3
import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge, CvBridgeError
from robot_communication.msg import ContainerDetection, ContainerDetectionArray
from sensor_msgs.msg import Image


class ContainerDetector:
    def __init__(self):
        self.bridge = CvBridge()
        ranges = rospy.get_param("~colors")
        self.colors = {
            color.strip().lower(): [(np.array(low, dtype=np.uint8), np.array(high, dtype=np.uint8))
                                     for low, high in bounds]
            for color, bounds in ranges.items()
        }
        self.roi = rospy.get_param("~roi", [0.0, 0.0, 1.0, 1.0])
        self.min_area = rospy.get_param("~min_area_px", 500.0)
        self.max_area = rospy.get_param("~max_area_fraction", 0.45)
        self.min_fill = rospy.get_param("~min_fill", 0.42)
        self.max_aspect = rospy.get_param("~max_aspect", 3.0)
        kernel_size = rospy.get_param("~kernel_size", 5)
        x1, y1, x2, y2 = self.roi
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1 and kernel_size >= 1):
            raise ValueError("ROI ou kernel de detecção inválido")
        self.kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        self.publisher = rospy.Publisher("/container_detections", ContainerDetectionArray, queue_size=1)
        camera = rospy.get_param("~image_topic", "/usb_cam_logitech/image_raw")
        self.subscriber = rospy.Subscriber(camera, Image, self.on_image, queue_size=1, buff_size=2**24)

    def detect(self, image):
        height, width = image.shape[:2]
        left, top, right, bottom = (int(scale * size) for scale, size
                                    in zip(self.roi, (width, height, width, height)))
        if left >= right or top >= bottom:
            return
        hsv = cv2.cvtColor(image[top:bottom, left:right], cv2.COLOR_BGR2HSV)
        for color, bounds in self.colors.items():
            mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
            for low, high in bounds:
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv, low, high))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if not self.min_area <= area <= width * height * self.max_area:
                    continue
                _, _, w, h = cv2.boundingRect(contour)
                if max(w, h) / min(w, h) > self.max_aspect or area / (w * h) < self.min_fill:
                    continue
                moments = cv2.moments(contour)
                if moments["m00"] > 0:
                    yield ContainerDetection(
                        color=color, center_x=left + moments["m10"] / moments["m00"],
                        center_y=top + moments["m01"] / moments["m00"], area_px=area,
                    )

    def on_image(self, msg):
        try:
            image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            result = list(self.detect(image))
        except (CvBridgeError, cv2.error) as exc:
            rospy.logwarn_throttle(2, "Falha ao processar contêineres: %s", exc)
            result = []
        self.publisher.publish(ContainerDetectionArray(
            header=msg.header, image_width=msg.width, image_height=msg.height, detections=result,
        ))


if __name__ == "__main__":
    rospy.init_node("container_detector")
    ContainerDetector()
    rospy.spin()
