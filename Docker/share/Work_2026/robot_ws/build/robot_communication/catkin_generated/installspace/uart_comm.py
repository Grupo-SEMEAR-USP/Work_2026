#!/usr/bin/env python3
import rospy
import serial
import struct
import threading
import math
from std_msgs.msg import Float32MultiArray
from robot_communication.msg import encoder_comm, velocity_comm, ultrasonic_comm

# --- Configuração das Portas ---
PORT_FRONT     = "/dev/esp_front"     # Encoder/Velocidade Roda Frontal
PORT_REAR      = "/dev/esp_rear"      # Encoder/Velocidade Roda Traseira
PORT_MANIP     = "/dev/esp_manip"     # Ultrassom/Comando Manipulador
BAUD_RATE      = 115200

# --- Definições do Protocolo ---
FRAME_SOF = 0xAA
FRAME_EOF = 0xBB

# Pacote Encoder/Velocidade (2 floats - 8 bytes)
ENC_PAYLOAD_SIZE = 8 
ENC_FRAME_SIZE   = 1 + ENC_PAYLOAD_SIZE + 1 + 1  # 11 bytes

# Pacote Ultrassom (3 floats - 12 bytes)
US_PAYLOAD_SIZE  = 12 
US_FRAME_SIZE    = 1 + US_PAYLOAD_SIZE + 1 + 1   # 15 bytes

# Pacote Comando Manipulação (4 floats - 16 bytes)
CMD_PAYLOAD_SIZE = 16 
CMD_FRAME_SIZE   = 1 + CMD_PAYLOAD_SIZE + 1 + 1  # 19 bytes

# Variável para verificação numérica
def _is_num(x):
    return x is not None and not math.isnan(x) and not math.isinf(x)


class UARTBridge:
    def __init__(self):
        rospy.init_node('uart_bridge', anonymous=False)
        
        # --- Publishers ---
        self.pub_encoder    = rospy.Publisher('/encoder_data', encoder_comm, queue_size=10)
        self.pub_ultrasonic = rospy.Publisher('/ultrasonic_distances', ultrasonic_comm, queue_size=10)
        
        # --- Subscribers ---
        self.sub_velocity = rospy.Subscriber('/velocity_cmd', velocity_comm, self.cb_vel_control)
        self.sub_arm      = rospy.Subscriber('/arm_control', Float32MultiArray, self.cb_arm_control)
        self.sub_ee       = rospy.Subscriber('/end_effector_control', Float32MultiArray, self.cb_ee_control)

        # --- Estado Interno e Cache ---
        self.enc_data = {'front_left': 0.0, 'front_right': 0.0, 'rear_left': 0.0, 'rear_right': 0.0}
        self.us_data = {'front_left': 0.0, 'front_right': 0.0, 'rear_left': 0.0}
        
        # Cache para o pacote COMPLETO de manipulação (4 floats - 16 bytes)
        self.cached_manip_cmd = {'arm': 0.0, 'base': 0.0, 'wrist': 0.0, 'grip': 0.0}

        self.data_lock = threading.Lock() # Mutex para dados compartilhados

        # --- Inicialização das Portas Seriais ---
        self.serial_front = self.open_serial(PORT_FRONT)
        self.serial_rear  = self.open_serial(PORT_REAR)
        self.serial_manip = self.open_serial(PORT_MANIP)

        if not all([self.serial_front, self.serial_rear, self.serial_manip]):
            rospy.logerr("Impossível iniciar sem as 3 ESPs conectadas.")
            # A falha aqui pode ser ajustada para permitir que o nó ROS continue, mas avise.
            exit(1)

        self.running = True

        # --- Threads de Leitura ---
        self.thread_front = threading.Thread(target=self.read_loop, args=(self.serial_front, 'FRONT', 'ENC'), daemon=True)
        self.thread_rear  = threading.Thread(target=self.read_loop, args=(self.serial_rear,  'REAR', 'ENC'), daemon=True)
        self.thread_manip = threading.Thread(target=self.read_loop, args=(self.serial_manip, 'MANIP', 'US'), daemon=True)
        
        self.thread_front.start()
        self.thread_rear.start()
        self.thread_manip.start()

        # Timer para publicar dados unificados (50 Hz)
        rospy.Timer(rospy.Duration(1.0/50.0), self.publish_unified_data)
        
    def open_serial(self, port_name):
        try:
            ser = serial.Serial(port=port_name, baudrate=BAUD_RATE, timeout=0.1)
            rospy.loginfo(f"Conectado: {port_name}")
            return ser
        except serial.SerialException as e:
            rospy.logerr(f"Falha ao abrir {port_name}: {e}")
            return None

    def calculate_checksum(self, data_bytes):
        """Calcula o checksum somando todos os bytes do payload."""
        return sum(data_bytes) & 0xFF

    # =========================================================================
    # ENVIOS (ROS -> ESP32)
    # =========================================================================

    # Envio de Velocidade (2 floats, 8 bytes payload) ---
    def send_vel_packet(self, serial_obj, val1, val2):
        if serial_obj is None or not serial_obj.is_open:
            return

        try:
            payload = struct.pack('<ff', val1, val2) # 2 floats
            checksum = self.calculate_checksum(payload)
            frame = struct.pack('B', FRAME_SOF) + payload + struct.pack('B', checksum) + struct.pack('B', FRAME_EOF)
            serial_obj.write(frame)
        except Exception as e:
            rospy.logwarn(f"Erro escrita serial (Vel): {e}")

    def cb_vel_control(self, msg):
        self.send_vel_packet(self.serial_front, msg.front_left, msg.front_right)
        self.send_vel_packet(self.serial_rear, msg.rear_left, msg.rear_right)

    # --- Envio de Manipulação (4 floats, 16 bytes payload) ---
    def send_manip_command(self, val_arm, val_base, val_wrist, val_grip):
        if self.serial_manip is None or not self.serial_manip.is_open:
            rospy.logwarn_throttle(2, "Aguardando conexão com esp_manipulator.")
            return

        try:
            # Pacote de 16 bytes (arm, base, wrist, grip)
            payload = struct.pack('<ffff', val_arm, val_base, val_wrist, val_grip)
            checksum = self.calculate_checksum(payload)
            
            frame = struct.pack('B', FRAME_SOF) + payload + struct.pack('B', checksum) + struct.pack('B', FRAME_EOF)
            self.serial_manip.write(frame)
        except Exception as e:
            rospy.logwarn(f"Erro escrita serial (Manip): {e}")

    def cb_arm_control(self, msg: Float32MultiArray):
        data = msg.data or [0.0, 0.0]
        
        # A ESP32 de manipulação espera setpoints de passo/valor.
        self.cached_manip_cmd['base'] = data[0] if len(data) > 0 and _is_num(data[0]) else self.cached_manip_cmd['base']
        self.cached_manip_cmd['arm']  = data[1] if len(data) > 1 and _is_num(data[1]) else self.cached_manip_cmd['arm']

        self._flush_manip_command()

    def cb_ee_control(self, msg: Float32MultiArray):
        data = msg.data or [0.0, 0.0]

        # Clamping de segurança antes do envio
        wrist = data[0] if len(data) > 0 and _is_num(data[0]) else self.cached_manip_cmd['wrist']
        grip  = data[1] if len(data) > 1 and _is_num(data[1]) else self.cached_manip_cmd['grip']
        
        self.cached_manip_cmd['wrist'] = max(0.0, min(180.0, float(wrist)))
        self.cached_manip_cmd['grip']  = max(0.0, min(180.0, float(grip)))
        
        self._flush_manip_command()
        
    def _flush_manip_command(self):
        self.send_manip_command(
            self.cached_manip_cmd['arm'], 
            self.cached_manip_cmd['base'], 
            self.cached_manip_cmd['wrist'], 
            self.cached_manip_cmd['grip']
        )

    # =========================================================================
    # LEITURA (ESP32 -> ROS)
    # =========================================================================
    def read_loop(self, serial_obj, location, data_type):
        expected_sof = struct.pack('B', FRAME_SOF)
        
        # Define o protocolo esperado para esta porta/thread
        if data_type == 'ENC':
            payload_size = ENC_PAYLOAD_SIZE  # 8 bytes (2 floats)
            frame_size   = ENC_FRAME_SIZE    # 11 bytes
            format_str   = '<ff'
        elif data_type == 'US':
            payload_size = US_PAYLOAD_SIZE   # 12 bytes (3 floats)
            frame_size   = US_FRAME_SIZE     # 15 bytes
            format_str   = '<fff' # 3 floats
        else:
            return

        while self.running and not rospy.is_shutdown():
            try:
                if serial_obj.in_waiting > 0:
                    byte = serial_obj.read(1)
                    
                    if byte == expected_sof:
                        rest = serial_obj.read(frame_size - 1)
                        
                        if len(rest) == (frame_size - 1):
                            payload = rest[0:payload_size]
                            received_chk = rest[payload_size:payload_size+1]
                            received_eof = rest[payload_size+1:payload_size+2]

                            # Validação EOF
                            if received_eof != struct.pack('B', FRAME_EOF):
                                continue 

                            # Validação Checksum
                            calc_chk = self.calculate_checksum(payload)
                            if received_chk != struct.pack('B', calc_chk):
                                rospy.logwarn(f"Checksum error em {location} ({data_type})")
                                continue

                            # Desempacota
                            values = struct.unpack(format_str, payload)

                            # Atualiza a memória compartilhada com segurança
                            with self.data_lock:
                                if data_type == 'ENC':
                                    if location == 'FRONT':
                                        self.enc_data['front_left'], self.enc_data['front_right'] = values
                                    elif location == 'REAR':
                                        self.enc_data['rear_left'], self.enc_data['rear_right'] = values
                                
                                elif data_type == 'US':
                                    self.us_data['front_left'], self.us_data['front_right'], self.us_data['rear_left'] = values
                                    
            except Exception as e:
                rospy.logerr(f"Erro leitura {location} ({data_type}): {e}")
                rospy.sleep(0.01)

    # --- Publicação Unificada (50 Hz Timer) ---
    def publish_unified_data(self, event):
        with self.data_lock:
            # Encoders
            enc_msg = encoder_comm()
            enc_msg.front_left  = self.enc_data['front_left']
            enc_msg.front_right = self.enc_data['front_right']
            enc_msg.rear_left   = self.enc_data['rear_left']
            enc_msg.rear_right  = self.enc_data['rear_right']
            self.pub_encoder.publish(enc_msg)

            # Ultrassônicos
            us_msg = ultrasonic_comm()
            us_msg.front_left   = self.us_data['front_left']
            us_msg.front_right  = self.us_data['front_right']
            us_msg.rear_left    = self.us_data['rear_left']
            us_msg.rear_right   = 0.0 # O ESP de manipulação só envia 3 sensores
            us_msg.back         = 0.0
            self.pub_ultrasonic.publish(us_msg)

    def shutdown(self):
        rospy.loginfo("Encerrando conexões seriais.")
        self.running = False
        if self.serial_front and self.serial_front.is_open:
            self.serial_front.close()
        if self.serial_rear and self.serial_rear.is_open:
            self.serial_rear.close()
        if self.serial_manip and self.serial_manip.is_open:
            self.serial_manip.close()

if __name__ == "__main__":
    try:
        bridge = UARTBridge()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        if 'bridge' in locals():
            bridge.shutdown()