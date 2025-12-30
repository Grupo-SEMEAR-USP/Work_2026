#!/usr/bin/env python3
import rospy
import cv2
import numpy as np
import tf.transformations as tf_trans
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo
from robot_communication.msg import AprilTagDetection, AprilTagDetectionArray
from pupil_apriltags import Detector

class AprilTagNode:
    def __init__(self):
        rospy.init_node("apriltag_detector")

        # --- Parâmetros ---
        self.camera_topic = rospy.get_param("~camera_topic", "/usb_cam_logitech/image_raw")
        self.info_topic = rospy.get_param("~camera_info", "/usb_cam_logitech/camera_info")
        self.decimate = rospy.get_param("~tag_decimate", 1.5)

        # Configuração da família
        self.family = rospy.get_param("~tag_family", "tag36h11")
        
        # Tamanho padrão da tag em metros
        self.default_size = rospy.get_param("~default_tag_size", 0.035)
        
        # Carrega tamanhos específicos do YAML
        self.tag_sizes = {}
        standalone_tags = rospy.get_param("~standalone_tags", [])
        for tag in standalone_tags:
            self.tag_sizes[tag['id']] = tag['size']

        # Inicializa Detector
        self.detector = Detector(
            families=self.family, 
            nthreads=4, 
            quad_decimate=self.decimate # Parâmetro mais importante para Range
        )
        self.bridge = CvBridge()

        # Publishers
        self.pub_detections = rospy.Publisher("/tag_detections", AprilTagDetectionArray, queue_size=10)
        self.pub_debug_img = rospy.Publisher("/tag_detections_image", Image, queue_size=1)

        # Subscribers
        rospy.Subscriber(self.info_topic, CameraInfo, self.info_cb)
        rospy.Subscriber(self.camera_topic, Image, self.image_cb, queue_size=1, buff_size=2**24)

        self.camera_params = None
        rospy.loginfo(f"Detector Iniciado! Família: {self.family}")

    def info_cb(self, msg):
        if self.camera_params is None:
            # fx, fy, cx, cy
            K = msg.K
            self.camera_params = (K[0], K[4], K[2], K[5])
            rospy.loginfo("Calibração da câmera recebida.")

    def image_cb(self, msg):
        if self.camera_params is None:
            return

        try:
            # Converte imagem ROS -> OpenCV
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # --- DETECÇÃO ---
            detections = self.detector.detect(gray, estimate_tag_pose=True, 
                                            camera_params=self.camera_params, 
                                            tag_size=self.default_size)

            msg_array = AprilTagDetectionArray()
            msg_array.header = msg.header

            for det in detections:
                tag_id = int(det.tag_id)
                
                # Verifica se essa tag tem um tamanho específico configurado
                real_size = self.tag_sizes.get(tag_id, self.default_size)
                
                # Se o tamanho real for diferente do padrão usado na detecção, ajustamos a escala da posição
                scale_factor = real_size / self.default_size
                
                # Cria a mensagem
                ros_det = AprilTagDetection()
                ros_det.id = [tag_id]
                ros_det.size = [real_size]
                ros_det.pose.header = msg.header
                
                # Posição (Ajustada pela escala)
                t_vec = det.pose_t * scale_factor
                ros_det.pose.pose.pose.position.x = t_vec[0][0]
                ros_det.pose.pose.pose.position.y = t_vec[1][0]
                ros_det.pose.pose.pose.position.z = t_vec[2][0]

                # Cria matriz 4x4 homogênea para o tf converter
                R = det.pose_R
                M = tf_trans.identity_matrix()
                M[:3, :3] = R
                q = tf_trans.quaternion_from_matrix(M)
                
                ros_det.pose.pose.pose.orientation.x = q[0]
                ros_det.pose.pose.pose.orientation.y = q[1]
                ros_det.pose.pose.pose.orientation.z = q[2]
                ros_det.pose.pose.pose.orientation.w = q[3]

                msg_array.detections.append(ros_det)

                # --- Debug Visual (Desenhar Quadrado) ---
                pts = det.corners.reshape((-1, 1, 2)).astype(np.int32)
                cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                cv2.circle(frame, (int(det.center[0]), int(det.center[1])), 5, (0, 0, 255), -1)
                cv2.putText(frame, f"ID: {tag_id}", (pts[0][0][0], pts[0][0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Publica
            self.pub_detections.publish(msg_array)
            self.pub_debug_img.publish(self.bridge.cv2_to_imgmsg(frame, "bgr8"))

        except Exception as e:
            rospy.logerr(f"Erro no processamento: {e}")

if __name__ == '__main__':
    try:
        AprilTagNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass