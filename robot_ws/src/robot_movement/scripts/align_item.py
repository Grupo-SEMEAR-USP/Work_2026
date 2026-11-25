#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import (
    SchedulerCommand,
    SchedulerResponse,
    AprilTagDetectionArray,
    container_comm,
)
 
# Nomes de target que este nó aceita do Scheduler
ACCEPTED_TARGETS = ("align_block", "align_item")
 
 
class AlignItem:
    def __init__(self):
        rospy.init_node('align_item', anonymous=True)
 
        #Parâmetros gerais 
        self.max_search_time = rospy.get_param("~default_timeout", 15.0)
        self.vel_linear = rospy.get_param("~vel_linear", 0.1)
        self.control_rate = rospy.get_param("~control_rate", 10.0)  # Hz
        self.lost_timeout = rospy.get_param("~lost_timeout", 0.5)   # s sem detecção = alvo perdido
 
        # --- Bloco (AprilTag, unidades em metros) ---
        # Offset da garra em relação ao centro da câmera
        self.offset_x = rospy.get_param("~offset_x", 0.0)
        self.offset_y = rospy.get_param("~offset_y", 0.0475)  # (ainda não usado)
        self.tol_x = rospy.get_param("~tol_x", 0.02)          # 2 cm (1 cm oscila a 0.1 m/s e 10 Hz)
        self.target_z = rospy.get_param("~target_z", 0.30)
        self.tol_z = rospy.get_param("~tol_z", 0.05)
 
        # Container (câmera, unidades em pixels)
        # Erro vem do findcontainer: posição do centróide - centro da imagem
        self.tol_x_px = rospy.get_param("~container_tol_x_px", 15)
        self.tol_y_px = rospy.get_param("~container_tol_y_px", 15)
        # Alinhamento em Y (frente/trás) pelo erro vertical da imagem.
        # Desativado por padrão: precisa testar o sinal com a câmera montada.
        self.container_align_y = rospy.get_param("~container_align_y", False)
        self.container_y_sign = rospy.get_param("~container_y_sign", 1.0)
 
        #Estado
        self.is_active = False
        self.has_converged = False
        self.mode = None               # "block" ou "container"
        self.target_block_ids = []
        self.target_color = None
        self.cmd_target = None         # nome de target do comando atual (para o feedback)
        self.last_sched_uid = None     # UID do comando em andamento
        self.last_handled_uid = None   # último UID já tratado (evita reexecutar)
        self.command_start_time = None
 
        self.block_position = None     # Point da AprilTag
        self.block_stamp = None
        self.container_error = None    # (erro_x_px, erro_y_px)
        self.container_stamp = None
 
        #Publishers e Subscribers 
        self.vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.feedback_pub = rospy.Publisher('/scheduler/feedback', SchedulerResponse, queue_size=1)
 
        rospy.Subscriber('/tag_detections', AprilTagDetectionArray, self.tag_detections_callback)
        rospy.Subscriber('/container_info', container_comm, self.container_callback)
        rospy.Subscriber('/scheduler/commands', SchedulerCommand, self.sched_callback)
 
        # Loop de controle 
        rospy.Timer(rospy.Duration(1.0 / self.control_rate), self.run_control_loop)
 
        rospy.loginfo("[align_item] Inicializado e aguardando comandos...")
 

    # Scheduler

    def parse_payload(self, payload):
        parts = [p.strip() for p in payload.split(',')]
 
        # Compatibilidade: payload antigo era só o ID do bloco
        if parts[0].lstrip('-').isdigit():
            return "block", [int(parts[0])], None
 
        if parts[0] == "block":
            if len(parts) < 2:
                raise ValueError("Payload de bloco incompleto")
            ids = [int(tag_id) for tag_id in parts[1].split('-')]
            return "block", ids, None
 
        if parts[0] == "container":
            if len(parts) < 2 or not parts[1]:
                raise ValueError("Payload de container incompleto")
            return "container", [], parts[1]
 
        raise ValueError("Tipo de alinhamento inválido")
 
    def sched_callback(self, msg):
        if msg.target not in ACCEPTED_TARGETS or msg.uid == self.last_handled_uid:
            return
 
        # Interrompe a operação atual
        if self.is_active:
            self.stop_robot()
 
        try:
            mode, ids, color = self.parse_payload(msg.payload)
        except ValueError as e:
            rospy.logerr(f"Payload inválido para align_item: '{msg.payload}' ({e})")
            self.last_sched_uid = msg.uid
            self.cmd_target = msg.target
            self.send_feedback("FAIL")
            return
 
        self.mode = mode
        self.target_block_ids = ids
        self.target_color = color
        self.cmd_target = msg.target
        self.last_sched_uid = msg.uid
        self.last_handled_uid = msg.uid
        self.command_start_time = rospy.Time.now()
        self.max_search_time = msg.timeout if msg.timeout > 0 else self.max_search_time
        self.has_converged = False
        self.block_position = None
        self.block_stamp = None
        self.container_error = None
        self.container_stamp = None
        self.is_active = True
 
        if mode == "block":
            rospy.loginfo(f"Alinhamento ao bloco {self.target_block_ids} iniciado (uid={msg.uid}).")
        else:
            rospy.loginfo(f"Alinhamento ao container {self.target_color} iniciado (uid={msg.uid}).")
 
    def send_feedback(self, status):
        if self.last_sched_uid is None:
            return
 
        fb_msg = SchedulerResponse(
            uid=self.last_sched_uid,
            target=self.cmd_target or ACCEPTED_TARGETS[0],
            status=status
        )
 
        # Publica algumas vezes para garantir que o scheduler receba
        for _ in range(3):
            self.feedback_pub.publish(fb_msg)
            rospy.sleep(0.05)
 
        # Reseta o estado e espera o próximo comando
        self.stop_robot()
        self.is_active = False
        self.last_sched_uid = None
        # last_handled_uid é mantido de propósito: o mesmo UID não roda duas vezes
 
    # Detecções
    def tag_detections_callback(self, data):
        if not self.is_active or self.has_converged or self.mode != "block":
            return
 
        # Entre as tags-alvo visíveis, usa a mais próxima
        best = None
        for detection in data.detections:
            if detection.id[0] in self.target_block_ids:
                pos = detection.pose.pose.pose.position
                if best is None or pos.z < best.z:
                    best = pos
 
        if best is not None:
            self.block_position = best
            self.block_stamp = rospy.Time.now()
 
    def container_callback(self, msg):
        if not self.is_active or self.has_converged or self.mode != "container":
            return
 
        if msg.color != self.target_color:
            return
 
        self.container_error = (msg.position_x, msg.position_y)
        self.container_stamp = rospy.Time.now()
 
    def is_fresh(self, stamp):
        return stamp is not None and (rospy.Time.now() - stamp).to_sec() <= self.lost_timeout
 
    # Controle (Timer)

    def run_control_loop(self, event):
        if not self.is_active or self.has_converged:
            return
 
        if (rospy.Time.now() - self.command_start_time).to_sec() > self.max_search_time:
            rospy.logwarn(f"Timeout de {self.max_search_time}s excedido. Desistindo do alinhamento.")
            self.send_feedback("FAIL")
            return
 
        if self.mode == "block":
            if self.is_fresh(self.block_stamp):
                self.align_block(self.block_position)
            else:
                self.search_or_stop()
        elif self.mode == "container":
            if self.is_fresh(self.container_stamp):
                self.align_container(*self.container_error)
            else:
                self.search_or_stop()
 
    def search_or_stop(self):
        # Perdeu o alvo: para e espera nova leitura
        self.stop_robot()
        rospy.loginfo_throttle(5, "Alvo perdido. Parado e aguardando nova detecção.")
 
    def align_block(self, position):
        cmd_vel = Twist()
 
        adjusted_x = position.x - self.offset_x
        adjusted_z = position.z
 
        # Lateral (X da câmera -> -Y linear do robô)
        if abs(adjusted_x) > self.tol_x:
            cmd_vel.linear.y = -self.vel_linear if adjusted_x > 0 else self.vel_linear
            rospy.loginfo_throttle(
                0.5, f"AJUSTE LATERAL (X -> Y): Erro={adjusted_x:.4f}m, Vel={cmd_vel.linear.y:.2f}")
 
        # Profundidade (Z da câmera -> X linear do robô)
        elif abs(adjusted_z - self.target_z) > self.tol_z:
            cmd_vel.linear.x = self.vel_linear if adjusted_z > self.target_z else -self.vel_linear
            rospy.loginfo_throttle(
                0.5, f"AJUSTE PROFUNDIDADE (Z -> X): Dist={adjusted_z:.4f}m, Vel={cmd_vel.linear.x:.2f}")
 
        else:
            rospy.loginfo("Robô alinhado ao bloco (lateral e distância).")
            self.finish_ok()
            return
 
        self.vel_pub.publish(cmd_vel)
 
    def align_container(self, error_x, error_y):
        cmd_vel = Twist()
 
        # Lateral: container à direita do centro (erro > 0) -> anda para a direita (-Y)
        if abs(error_x) > self.tol_x_px:
            cmd_vel.linear.y = -self.vel_linear if error_x > 0 else self.vel_linear
            rospy.loginfo_throttle(
                0.5, f"AJUSTE LATERAL CONTAINER: Erro={error_x}px, Vel={cmd_vel.linear.y:.2f}")
 
        elif self.container_align_y and abs(error_y) > self.tol_y_px:
            direction = self.container_y_sign if error_y > 0 else -self.container_y_sign
            cmd_vel.linear.x = self.vel_linear * direction
            rospy.loginfo_throttle(
                0.5, f"AJUSTE FRONTAL CONTAINER: Erro={error_y}px, Vel={cmd_vel.linear.x:.2f}")
 
        else:
            rospy.loginfo(f"Robô alinhado ao container {self.target_color}.")
            self.finish_ok()
            return
 
        self.vel_pub.publish(cmd_vel)
 
    def finish_ok(self):
        self.stop_robot()
        self.has_converged = True
        self.send_feedback("OK")
 
    def stop_robot(self):
        self.vel_pub.publish(Twist())
 
 
if __name__ == '__main__':
    try:
        AlignItem()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
