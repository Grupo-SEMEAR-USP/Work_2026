#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import tf
import math

class RotationCalibration:
    def __init__(self):
        rospy.init_node('rotation_calibration', anonymous=True)
        
        self.pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        self.sub_odom = rospy.Subscriber('/odom', Odometry, self.odom_cb)
        
        self.current_yaw = 0.0
        self.last_yaw = 0.0
        self.accumulated_angle = 0.0
        self.first_run = True
        
        rospy.loginfo("Aguardando odometria...")

    def odom_cb(self, msg):
        # Converte Quaternion para Euler (Yaw)
        quaternion = (
            msg.pose.pose.orientation.x,
            msg.pose.pose.orientation.y,
            msg.pose.pose.orientation.z,
            msg.pose.pose.orientation.w)
        euler = tf.transformations.euler_from_quaternion(quaternion)
        yaw = euler[2] # Eixo Z

        if self.first_run:
            self.last_yaw = yaw
            self.first_run = False
            return

        # Calcula a diferença (delta) considerando a virada de -PI para +PI
        delta = yaw - self.last_yaw
        
        # Corrige o salto de angulo (ex: de 3.14 para -3.14)
        if delta < -math.pi:
            delta += 2 * math.pi
        elif delta > math.pi:
            delta -= 2 * math.pi
            
        self.accumulated_angle += delta
        self.last_yaw = yaw

    def run_test(self, total_turns, speed_rad_s):
        # Aguarda conexões
        while self.pub.get_num_connections() == 0:
            rospy.sleep(0.1)
            
        target_angle = total_turns * 2 * math.pi
        
        rospy.loginfo(f"--- INICIANDO CALIBRAÇÃO DE ROTAÇÃO ---")
        rospy.loginfo(f"Alvo: {total_turns} voltas ({math.degrees(target_angle):.2f} graus)")
        rospy.loginfo("O robô vai girar até que a ODOMETRIA diga que chegou lá.")
        
        cmd = Twist()
        cmd.angular.z = speed_rad_s
        
        rate = rospy.Rate(50)
        
        # Zera acumulador para começar o teste agora
        self.accumulated_angle = 0.0
        self.first_run = True # Reseta a logica de delta
        rospy.sleep(0.5) # Tempo para estabilizar reset

        try:
            while abs(self.accumulated_angle) < target_angle and not rospy.is_shutdown():
                self.pub.publish(cmd)
                rate.sleep()
                
                # Feedback visual a cada volta completa
                if int(abs(self.accumulated_angle) / (2*math.pi)) > int((abs(self.accumulated_angle) - abs(cmd.angular.z/50.0)) / (2*math.pi)):
                     rospy.loginfo(f"Completou uma volta na odometria...")

        except KeyboardInterrupt:
            pass
        finally:
            # Para o robô
            stop_cmd = Twist()
            self.pub.publish(stop_cmd)
            rospy.sleep(2) # Aguarda estabilização
            rospy.loginfo(f"--- FIM ---")
            rospy.loginfo(f"Odometria final: {math.degrees(self.accumulated_angle):.2f} graus")
            rospy.loginfo("Agora verifique o alinhamento físico no chão.")

if __name__ == "__main__":
    try:
        tester = RotationCalibration()
        # run_test(numero de voltas, velocidade (rad/s))
        tester.run_test(1, 1.0) 
    except rospy.ROSInterruptException:
        pass