#!/usr/bin/env python3
import rospy
import json
import threading
import paho.mqtt.client as mqtt
import math
from std_msgs.msg import Float32MultiArray
from robot_communication.msg import encoder_comm, velocity_comm, ultrasonic_comm # ultrasonic_comm é a mensagem de ultrassom

# --- Configurações MQTT ---
BROKER = "192.168.1.100"
PORT = 1883

# Tópicos de Movimento (ESP Frontal/Traseiro)
TOPIC_CMD_VEL   = "command/motors"
TOPIC_ENC_STATE = "state/encoders"

# Tópicos de Manipulação (ESP Manipulação)
TOPIC_CMD_MANIP   = "command/manipulator"
TOPIC_US_STATE    = "state/ultrassonics"

# Função auxiliar para verificação numérica
def _is_num(x):
    return x is not None and not math.isnan(x) and not math.isinf(x)


class MQTTComm:
    def __init__(self):
        rospy.init_node('mqtt_comm', anonymous=False)
        
        # --- Publishers ---
        self.pub_encoder    = rospy.Publisher('/encoder_data', encoder_comm, queue_size=10)
        self.pub_ultrasonic = rospy.Publisher('/ultrasonic_distances', ultrasonic_comm, queue_size=10)
        
        # --- Subscribers ---
        self.sub_velocity = rospy.Subscriber('/velocity_cmd', velocity_comm, self.cb_vel_control)
        self.sub_arm      = rospy.Subscriber('/arm_control', Float32MultiArray, self.cb_arm_control)
        self.sub_ee       = rospy.Subscriber('/end_effector_control', Float32MultiArray, self.cb_ee_control)

        # --- Cache de Dados Compartilhados ---
        self.enc_data = {'left_front': 0.0, 'right_front': 0.0, 'left_rear': 0.0, 'right_rear': 0.0}
        self.us_data = {'front_left': 0.0, 'front_right': 0.0, 'rear_left': 0.0} # Apenas 3 US no ESP de Manipulação
        self.data_lock = threading.Lock() 

        # Cache para o pacote completo de manipulação (armazenado antes de enviar)
        self.cached_manip_cmd = {'arm': 0.0, 'base': 0.0, 'wrist': 0.0, 'grip': 0.0}
        
        # --- Cliente MQTT ---
        self.client = mqtt.Client(client_id="", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        try:
            self.client.connect(BROKER, PORT, 60)
        except Exception as e:
            rospy.logerr(f"Falha ao conectar no broker MQTT: {e}")
            exit(1)

        self.mqtt_thread = threading.Thread(target=self.client.loop_forever, daemon=True)
        self.mqtt_thread.start()

        # Timer: Publica o estado consolidado (Encoder + US) no ROS a 50Hz
        rospy.Timer(rospy.Duration(1.0/50.0), self.publish_state_ros)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            rospy.loginfo("MQTT Conectado! Assinando tópicos de estado...")
            # Assina ambos os tópicos de estado: Encoders (Movimento) e US (Manipulação)
            client.subscribe(TOPIC_ENC_STATE, qos=0)
            client.subscribe(TOPIC_US_STATE, qos=0)
        else:
            rospy.logerr(f"Conexão MQTT falhou com código {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            with self.data_lock:
                if msg.topic == TOPIC_ENC_STATE:
                    # Recebe de ESP Frontal/Traseiro
                    for key in self.enc_data.keys():
                        if key in payload:
                            self.enc_data[key] = float(payload[key])
                            
                elif msg.topic == TOPIC_US_STATE:
                    # Recebe do ESP Manipulação
                    for key in self.us_data.keys():
                        if key in payload:
                            self.us_data[key] = float(payload[key])

        except json.JSONDecodeError:
            rospy.logwarn_throttle(5, f"Erro ao decodificar JSON em {msg.topic}")
        except Exception as e:
            rospy.logerr(f"Erro processando mensagem MQTT: {e}")

    # =========================================================================
    # ENVIOS (ROS -> MQTT)
    # =========================================================================
    
    def cb_vel_control(self, msg: velocity_comm):
        try:
            command_payload = {
                "left_front":  msg.front_left,
                "right_front": msg.front_right,
                "left_rear":   msg.rear_left,
                "right_rear":  msg.rear_right
            }
            self.client.publish(TOPIC_CMD_VEL, json.dumps(command_payload), qos=0)
        except Exception as e:
            rospy.logerr(f"Erro ao publicar comando de velocidade: {e}")

    def _publish_manip_command(self):
        try:
            # O ESP de Manipulação espera arm, base, wrist, grip (4 valores)
            payload = {
                "arm": self.cached_manip_cmd['arm'],
                "base": self.cached_manip_cmd['base'],
                "wrist": self.cached_manip_cmd['wrist'],
                "grip": self.cached_manip_cmd['grip']
            }
            # O cJSON no firmware do ESP de Manipulação lê diretamente esses campos.
            self.client.publish(TOPIC_CMD_MANIP, json.dumps(payload), qos=0)
        except Exception as e:
            rospy.logerr(f"Erro ao publicar comando de manipulação: {e}")

    def cb_arm_control(self, msg: Float32MultiArray):
        data = msg.data or []
        
        # O ESP de Manipulação espera setpoints de passo/valor.
        if len(data) > 0 and _is_num(data[0]):
            self.cached_manip_cmd['base'] = data[0]
        if len(data) > 1 and _is_num(data[1]):
            self.cached_manip_cmd['arm'] = data[1]

        self._publish_manip_command()

    def cb_ee_control(self, msg: Float32MultiArray):
        """Atualiza o cache de setpoints de Servo e envia o pacote completo."""
        data = msg.data or []
        
        # Clamping de segurança antes de atualizar o cache
        if len(data) > 0 and _is_num(data[0]):
            self.cached_manip_cmd['wrist'] = max(0.0, min(180.0, float(data[0])))
        if len(data) > 1 and _is_num(data[1]):
            self.cached_manip_cmd['grip'] = max(0.0, min(180.0, float(data[1])))
        
        self._publish_manip_command()

    # =========================================================================
    # PUBLICAÇÃO UNIFICADA NO ROS (MQTT -> ROS)
    # =========================================================================

    def publish_state_ros(self, event):
        with self.data_lock:
            # Encoders
            enc_msg = encoder_comm()
            enc_msg.front_left  = self.enc_data['left_front']
            enc_msg.front_right = self.enc_data['right_front']
            enc_msg.rear_left   = self.enc_data['left_rear']
            enc_msg.rear_right  = self.enc_data['right_rear']
            self.pub_encoder.publish(enc_msg)

            # Ultrassônicos
            us_msg = ultrasonic_comm()
            us_msg.front_left   = self.us_data['front_left']
            us_msg.front_right  = self.us_data['front_right']
            us_msg.rear_left    = self.us_data['rear_left']
            # Sensores inexistentes são zerados
            us_msg.rear_right   = 0.0 
            us_msg.back         = 0.0
            self.pub_ultrasonic.publish(us_msg)

    def shutdown(self):
        rospy.loginfo("Ponte MQTT encerrada.")
        self.client.disconnect()
        self.client.loop_stop()

if __name__ == "__main__":
    try:
        bridge = MQTTComm()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        if 'bridge' in locals():
            bridge.shutdown()