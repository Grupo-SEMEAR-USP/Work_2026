import rospy
from std_msgs.msg import String, Int32, Float32
from sensor_msgs.msg import Range
from robot_communication.msg import AprilTagDetection, AprilTagDetectionArray
from robot_communication.msg import ultrasonic_comm, container_comm
from robot_communication.msg import SchedulerCommand, SchedulerResponse

class ZigZagSearch:
    def __init__(self):
        rospy.init_node('search_item', anonymous=True)
        self.node_name = "search_item"
        self.aruco_reference_id = [] #referente as tags ex: 1-2-3
        self.aruco_reference_color = None
        self.last_uid = None
        self.distance_threshold = 10  # 10 cm  PRECISA TESTAR ISSOOOO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        self.center_tolerance = 0.06  # Tolerância de 10% em relação ao centro da imagem  PRECISA TESTAR ISSOOOO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        self.distance_container_threshold = 0.15  #15cm PRECISA TESTAR ISSOOOO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        self.pub_move_time = rospy.Publisher('move_time', String, queue_size=10)
        self.pub_feedback = rospy.Publisher('/scheduler/feedback', SchedulerResponse, queue_size=10)
        
        self.sub_search = rospy.Subscriber('/scheduler/commands', SchedulerCommand, self.sched_cb)
        self.sub_tag_detections = rospy.Subscriber('/tag_detections', AprilTagDetectionArray, self.tag_detection_callback)
        self.sub_ultrasound = rospy.Subscriber('/ultrasonic_distances', ultrasonic_comm, self.ultrasound_callback)
        self.sub_color_detections = rospy.Subscriber('/container_info', container_comm, self.color_detection_callback)

        self.rate = rospy.Rate(50)
        self.movement_active = False
        self.target_found = False
        self.current_distance = float('inf')  # Inicializa com um valor alto
        self.direction = None
        self.inverse_direction = None
        self.timeout = None
        self.last_time = None
        self.fb = None
        self.otarget = None
    
    def sched_cb(self, msg):
        if msg.target != 'search_item' or msg.uid == self.last_uid:
            return

        self.target_found = False
        self.fb = False
        self.movement_active = True
        
        try:
            # O payload é o nome do bloco, que pode não ser um ID numérico.
            # A lógica de qual ID procurar precisaria ser mapeada aqui.
            # Por simplicidade, vamos assumir que o payload é o ID por enquanto.
            payload = msg.payload.split(',')
            self.otarget = payload[0]
            rospy.loginfo(f"Payload recebido: {payload}. Tipo de busca: {self.otarget}")
            if payload[0] == "block":
                if len(payload) < 2:
                    raise ValueError("Payload de bloco incompleto")

                self.aruco_reference_id = [
                    int(tag_id) for tag_id in payload[1].split('-')
                ]

            elif payload[0] == "container":
                if len(payload) < 3:
                    raise ValueError("Payload de container incompleto")

                self.aruco_reference_color = payload[1]
                self.direction = payload[2]

                if self.direction == "direita":
                    self.inverse_direction = "esquerda"
                elif self.direction == "esquerda":
                    self.inverse_direction = "direita"
                else:
                    raise ValueError("Direção inválida")

            else:
                raise ValueError("Tipo de busca inválido")
                        # self.target_block_id = int(block_id_str) # Mapear nome para ID se necessário
            rospy.loginfo(f"Iniciando busca (uid={msg.uid})")
            
            self.last_uid = msg.uid
            self.movement_active = True
            self.timeout = msg.timeout
            self.last_time = rospy.Time.now()
            self.perform_zigzag()
            # A busca em zigue-zague é bloqueante, então a executamos aqui
            if self.fb:
                fb_msg = SchedulerResponse(self.last_uid, self.node_name, "OK")
            else:
                fb_msg = SchedulerResponse(self.last_uid, self.node_name, "SKIP")
            self.pub_feedback.publish(fb_msg)
            
        except ValueError:
            rospy.logerr(f"Payload inválido para search_item: {msg.payload}")
            fb_msg = SchedulerResponse(self.last_uid, self.node_name, "FAIL")
            self.pub_feedback.publish(fb_msg)

    def ultrasound_callback(self, msg):
        self.current_distance = msg.rear_left

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
        if self.otarget != "block":
            return

        # Não processa se a busca não estiver ativa
        if not self.movement_active:
            return

        # Não processa se já encontrou o alvo
        if self.target_found:
            return
            
        for detection in msg.detections:
            tag_id = detection.id[0]
            rospy.loginfo(f"Achou id. ID: {tag_id}.")
            if tag_id in self.aruco_reference_id:
                self.movement_active = False
                self.aruco_reference_id = []
                # Calcula a posição do bloco em relação ao centro da imagem
                center_x = detection.pose.pose.pose.position.x
                center_y = detection.pose.pose.pose.position.y
                if abs(center_x) < self.center_tolerance and abs(center_y) < self.center_tolerance:
                    # rospy.loginfo(f"Bloco detectado no centro com ID {tag_id}.")
                    rospy.loginfo(f"Bloco detectado com ID {tag_id}.")
                    # self.pub_found_block.publish(tag_id)
                    self.target_found = True
                else:
                    # rospy.loginfo(f"Bloco detectado fora do centro com ID {tag_id}. Coordenadas: ({center_x}, {center_y})")
                    rospy.loginfo(f"Bloco detectado com ID {tag_id}.")

    def color_detection_callback(self, msg):
        if self.otarget != "container":
                    return
        
        # Não processa se a busca não estiver ativa
        if not self.movement_active:
            return

        # Não processa se já encontrou o alvo
        if self.target_found:
            return

        rospy.loginfo(f"Container detectado com cor {self.aruco_reference_color}.")
        if msg.color == self.aruco_reference_color:
            self.movement_active = False
            self.aruco_reference_color = None

            deslocamento_x = msg.position_x
            deslocamento_y = msg.position_y    

            #if abs(deslocamento_x) < self.distance_container_threshold and abs(deslocamento_y) < self.distance_container_threshold:
            #    rospy.loginfo(f"Container detectado com cor {msg.color}.")
            #    self.target_found = True
            #else:
            rospy.loginfo(f"Container detectado com cor {msg.color}.")
            self.target_found = True

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
                self.pub_feedback.publish(self.last_uid, self.node_name, "OK")

        except Exception as e:
            rospy.logerr("Erro durante o movimento inverso: %s", str(e))
            self.pub_feedback.publish(self.last_uid, self.node_name, "FAIL")
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