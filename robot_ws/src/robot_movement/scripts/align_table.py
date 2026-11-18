#!/usr/bin/env python3
import math
import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
from tf.transformations import euler_from_quaternion
from robot_communication.msg import SchedulerCommand, SchedulerResponse, ultrasonic_comm
from collections import deque
TARGET_NAME = "approach_table"
BUFFER_SIZE = 5  # Número de leituras para média móvel
IMU_TOPIC = "/imu/data_filtered"  # Mesmo tópico usado pelo hw_interface

# Definição dos Estados de Controle
STATE_IDLE = 0          # Aguardando comando
STATE_PRE_ALIGNING = 1  # Girando para alinhar com a mesa (90 graus)
STATE_ALIGNING = 2      # Alinhando lateralmente (corrige diferença entre sensores)
STATE_FIX_DISTANCE = 3  # Ajustando distância (corrige profundidade)
STATE_FINISHED = 4      # Missão concluída

class AlignTable:
    def __init__(self):
        rospy.init_node('approach_table', anonymous=True)
        
        # --- Parâmetros de Controle ---
        self.diff_max = 0.5    # Tolerância de desalinhamento (cm)
        self.tolerance = 1.0   # Tolerância de profundidade (cm)
        self.ang_vel = 0.1     # Velocidade angular (rad/s)
        self.lin_vel = 0.05    # Velocidade linear (m/s)
        self.control_rate = 50.0 # Frequência do loop principal [Hz]

        # --- Parâmetros do Pré-Alinhamento (IMU) ---
        self.pre_align_vel = self.ang_vel * 0.5             # Velocidade angular do giro de 90° (rad/s)
        self.pre_align_target = math.radians(90.0)          # Ângulo a girar (rad)
        self.pre_align_tolerance = math.radians(2.0)        # Tolerância do giro (rad)
        self.imu_timeout = 0.5                              # Tempo máximo sem mensagens da IMU (s)

        # --- Variáveis de Estado ---
        self.current_state = STATE_IDLE
        self.align_type = None
        self.lastID = None
        self.timeout = 0.0
        self.startTime = rospy.Time(0)
        self.table_dist = 0.0      # Distância alvo (cm), vem do Scheduler payload

        # Leituras processadas
        self.dist_front_right = 0.0
        self.dist_front_left = 0.0
        self.dist_right_front = 0.0
        self.dist_right_back = 0.0
        self.dist_left_front = 0.0
        self.dist_left_back = 0.0

        self.diff_front = 0.0 # Diferença entre esquerdo e direito
        self.diff_right = 0.0 
        self.diff_left = 0.0 

        # Buffers de leitura
        self.buffer_front_left = deque(maxlen=BUFFER_SIZE)
        self.buffer_front_right = deque(maxlen=BUFFER_SIZE)
        self.buffer_right_front = deque(maxlen=BUFFER_SIZE)
        self.buffer_right_back = deque(maxlen=BUFFER_SIZE)
        self.buffer_left_front = deque(maxlen=BUFFER_SIZE)
        self.buffer_left_back = deque(maxlen=BUFFER_SIZE)

        # Leituras da IMU
        self.last_yaw = None                # Último yaw lido (rad), em [-pi, pi]
        self.accumulated_yaw = 0.0          # Ângulo girado desde o início do pré-alinhamento (rad)
        self.last_imu_time = rospy.Time(0)  # Instante da última mensagem da IMU

        # --- Publishers e Subscribers ---
        rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.sched_cb, queue_size=1)
        rospy.Subscriber("/ultrasonic_distances", ultrasonic_comm, self.ultrasound_callback, queue_size=1)
        rospy.Subscriber(IMU_TOPIC, Imu, self.imu_callback, queue_size=1)
        
        self.pub_vel = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.pub_feedback = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=1)

        # Inicia o loop principal de controle com um Timer não bloqueante
        rospy.Timer(rospy.Duration(1.0/self.control_rate), self.run_control_loop)

        rospy.loginfo("[approach_table] Inicializado e aguardando comandos...")

    def sched_cb(self, msg):
        if msg.target != TARGET_NAME or msg.uid == self.lastID:
            return
        
        self.stop_robot() # Garantir que o robô pare antes de iniciar o novo comando

        try:
            self.align_type, self.table_dist = [p.strip().lower() for p in msg.payload.split(",")]
            self.table_dist = float(self.table_dist)
            self.timeout = msg.timeout
            self.lastID = msg.uid
            self.startTime = rospy.Time.now()
            self.clear_buffers()

            if self.align_type in ["right", "left"]:
                # Zera o acumulador antes de mudar o estado, para o giro ser medido a partir de agora
                self.accumulated_yaw = 0.0
                self.current_state = STATE_PRE_ALIGNING
            else:
                self.current_state = STATE_ALIGNING

            rospy.loginfo(f"[approach_table] Comando recebido! Tipo: {self.align_type}, Distância Alvo: {self.table_dist} cm, Timeout: {self.timeout}s.")
        
        except ValueError:
            rospy.logerr(f"Payload inválido: '{msg.payload}'. Deve ser um valor numérico para a distância.")
            self.publish_feedback(status="FAIL")


    def clear_buffers(self):
        self.buffer_front_left.clear()
        self.buffer_front_right.clear()
        self.buffer_right_front.clear()
        self.buffer_right_back.clear()
        self.buffer_left_front.clear()
        self.buffer_left_back.clear()


    def imu_callback(self, msg: Imu):
        """ Lê o yaw da IMU e, durante o pré-alinhamento, acumula o quanto o robô girou. """
        q = msg.orientation
        _, _, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])

        if self.current_state == STATE_PRE_ALIGNING and self.last_yaw is not None:
            # Diferença entre leituras, corrigindo o salto de -pi para +pi (e vice-versa)
            delta = yaw - self.last_yaw
            if delta > math.pi:
                delta -= 2.0 * math.pi
            elif delta < -math.pi:
                delta += 2.0 * math.pi
            self.accumulated_yaw += delta

        self.last_yaw = yaw
        self.last_imu_time = rospy.Time.now()


    def ultrasound_callback(self, msg: ultrasonic_comm):
        if self.current_state == STATE_IDLE:
            return
            
        self.buffer_front_left.append(msg.front_left)
        self.buffer_front_right.append(msg.front_right)
        self.buffer_right_front.append(msg.right_front)
        self.buffer_right_back.append(msg.right_back)
        self.buffer_left_front.append(msg.left_front)
        self.buffer_left_back.append(msg.left_back)

        if len(self.buffer_front_left) == BUFFER_SIZE:
            self.dist_front_left = sum(self.buffer_front_left) / BUFFER_SIZE
            self.dist_front_right = sum(self.buffer_front_right) / BUFFER_SIZE
            self.dist_right_front = sum(self.buffer_right_front) / BUFFER_SIZE
            self.dist_right_back = sum(self.buffer_right_back) / BUFFER_SIZE
            self.dist_left_front = sum(self.buffer_left_front) / BUFFER_SIZE
            self.dist_left_back = sum(self.buffer_left_back) / BUFFER_SIZE

            # diff > 0 => Girar para a direita
            self.diff_front = self.dist_front_left - self.dist_front_right
            self.diff_right = self.dist_right_back - self.dist_right_front
            self.diff_left = self.dist_left_front - self.dist_left_back

            rospy.loginfo_throttle(1, f"[approach_table] Médias FRONT: Esq = {self.dist_front_left:.1f} cm, Dir = {self.dist_front_right:.1f} cm, Diff = {self.diff_front:.1f}")
            rospy.loginfo_throttle(1, f"[approach_table] Médias RIGHT: Front = {self.dist_right_front:.1f} cm, Back = {self.dist_right_back:.1f} cm, Diff = {self.diff_right:.1f}")
            rospy.loginfo_throttle(1, f"[approach_table] Médias LEFT: Front = {self.dist_left_front:.1f} cm, Back = {self.dist_left_back:.1f} cm, Diff = {self.diff_left:.1f}")

    def publish_feedback(self, status="OK"):
        if self.lastID is None:
            return
            
        feedback = SchedulerResponse(uid=self.lastID, target=TARGET_NAME, status=status)
        self.pub_feedback.publish(feedback)
        
        rospy.loginfo(f"[approach_table] Missão concluída com status: {status}")

        self.stop_robot()
        self.current_state = STATE_IDLE
        self.lastID = None
        self.startTime = rospy.Time(0)


    def stop_robot(self):
        cmd_vel = Twist()
        cmd_vel.linear.x = 0.0
        cmd_vel.linear.y = 0.0 
        cmd_vel.angular.z = 0.0
        self.pub_vel.publish(cmd_vel)


    def align(self, align_type):
        """ Estado 1: Gira o robô para zerar a diferença entre ultras (diff). """
        twist = Twist()

        # Variáveis locais
        dist_1 = 0.0    
        dist_2 = 0.0    
        diff = 0.0
        buffer = None

        if align_type == "front":
            # A atribuição delas não importa de fato, pois a variavél só é pra verificar a validade da leitura
            dist_1 = self.dist_front_right
            dist_2 = self.dist_front_left
            buffer = self.buffer_front_left   # um dos buffers para checar se há leituras válidas
            diff = self.diff_front
        if align_type == "right":
            dist_1 = self.dist_right_front
            dist_2 = self.dist_right_back
            buffer = self.buffer_right_front   
            diff = self.diff_right
        if align_type == "left":
            dist_1 = self.dist_left_front
            dist_2 = self.dist_left_back
            buffer = self.buffer_left_front   
            diff = self.diff_left

        # Checagem de Validade (Evita girar baseado em leituras -1 ou 0)
        if dist_1 <= 0.0 or dist_2 <= 0.0 or len(buffer) < BUFFER_SIZE:
            # Gira lentamente se não houver leituras válidas (procurando a mesa)
            twist.angular.z = self.ang_vel * 0.5 
            rospy.loginfo_throttle(1, "[approach_table] Aguardando leituras válidas para alinhamento.")
            self.pub_vel.publish(twist)
            return

        # Condição de Transição (Pronto para Fix_Distance?)
        if abs(diff) <= self.diff_max:
            rospy.loginfo("[approach_table] Robô alinhado.")
            self.stop_robot()
            self.current_state = STATE_FIX_DISTANCE
            return

        # Correção de Movimento
        if diff > self.diff_max:    # Gira para a direita (angular.z negativo)
            twist.angular.z = -self.ang_vel  
        elif diff < -self.diff_max: # Gira para a esquerda (angular.z positivo)
            twist.angular.z = self.ang_vel
        self.pub_vel.publish(twist)


    def fix_distance(self, align_type):
        twist = Twist()
        if align_type == "front":
            dist_1 = self.dist_front_right
            dist_2 = self.dist_front_left
        elif align_type == "right":
            dist_1 = self.dist_right_front
            dist_2 = self.dist_right_back
        elif align_type == "left":  
            dist_1 = self.dist_left_front
            dist_2 = self.dist_left_back
        
        # Usa a menor distância (mais conservador)
        dist_processada = min(dist_1, dist_2) 

        # Condição de Transição (Missão Concluída?)
        if dist_processada <= (self.table_dist + self.tolerance) and dist_processada >= (self.table_dist - self.tolerance):
            rospy.loginfo("[approach_table] Robô na distância alvo.")
            self.stop_robot()
            self.current_state = STATE_FINISHED
            return

        # Correção de Movimento
        if dist_processada > (self.table_dist + self.tolerance):    # Longe demais: Avança
            if align_type == "front":
                twist.linear.x = self.lin_vel
            elif align_type == "right":
                twist.linear.y = -self.lin_vel
            else:
                twist.linear.y = self.lin_vel

        elif dist_processada < (self.table_dist - self.tolerance):  # Perto demais: Recua
            if align_type == "front":
                twist.linear.x = -self.lin_vel
            elif align_type == "right":
                twist.linear.y = self.lin_vel
            else:
                twist.linear.y = -self.lin_vel     
            
        self.pub_vel.publish(twist)

    def pre_align(self, align_type):
        """ Gira o robô 90 graus para alinhar com a mesa antes de iniciar o alinhamento lateral.
            O ângulo girado é medido pela IMU (self.accumulated_yaw, atualizado em imu_callback). """
        twist = Twist()

        # Sem IMU (nunca recebeu ou parou de publicar): não gira às cegas
        imu_age = (rospy.Time.now() - self.last_imu_time).to_sec()
        if self.last_yaw is None or imu_age > self.imu_timeout:
            self.stop_robot()
            rospy.logwarn_throttle(1, f"[approach_table] Sem dados da IMU em {IMU_TOPIC}. Aguardando para o pré-alinhamento.")
            return

        # Condição de Transição (girou 90 graus?)
        # abs(): o sentido já é definido pelo comando, então só a magnitude importa
        rotated = abs(self.accumulated_yaw)
        if rotated >= self.pre_align_target - self.pre_align_tolerance:
            self.stop_robot()
            rospy.loginfo(f"[approach_table] Pré-alinhamento concluído. Giro medido pela IMU: {math.degrees(self.accumulated_yaw):.1f} graus.")
            # Descarta leituras dos ultrassons feitas durante o giro
            self.clear_buffers()
            self.current_state = STATE_ALIGNING
            return

        if align_type == "right":
            # Gira para a esquerda (angular.z positivo)
            twist.angular.z = self.pre_align_vel
        else:
            # Gira para a direita (angular.z negativo)
            twist.angular.z = -self.pre_align_vel

        rospy.loginfo_throttle(1, f"[approach_table] Pré-alinhando: {math.degrees(rotated):.1f} / {math.degrees(self.pre_align_target):.0f} graus.")
        self.pub_vel.publish(twist)

    def run_control_loop(self, event):
        if self.current_state == STATE_IDLE:
            return

        # Checagem de Timeout
        if self.timeout > 0 and (rospy.Time.now() - self.startTime).to_sec() > self.timeout:
            rospy.logwarn("[approach_table] Timeout excedido.")
            self.publish_feedback(status="FAIL")
            return # Sai do loop, estado já foi resetado

        # SÓ SE A NAVEGAÇÃO NÃO CUIDAR DE JÁ DEIXAR VIRADO
        if self.current_state == STATE_PRE_ALIGNING:
            self.pre_align(align_type=self.align_type)
            return

        # Gerenciamento de Estados
        if self.current_state == STATE_ALIGNING:
            self.align(align_type=self.align_type)
            
        elif self.current_state == STATE_FIX_DISTANCE:
            self.fix_distance(align_type=self.align_type)
            
        elif self.current_state == STATE_FINISHED:
            self.publish_feedback(status="OK")


if __name__ == '__main__':
    try:
        AlignTable()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass