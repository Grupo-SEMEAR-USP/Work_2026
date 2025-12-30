#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist, Point
from robot_communication.msg import SchedulerCommand, SchedulerResponse, AprilTagDetectionArray

# Nome do executor que responde ao Scheduler
TARGET_NAME = "align_block"

class AlignBlock:
    def __init__(self):
        rospy.init_node('align_block', anonymous=True)

        # --- Parâmetros ---
        self.max_search_time = 15.0 # Timeout total
        self.convergence_tolerance_xy = 0.01 # cm
        self.vel_linear = 0.1
        self.vel_angular = 0.3
        self.control_rate = 10.0 # Frequência do loop de controle [Hz]

        # Offset da garra (em relação ao centro da câmera, em metros)
        self.offset_y = 0.0475
        self.offset_x = 0.0

        # Parâmetros de Distância Alvo
        self.target_z = 0.30          
        self.tol_z = 0.05

        # --- Variáveis de Estado ---
        self.is_active = False              # Se está executando um comando do Scheduler
        self.has_converged = False          # Se o alinhamento terminou com sucesso
        self.target_block_id = None
        self.last_sched_uid = None
        self.command_start_time = None
        self.last_valid_position = Point()  # Última pose válida (x, y, z)
        
        # --- Publishers & Subscribers ---
        self.vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.feedback_pub = rospy.Publisher('/scheduler/feedback', SchedulerResponse, queue_size=1)
        
        rospy.Subscriber('/tag_detections', AprilTagDetectionArray, self.tag_detections_callback)
        rospy.Subscriber('/scheduler/commands', SchedulerCommand, self.sched_callback)
        
        # --- Loop de Controle ---
        rospy.Timer(rospy.Duration(1.0/self.control_rate), self.run_control_loop)
        
        rospy.loginfo("[align_block] Inicializado e aguardando comandos...")

    def sched_callback(self, msg: SchedulerCommand):
        if msg.target != TARGET_NAME or msg.uid == self.last_sched_uid:
            return

        # Parar a operação atual
        if self.is_active:
             self.stop_robot()
        
        # Inicializar novo comando
        try:
            self.target_block_id = int(msg.payload)
        except ValueError:
            rospy.logerr(f"Payload inválido: '{msg.payload}'. Deve ser um ID de bloco inteiro.")
            self.send_feedback("FAIL")
            return

        self.last_sched_uid = msg.uid
        self.command_start_time = rospy.Time.now()
        self.max_search_time = msg.timeout
        self.is_active = True
        self.has_converged = False
        self.last_valid_position = None # Resetar a posição ao iniciar

        rospy.loginfo(f"Busca pelo bloco de ID {self.target_block_id} iniciado.")


    def send_feedback(self, status):
        if self.last_sched_uid is None:
            return
            
        fb_msg = SchedulerResponse(uid=self.last_sched_uid, target=TARGET_NAME, status=status)
        
        # Publicar algumas vezes para garantir que o scheduler receba
        for _ in range(3):
            self.feedback_pub.publish(fb_msg)
            rospy.sleep(0.05)
            
        # Reseta o estado principal (parar o robô e esperar próximo comando)
        self.stop_robot()
        self.is_active = False
        self.last_sched_uid = None # Limpa o UID após o feedback

    def tag_detections_callback(self, data: AprilTagDetectionArray):
        if not self.is_active or self.has_converged:
            return

        target_detected = False
        
        for detection in data.detections:
            if detection.id[0] == self.target_block_id:
                # Armazena a posição do bloco no frame da câmera
                self.last_valid_position = detection.pose.pose.pose.position
                target_detected = True
                break # Encontrou o alvo, pode parar de procurar

        if not target_detected:
            self.last_valid_position = None # Indica que o bloco foi perdido

    # --- Controle (Timer Loop) ---
    def run_control_loop(self, event):
        if not self.is_active or self.has_converged:
            return

        # Gerenciamento de Timeout (Se o tempo total exceder o limite)
        if self.command_start_time and \
           (rospy.Time.now() - self.command_start_time).to_sec() > self.max_search_time:
            
            rospy.logwarn(f"Timeout de {self.max_search_time}s excedido. Desistindo da busca.")
            self.send_feedback("FAIL")
            return

        # Execução da Tarefa
        if self.last_valid_position is not None:
            # Bloco está visível: Tentar alinhamento
            self.align_with_position(self.last_valid_position)
        else:
            # Bloco não está visível: Lógica de Busca/Parada
            self.search_or_stop()
    
    def search_or_stop(self):
        # Se o robô perdeu a tag, ele para e fica esperando uma nova leitura.
        self.stop_robot()
        rospy.loginfo_throttle(5, "Bloco alvo perdido. Parado e aguardando nova detecção.")

    def align_with_position(self, position: Point):
        cmd_vel = Twist()

        # Compensa o deslocamento da garra
        adjusted_x = position.x - self.offset_x 
        adjusted_z = position.z 
              
        tol_x = self.convergence_tolerance_xy # 0.01 m (1 cm)
        target_z = 0.30 
        tol_z = 0.05
        
        # Alinhamento Lateral (Eixo X da câmera -> - Linear Y do robô)
        if abs(adjusted_x) > tol_x:            
            cmd_vel.linear.y = -self.vel_linear if adjusted_x > 0 else self.vel_linear 
            rospy.loginfo_throttle(0.5, f"AJUSTE LATERAL (X -> Y): Erro={adjusted_x:.4f}m, Velocidade={cmd_vel.linear.y:.2f}")

        # Profundidade (Eixo Z da câmera -> Linear X do robô)
        elif abs(adjusted_z - target_z) > tol_z:
            if adjusted_z > target_z:
                cmd_vel.linear.x = self.vel_linear
            else:
                cmd_vel.linear.x = -self.vel_linear
            
            rospy.loginfo_throttle(0.5, f"AJUSTE PROFUNDIDADE (Z -> X): Dist={adjusted_z:.4f}m, Velocidade={cmd_vel.linear.x:.2f}")

        # Convergência
        else:
            rospy.loginfo("Robô alinhado horizontalmente e na distância alvo.")
            self.stop_robot()
            self.has_converged = True
            self.send_feedback("OK")
            return 
        
        # Publica o comando de movimento (se não tiver convergido)
        self.vel_pub.publish(cmd_vel)


    def stop_robot(self):
        cmd_vel = Twist()
        cmd_vel.linear.x = 0.0
        cmd_vel.linear.y = 0.0 
        cmd_vel.angular.z = 0.0
        self.vel_pub.publish(cmd_vel)

if __name__ == '__main__':
    try:
        AlignBlock()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass