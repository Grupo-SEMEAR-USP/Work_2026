#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math
import sys

class OmniCalibration:
    def __init__(self):
        rospy.init_node('teste_linear', anonymous=True)
        self.pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        self.sub = rospy.Subscriber('/odom', Odometry, self.odom_cb)
        
        self.current_x = 0.0
        self.current_y = 0.0
        self.start_x = 0.0
        self.start_y = 0.0
        self.first_odom_received = False

    def odom_cb(self, msg):
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y
        self.first_odom_received = True

    def get_distance_moved(self):
        dx = self.current_x - self.start_x
        dy = self.current_y - self.start_y
        return math.sqrt(dx**2 + dy**2), dx, dy

    def run_test(self, axis, target_distance, speed):
        # Espera inicialização
        while not self.first_odom_received and not rospy.is_shutdown():
            rospy.loginfo("Aguardando odometria...")
            rospy.sleep(0.5)

        # Estabiliza e zera referência
        rospy.sleep(1)
        self.start_x = self.current_x
        self.start_y = self.current_y
        
        cmd = Twist()
        
        # Configura a velocidade baseada no eixo
        if axis.lower() == 'x':
            cmd.linear.x = speed
            cmd.linear.y = 0.0
            test_name = "Longitudinal (X)"
        elif axis.lower() == 'y':
            cmd.linear.x = 0.0
            cmd.linear.y = speed
            test_name = "Lateral (Y)"
        else:
            rospy.logerr("Eixo inválido! Use 'x' ou 'y'")
            return

        rospy.loginfo(f"--- INICIANDO TESTE {test_name} ---")
        rospy.loginfo(f"Meta: {target_distance}m | Velocidade: {speed} m/s")
        rospy.loginfo(f"Start Odom: X={self.start_x:.3f}, Y={self.start_y:.3f}")

        rate = rospy.Rate(50)
        
        while not rospy.is_shutdown():
            dist_total, dx, dy = self.get_distance_moved()
            
            # Para se atingir a distância (usamos valor absoluto para garantir)
            # Para o teste, focamos na distância Euclidiana total percorrida
            if dist_total >= target_distance:
                break
            
            self.pub.publish(cmd)
            rate.sleep()
            
        # Parar o robô
        stop_cmd = Twist()
        self.pub.publish(stop_cmd)
        rospy.sleep(1) # Espera parar totalmente
        
        # Relatório Final
        final_dist, final_dx, final_dy = self.get_distance_moved()
        
        print("\n" + "="*30)
        print(f"RESULTADO DO TESTE DE EIXO [{axis.upper()}]")
        print("="*30)
        print(f"Distância Total (Odom): {final_dist:.4f} m")
        print(f"Delta X (Frente):       {final_dx:.4f} m")
        print(f"Delta Y (Lado):         {final_dy:.4f} m")
        print("-" * 30)
        print(f"--> Agora meça com a régua a distância REAL no chão.")
        print("="*30 + "\n")

if __name__ == "__main__":
    try:
        tester = OmniCalibration()
                
        # Configurar o teste aqui
        tester.run_test(axis='x', target_distance=2.0, speed=0.3)
        
    except rospy.ROSInterruptException:
        pass