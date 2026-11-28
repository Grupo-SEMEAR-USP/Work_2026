#!/usr/bin/env python3
import rospy
from std_msgs.msg import String, Int32
from robot_communication.msg import SchedulerCommand, SchedulerResponse, AprilTagDetectionArray, ultrasonic_comm

'''
Script para procurar o bloco com zig zag: para logo após identificar.
Ao encontrar um dos IDs, envia o comando para o align_block (com o mesmo uid do scheduler),
e é o align_block quem devolve o feedback para o scheduler.
'''

class ZigZagSearch:
    def __init__(self):
        rospy.init_node('search_block', anonymous=True)
        self.node_name = "search_block"
        self.aruco_reference_ids = None
        self.last_uid = None
        self.distance_threshold = 10  # 10 cm
        self.center_tolerance = 0.06  # Tolerância de 10% em relação ao centro da imagem

        self.pub_move_time = rospy.Publisher('move_time', String, queue_size=10)
        self.pub_feedback = rospy.Publisher('/scheduler/feedback', SchedulerResponse, queue_size=10)
        self.pub_found_block = rospy.Publisher('/found_block', Int32, queue_size=10)
        
        self.sub_search = rospy.Subscriber('/scheduler/commands', SchedulerCommand, self.sched_cb)
        self.sub_tag_detections = rospy.Subscriber('/tag_detections', AprilTagDetectionArray, self.tag_detection_callback)
        self.sub_ultrasound_right = rospy.Subscriber('/ultrasonic_distances', ultrasonic_comm, self.ultrasound_callback)

        # Comando para o align_block (search_block faz o papel do scheduler)
        self.pub_align_cmd = rospy.Publisher('/scheduler/commands', SchedulerCommand, queue_size=10)

        self.rate = rospy.Rate(50)
        self.movement_active = False
        self.target_found = False
        self.current_distance = float('inf')  # Inicializa com um valor alto
        self.direction = None
        self.inverse_direction = None
        self.timeout = None
        self.last_time = None
        self.fb = None
        self.found_id = None
    
    def sched_cb(self, msg):
        if msg.target != 'search_block' or msg.uid == self.last_uid:
            return
        
        try:
            # O payload é o nome do bloco, que pode não ser um ID numérico.
            # A lógica de qual ID procurar precisaria ser mapeada aqui.
            # Por simplicidade, vamos assumir que o payload é o ID por enquanto.
            payload = msg.payload.split(',')
            self.aruco_reference_ids = [
                int(tag_id) for tag_id in payload[0].split('-')
            ]
            # self.aruco_reference_ids = int(payload[0])
            self.direction = payload[1]
            if self.direction == "direita":
                self.inverse_direction = "esquerda"
            elif self.direction == "esquerda":
                self.inverse_direction = "direita"

            # self.target_block_id = int(block_id_str) # Mapear nome para ID se necessário
            rospy.loginfo(f"Iniciando busca pelos blocos '{self.aruco_reference_ids}' pela {self.direction} (uid={msg.uid})")
            
            self.last_uid = msg.uid
            self.found_id = None
            self.target_found = False
            self.movement_active = True
            self.timeout = msg.timeout
            self.last_time = rospy.Time.now()
            # A busca em zigue-zague é bloqueante, então a executamos aqui
            self.perform_zigzag()
            self.movement_active = False

            if self.found_id is not None:
                # Achou: manda o align procurar exatamente esse ID, com o mesmo uid do scheduler,
                # para que o feedback do align libere a espera do scheduler.
                elapsed = (rospy.Time.now() - self.last_time).to_sec()
                self.send_align_command(self.found_id, max(self.timeout - elapsed, 1.0))
            else:
                fb_msg = SchedulerResponse(self.last_uid, self.node_name, "SKIP")
                self.pub_feedback.publish(fb_msg)
            
        except ValueError:
            rospy.logerr(f"Payload inválido para search_block: {msg.payload}")
            fb_msg = SchedulerResponse(self.last_uid, self.node_name, "FAIL")
            self.pub_feedback.publish(fb_msg)

    def send_align_command(self, block_id, timeout):
        cmd = SchedulerCommand()
        cmd.uid = self.last_uid
        cmd.target = "align_block"
        cmd.payload = str(block_id)
        cmd.need_ack = True
        cmd.timeout = float(timeout)

        rospy.loginfo(f"[search_block] → align_block id={block_id} uid={cmd.uid} timeout={timeout:.1f}s")
        for _ in range(3):
            self.pub_align_cmd.publish(cmd)
            rospy.sleep(0.05)

    def ultrasound_callback(self, msg):
        self.current_distance = msg.us_left_1

    def perform_zigzag(self):
        # rospy.loginfo(f"Primeiro:{self.current_distance > self.distance_threshold}")
        # rospy.loginfo(f"Segundo:{self.movement_active}")
        # rospy.loginfo(f"Terceiro:{(rospy.Time.now() - self.last_time).to_sec() < self.timeout}")
        # rospy.loginfo(f"Atual: {self.current_distance} || Threshold: {self.distance_threshold}")
        rospy.sleep(2)
        # while self.current_distance > self.distance_threshold and self.movement_active and (rospy.Time.now() - self.last_time).to_sec() < self.timeout:
        while self.movement_active and (rospy.Time.now() - self.last_time).to_sec() < self.timeout:
            rospy.loginfo("Executando movimento de zigue-zague...")
                
            if not self.movement_active:
                self.fb = True
                return

            # rospy.loginfo("Movendo para o lado por 2.0 segundos.")
            self.pub_move_time.publish(self.direction+",0.7")
            self.pub_move_time.publish("parar,0.1")
            rospy.sleep(2)
            # rospy.sleep(2.6)
            
            if not self.movement_active:
                self.fb = True
                return

            # rospy.loginfo("Movendo para trás por 1.1 segundos.")
            self.pub_move_time.publish("tras,0.7")
            self.pub_move_time.publish("parar,0.1")
            rospy.sleep(2)

            if not self.movement_active:
                self.fb = True
                return

            # rospy.loginfo("Movendo para o lado por 2.0 segundos.")
            self.pub_move_time.publish(self.direction+",0.7")
            self.pub_move_time.publish("parar,0.1")
            rospy.sleep(2)

            if not self.movement_active:
                self.fb = True
                return

            # rospy.loginfo("Movendo para a frente por 1.1 segundos.")
            self.pub_move_time.publish("frente,0.7")
            self.pub_move_time.publish("parar,0.1")
            rospy.sleep(2)

            if not self.movement_active:
                self.fb = True
                return
    

    def tag_detection_callback(self, msg):
        if not self.movement_active or self.target_found:
            return
        
        for detection in msg.detections:
            tag_id = detection.id[0]
            rospy.loginfo(f"Achou id. ID: {tag_id}.")
            if tag_id in self.aruco_reference_ids:
                self.movement_active = False
                self.found_id = tag_id
                self.aruco_reference_ids = []
                # Calcula a posição do bloco em relação ao centro da imagem
                center_x = detection.pose.pose.pose.position.x
                center_y = detection.pose.pose.pose.position.y
                if abs(center_x) < self.center_tolerance and abs(center_y) < self.center_tolerance:
                    # rospy.loginfo(f"Bloco detectado no centro com ID {tag_id}.")
                    rospy.loginfo(f"Bloco detectado com ID {tag_id}.")
                    self.pub_found_block.publish(tag_id)
                    self.target_found = True


                else:
                    # rospy.loginfo(f"Bloco detectado fora do centro com ID {tag_id}. Coordenadas: ({center_x}, {center_y})")
                    rospy.loginfo(f"Bloco detectado com ID {tag_id}.")

    def perform_reverse_zigzag(self):
        try:
            rospy.loginfo("Executando movimento de zigue-zague reverso...")

            for cycle in range(3):
                rospy.loginfo(f"Executando ciclo inverso {cycle + 1}/3")

                if not self.movement_active:
                    return

                rospy.loginfo("Movendo para o lado contrário por 2.0 segundos.")
                self.pub_move_time.publish(self.inverse_direction+",2.0")
                rospy.sleep(2.3)

                if not self.movement_active:
                    return

                rospy.loginfo("Movendo para trás por 1.1 segundos.")
                self.pub_move_time.publish("tras,1.1")
                rospy.sleep(1.4)

                if not self.movement_active:
                    return

                rospy.loginfo("Movendo para a esquerda por 2.0 segundos.")
                self.pub_move_time.publish(self.inverse_direction+",2.0")
                rospy.sleep(2.3)

                if not self.movement_active:
                    return

                rospy.loginfo("Movendo para a frente por 1.1 segundos.")
                self.pub_move_time.publish("frente,1.1")
                rospy.sleep(1.4)

                if cycle < 2:
                    rospy.loginfo("Movendo para a esquerda por 2.0 segundos.")
                    self.pub_move_time.publish(self.inverse_direction+",2.0")
                    rospy.sleep(2.3)

            rospy.loginfo("Movimento de zigue-zague reverso completo.")
            if self.movement_active:
                self.pub_feedback.publish(1)

        except Exception as e:
            rospy.logerr("Erro durante o movimento inverso: %s", str(e))
            self.pub_feedback.publish(0)
            self.movement_active = False
            
    def run(self):
        self.rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            self.rate.sleep()

if __name__ == '__main__':
    
    try:
        zigzag = ZigZagSearch()
        zigzag.run()
    except rospy.ROSInterruptException:
        pass