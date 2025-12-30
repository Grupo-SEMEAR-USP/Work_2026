#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import SchedulerCommand, SchedulerResponse, ultrasonic_comm 
from collections import deque

# Nome do executor que responde ao Scheduler
TARGET_NAME = "border_detect"
BUFFER_SIZE = 5  # Número de leituras para média móvel

class BorderDetect:
    def __init__(self):
        rospy.init_node('border_detect', anonymous=True)
        
        # --- Configurações ---
        self.lin_vel = 0.05
        self.edge_threshold_cm = 15.0  # diferença entre sensores (em cm)
        self.control_rate = 10.0 # Frequência do loop de controle [Hz]

        # --- Variáveis de Estado ---
        self.twist = Twist()
        self.edge_detected = False
        self.movement_active = False # Flag principal para rodar o loop de controle
        self.search_direction = None
        self.timeout = 0.0          # Timeout para a missão atual
        self.start_time = rospy.Time(0) # Inicializado como zero
        self.lastID = None

        # Buffers para médias móveis
        self.buffer_left = deque(maxlen=BUFFER_SIZE)
        self.buffer_right = deque(maxlen=BUFFER_SIZE)
        
        # --- Subscribers e Publishers ---
        self.edge_detect_sub = rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.sched_cb, queue_size=10)
        self.depth_sub = rospy.Subscriber("/ultrasonic_distances", ultrasonic_comm, self.ultrasonic_edge_callback, queue_size=10)

        self.cmd_vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1) # Q_size 1 para comandos de movimento
        self.pub_feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=1)
        
        # --- Loop de Controle (Timer) ---
        rospy.Timer(rospy.Duration(1.0/self.control_rate), self.run_control_loop)

        rospy.loginfo("[border_detect] Nó iniciado. Aguardando comando...")

    def sched_cb(self, msg):
        if msg.target != TARGET_NAME or msg.uid == self.lastID:
            return

        # Parar atividade anterior antes de iniciar a nova
        if self.movement_active:
             self.stop_robot()

        self.lastID = msg.uid
        self.search_direction = msg.payload
        self.movement_active = True
        self.edge_detected = False
        self.timeout = msg.timeout
        self.start_time = rospy.Time.now()

        # Limpar buffers para iniciar a média do zero
        self.buffer_left.clear()
        self.buffer_right.clear()

        rospy.loginfo(f"[border_detect] Comando recebido! Direção: {self.search_direction}, timeout={self.timeout}s")

    def publish_feedback(self, success=True):
        feedback = SchedulerResponse()
        feedback.uid = self.lastID
        feedback.target = TARGET_NAME
        status_str = "OK" if success else "FAIL"
        feedback.status = status_str

        self.pub_feedback.publish(feedback)
        rospy.loginfo(f"[border_detect] Feedback: {status_str}")

        # Limpeza de estado após feedback
        self.movement_active = False
        self.edge_detected = False
        self.lastID = None
        self.start_time = rospy.Time(0)

    def ultrasonic_edge_callback(self, msg: ultrasonic_comm):
        if not self.movement_active or self.edge_detected:
            return

        # Assumindo que estão em centímetros
        front_left = msg.front_left
        front_right = msg.front_right
        
        self.buffer_left.append(front_left)
        self.buffer_right.append(front_right)

        # Checa a borda a cada nova leitura (mas só age com a média)
        if len(self.buffer_left) == BUFFER_SIZE:
            self.check_for_edge()


    def check_for_edge(self):
        # Calcula a média móvel e define self.edge_detected
        avg_left = sum(self.buffer_left) / BUFFER_SIZE
        avg_right = sum(self.buffer_right) / BUFFER_SIZE
        diff = abs(avg_left - avg_right)

        rospy.loginfo_throttle(1, f"[border_detect] Médias: Esq={avg_left:.1f} cm, Dir={avg_right:.1f} cm, Diferença={diff:.1f} cm")

        if diff > self.edge_threshold_cm:
            rospy.logwarn(f"[border_detect] BORDA DETECTADA! Diferença {diff:.1f} cm > limiar {self.edge_threshold_cm:.1f} cm")
            self.edge_detected = True

    def move_robot(self):
        self.twist.linear.x = 0.0
        self.twist.angular.z = 0.0
        
        if self.search_direction == "direita":
            self.twist.linear.y = -self.lin_vel
            rospy.loginfo_throttle(2, "[border_detect] Movendo para a direita...")
        elif self.search_direction == "esquerda":
            self.twist.linear.y = self.lin_vel
            rospy.loginfo_throttle(2, "[border_detect] Movendo para a esquerda...")
        else:
             # Se a direção for inválida, apenas para
             self.stop_robot()
             return

        self.cmd_vel_pub.publish(self.twist)

    def stop_robot(self):
        self.twist.linear.x = 0.0
        self.twist.linear.y = 0.0
        self.twist.angular.z = 0.0
        self.cmd_vel_pub.publish(self.twist)
        rospy.loginfo_throttle(1, "[border_detect] Robô parado.")

    def run_control_loop(self, event):
        if not self.movement_active:
            return
            
        elapsed = (rospy.Time.now() - self.start_time).to_sec()

        # Se detectou borda -> Sucesso
        if self.edge_detected:
            self.stop_robot()
            self.publish_feedback(success=True)
            return

        # Se atingiu o timeout -> Falha
        if self.timeout > 0 and elapsed > self.timeout:
            rospy.logwarn(f"[border_detect] Timeout ({self.timeout}s) atingido sem detectar borda.")
            self.stop_robot()
            self.publish_feedback(success=False)
            return

        # Continua procurando
        self.move_robot()

if __name__ == '__main__':
    try:
        BorderDetect()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass