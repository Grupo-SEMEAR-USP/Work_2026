
#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Image
from std_msgs.msg import String, Float32MultiArray
import cv2
import numpy as np


class SearchForContainer:

    def __init__(self):

        rospy.init_node('search_for_container', anonymous=True)

        self.camera_image = None
        self.image_received = False

        # Limites HSV
        self.blue_lower_hsv = np.array([90, 21, 0])
        self.blue_upper_hsv = np.array([122, 185, 123])

        self.red_lower_hsv1 = np.array([0, 188, 32])
        self.red_upper_hsv1 = np.array([179, 255, 151])

        # Publishers
        self.container_color_pub = rospy.Publisher(
            '/container_color', String, queue_size=10
        )

        self.container_position_pub = rospy.Publisher(
            '/container_position', Float32MultiArray, queue_size=10
        )

        # Subscriber da câmera
        rospy.Subscriber(
            '/usb_cam_logitech/image_raw',
            Image,
            self.camera_callback
        )

    # Criar máscara
    def create_mask(self, image, left_limit, right_limit):

        h, w = image.shape[:2]

        left_mask_points = np.array([
            (0, 0),
            (left_limit, 0),
            (left_limit, h),
            (0, h)
        ])

        right_mask_points = np.array([
            (right_limit, 0),
            (w, 0),
            (w, h),
            (right_limit, h)
        ])

        mask = np.ones_like(image) * 255

        cv2.fillPoly(mask, [left_mask_points], (0, 0, 0))
        cv2.fillPoly(mask, [right_mask_points], (0, 0, 0))

        return cv2.bitwise_and(image, mask)

    # Encontrar cor e posição
    def find_container(self, roi):

        hsv_image = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        red_mask = cv2.inRange(
            hsv_image,
            self.red_lower_hsv1,
            self.red_upper_hsv1
        )

        blue_mask = cv2.inRange(
            hsv_image,
            self.blue_lower_hsv,
            self.blue_upper_hsv
        )

        red_pixels = cv2.countNonZero(red_mask)
        blue_pixels = cv2.countNonZero(blue_mask)

        if red_pixels > blue_pixels:
            mask = red_mask
            color = "red"

        elif blue_pixels > red_pixels:
            mask = blue_mask
            color = "blue"

        else:
            return "unknown", None

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return "unknown", None

        largest = max(contours, key=cv2.contourArea)

        if cv2.contourArea(largest) < 500:
            return "unknown", None

        M = cv2.moments(largest)

        if M["m00"] == 0:
            return "unknown", None

        center_x = int(M["m10"] / M["m00"])
        center_y = int(M["m01"] / M["m00"])

        return color, (center_x, center_y)

    # Publicar informações
    def publish_container(self, color, position):

        if color == "unknown" or position is None:
            return

        self.container_color_pub.publish(
            String(data=color)
        )

        self.container_position_pub.publish(
            Float32MultiArray(data=[position[0], position[1]])
        )

        rospy.loginfo(
            f"Container: {color} | Posição X: {position[0]}, Y: {position[1]}"
        )

    # Callback da câmera
    def camera_callback(self, img_msg):

        try:

            if img_msg.encoding != "rgb8":
                rospy.logwarn(
                    f"Formato inesperado: {img_msg.encoding}"
                )
                return

            self.camera_image = np.frombuffer(
                img_msg.data,
                dtype=np.uint8
            ).reshape(
                img_msg.height,
                img_msg.width,
                3
            )

            self.camera_image = cv2.cvtColor(
                self.camera_image,
                cv2.COLOR_RGB2BGR
            )

            self.image_received = True

            # Aplicar máscara
            roi = self.create_mask(
                self.camera_image,
                left_limit=100,
                right_limit=500
            )

            # Encontrar cor e posição
            color, position = self.find_container(roi)

            # Publicar continuamente
            self.publish_container(color, position)

            # Centro da imagem nos eixos X (horizontal) e Y (vertical)
            image_center_x = self.camera_image.shape[1] // 2
            image_center_y = self.camera_image.shape[0] // 2

            cv2.line(
                self.camera_image,
                (image_center_x, 0),
                (image_center_x, self.camera_image.shape[0]),
                (255, 0, 0),
                2
            )
            cv2.line(
                self.camera_image,
                (0, image_center_y),
                (self.camera_image.shape[1], image_center_y),
                (0, 255, 255),
                2
            )

            if position is not None:

                error_x = position[0] - image_center_x
                error_y = position[1] - image_center_y

                rospy.loginfo(
                    f"Erro de centralização: X={error_x}, Y={error_y}"
                )

                cv2.circle(
                    self.camera_image,
                    position,
                    5,
                    (0, 255, 0),
                    -1
                )

            cv2.imshow("Search Container", self.camera_image)
            cv2.waitKey(1)

        except Exception as e:

            rospy.logerr(
                f"Erro no processamento: {e}"
            )

            self.image_received = False

    def run(self):

        rospy.spin()
        cv2.destroyAllWindows()


if __name__ == '__main__':

    try:
        node = SearchForContainer()
        node.run()

    except rospy.ROSInterruptException:
        pass
