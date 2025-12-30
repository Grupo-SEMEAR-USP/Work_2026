#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import SchedulerCommand, SchedulerResponse, ultrasonic_comm
from collections import deque
TARGET_NAME = "align_table"
BUFFER_SIZE = 5  # Número de leituras para média móvel

# Definição dos Estados de Controle
STATE_IDLE = 0          # Aguardando comando
STATE_ALIGNING = 1      # Alinhando lateralmente (corrige diferença entre sensores)
STATE_FIX_DISTANCE = 2  # Ajustando distância (corrige profundidade)
STATE_FINISHED = 3      # Missão concluída

class AlignTable:
    def __init__(self):
        rospy.init_node('align_table', anonymous=True)
        
        # --- Parâmetros de Controle ---
        self.diff_max = 0.5    # Tolerância lateral (cm)
        self.tolerance = 1.0   # Tolerância de profundidade (cm)
        self.ang_vel = 0.1     # Velocidade angular (rad/s)
        self.lin_vel = 0.05    # Velocidade linear (m/s)
        self.control_rate = 50.0 # Frequência do loop principal [Hz]

        # --- Variáveis de Estado ---
        self.current_state = STATE_IDLE
        self.lastID = None
        self.timeout = 0.0
        self.startTime = rospy.Time(0)
        self.table_dist = 0.0      # Distância alvo (cm), vem do Scheduler payload

        # Leituras processadas
        self.dist_right = 0.0
        self.dist_left = 0.0
        self.diff = 0.0 # Diferença entre esquerdo e direito

        # Buffers de leitura
        self.buffer_left = deque(maxlen=BUFFER_SIZE)
        self.buffer_right = deque(maxlen=BUFFER_SIZE)
        
        # --- Publishers e Subscribers ---
        rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.sched_cb, queue_size=1)
        rospy.Subscriber("/ultrasonic_distances", ultrasonic_comm, self.ultrasound_callback, queue_size=1)
        
        self.pub_vel = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.pub_feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=1)

        # Inicia o loop principal de controle com um Timer não bloqueante
        rospy.Timer(rospy.Duration(1.0/self.control_rate), self.run_control_loop)

        rospy.loginfo("[align_table] Inicializado e aguardando comandos...")

    def sched_cb(self, msg):
        if msg.target != TARGET_NAME or msg.uid == self.lastID:
            return
        
        self.stop_robot() # Garantir que o robô pare antes de iniciar o novo comando

        try:
            self.table_dist = float(msg.payload)
            self.timeout = msg.timeout
            self.lastID = msg.uid
            self.startTime = rospy.Time.now()
            self.current_state = STATE_ALIGNING
            
            self.buffer_left.clear()
            self.buffer_right.clear()

            rospy.loginfo(f"[align_table] Comando recebido! Distância Alvo: {self.table_dist} cm, Timeout: {self.timeout}s.")
        
        except ValueError:
            rospy.logerr(f"Payload inválido: '{msg.payload}'. Deve ser um valor numérico para a distância.")
            self.publish_feedback(status="FAIL")


    def ultrasound_callback(self, msg: ultrasonic_comm):
        if self.current_state == STATE_IDLE:
            return
            
        self.buffer_left.append(msg.front_left)
        self.buffer_right.append(msg.front_right)

        if len(self.buffer_left) == BUFFER_SIZE:
            self.dist_left = sum(self.buffer_left) / BUFFER_SIZE
            self.dist_right = sum(self.buffer_right) / BUFFER_SIZE
            self.diff = self.dist_right - self.dist_left

            rospy.loginfo_throttle(1, f"[align_table] Médias: Esq={self.dist_left:.1f} cm, Dir={self.dist_right:.1f} cm, Diff={self.diff:.1f}")

    def publish_feedback(self, status="OK"):
        if self.lastID is None:
            return
            
        feedback = SchedulerResponse(uid=self.lastID, target=TARGET_NAME, status=status)
        self.pub_feedback.publish(feedback)
        
        rospy.loginfo(f"[align_table] Missão concluída com status: {status}")

        self.stop_robot()
        self.current_state = STATE_IDLE
        self.lastID = None
        self.startTime = rospy.Time(0)


    def stop_robot(self):
        cmd_vel = Twist()
        cmd_vel.linear.x = 0.0
        cmd_vel.linear.y = 0.0 
        cmd_vel.angular.z = 0.0
        self.vel_pub.publish(cmd_vel)


    def align_lateral(self):
        """ Estado 1: Gira o robô para zerar a diferença lateral (diff). """
        twist = Twist()
        
        # Checagem de Validade (Evita girar baseado em leituras -1 ou 0)
        if self.dist_left <= 0.0 or self.dist_right <= 0.0 or len(self.buffer_left) < BUFFER_SIZE:
            # Gira lentamente se não houver leituras válidas (procurando a mesa)
            twist.angular.z = self.ang_vel * 0.5 
            rospy.loginfo_throttle(1, "[align_table] Aguardando leituras válidas para alinhamento.")
            self.pub_vel.publish(twist)
            return

        # Condição de Transição (Pronto para Fix_Distance?)
        if abs(self.diff) <= self.diff_max:
            rospy.loginfo("[align_table] Robô alinhado lateralmente.")
            self.stop_robot()
            self.current_state = STATE_FIX_DISTANCE
            return

        # Correção de Movimento
        if self.diff > self.diff_max:    # Distância Direita > Esquerda -> Gira para a direita (angular.z negativo)
            twist.angular.z = -self.ang_vel  
        elif self.diff < -self.diff_max: # Distância Esquerda > Direita -> Gira para a esquerda (angular.z positivo)
            twist.angular.z = self.ang_vel
        self.pub_vel.publish(twist)


    def fix_distance(self):
        twist = Twist()
        
        # Usa a menor distância (mais conservador)
        dist_processada = min(self.dist_left, self.dist_right) 

        # Condição de Transição (Missão Concluída?)
        if dist_processada <= (self.table_dist + self.tolerance) and dist_processada >= (self.table_dist - self.tolerance):
            rospy.loginfo("[align_table] Robô na distância alvo.")
            self.stop_robot()
            self.current_state = STATE_FINISHED
            return

        # Correção de Movimento
        if dist_processada > (self.table_dist + self.tolerance):
            twist.linear.x = self.lin_vel       # Longe demais: Avança
        elif dist_processada < (self.table_dist - self.tolerance):
            twist.linear.x = -self.lin_vel      # Perto demais: Recua
            
        self.pub_vel.publish(twist)

    def run_control_loop(self, event):
        if self.current_state == STATE_IDLE:
            return

        # Checagem de Timeout
        if self.timeout > 0 and (rospy.Time.now() - self.startTime).to_sec() > self.timeout:
            rospy.logwarn("[align_table] Timeout excedido.")
            self.publish_feedback(status="FAIL")
            return # Sai do loop, estado já foi resetado

        # Gerenciamento de Estados
        if self.current_state == STATE_ALIGNING:
            self.align_lateral()
            
        elif self.current_state == STATE_FIX_DISTANCE:
            self.fix_distance()
            
        elif self.current_state == STATE_FINISHED:
            self.publish_feedback(status="OK")


if __name__ == '__main__':
    try:
        AlignTable()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass