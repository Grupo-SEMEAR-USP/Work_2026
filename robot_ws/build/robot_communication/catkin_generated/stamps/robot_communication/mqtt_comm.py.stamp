#!/usr/bin/env python3
"""Bridge ROS Noetic <-> MQTT para esp_left, esp_right e esp_center.

ROS existentes:
    /velocity_cmd           robot_communication/velocity_comm
    /arm_control            std_msgs/Float32MultiArray: [base_deg, elevator_cm]
    /end_effector_control   std_msgs/Float32MultiArray: [wrist_deg, gripper_deg]
    /encoder_data           robot_communication/encoder_comm
    /ultrasonic_distances   robot_communication/ultrasonic_comm (legado)

ROS adicionais (sem criar mensagens customizadas):
    /ultrasonic_distances_6 std_msgs/Float32MultiArray:
        [us_esq_1, us_esq_2, us_dir_1, us_dir_2, us_frt_1, us_trs_1] (cm)
    /encoder_ticks          std_msgs/Int32MultiArray: [LF, RF, LR, RR]
    /manipulator_state      std_msgs/Float32MultiArray:
        [base_angle_deg, base_angle_rad, upper_limit_active, encoder_valid]

Se ultrasonic_comm.msg for atualizado com os seis campos us_*, o bridge
preenche-os diretamente. Caso contrario, usa o mapeamento legado documentado.
"""

import json
import math
import threading
import time

import paho.mqtt.client as mqtt
import rospy
from std_msgs.msg import Float32MultiArray, Int32MultiArray
from robot_communication.msg import encoder_comm, velocity_comm, ultrasonic_comm

BROKER_DEFAULT = "192.168.1.100"
TOPIC_ULTRASONIC = "state/ultrasonic"           # esp_left
TOPIC_VELOCITY = "command/velocity"             # esp_right
TOPIC_ENCODERS = "state/encoders"               # esp_right
TOPIC_MOTORS = "command/motors"                 # esp_center
TOPIC_MANIPULATOR = "state/manipulator"         # esp_center

WHEEL_KEYS = ("left_front", "right_front", "left_rear", "right_rear")
US_KEYS = ("us_esq_1", "us_esq_2", "us_dir_1", "us_dir_2", "us_frt_1", "us_trs_1")

MASK_ELEVATOR = 1
MASK_BASE = 2
MASK_WRIST = 4
MASK_GRIPPER = 8


def finite_number(value):
    """Aceita numeros reais finitos, mas nao bool, string, NaN ou infinito."""
    return (isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value)))


def normal_us(value):
    """O JSON da ESP left usa null para uma medicao indisponivel."""
    if value is None:
        return float("nan")
    if not finite_number(value):
        raise ValueError("distancia invalida")
    return float(value)


def put_ultrasonic_message(msg, values):
    """Suporta ultrasonic_comm atualizado (6 campos) ou o antigo (5)."""
    if all(hasattr(msg, name) for name in US_KEYS):
        for key, value in zip(US_KEYS, values):
            setattr(msg, key, value)
        return

    # Compatibilidade PROVISORIA com a mensagem ROS antiga de 5 campos.
    # Assume sensor lateral 1 proximo da frente e sensor lateral 2 atras.
    # Nao existe campo legado para o ultrassonico frontal: usar topico _6.
    mapping = {
        "front_left": 0,  # us_esq_1
        "rear_left": 1,   # us_esq_2
        "front_right": 2, # us_dir_1
        "rear_right": 3,  # us_dir_2
        "back": 5,        # us_trs_1
    }
    for attr, index in mapping.items():
        if hasattr(msg, attr):
            setattr(msg, attr, values[index])


class MQTTBridge:
    def __init__(self):
        rospy.init_node("mqtt_bridge", anonymous=False)
        self.broker = rospy.get_param("~broker_host", BROKER_DEFAULT)
        self.port = int(rospy.get_param("~broker_port", 1883))
        self.ros_rate = float(rospy.get_param("~publish_rate_hz", 50.0))
        self.velocity_rate = float(rospy.get_param("~velocity_rate_hz", 20.0))
        self.command_timeout = float(rospy.get_param("~command_timeout_s", 0.25))
        self.state_timeout = float(rospy.get_param("~state_timeout_s", 1.0))
        if min(self.ros_rate, self.velocity_rate, self.command_timeout,
               self.state_timeout) <= 0:
            raise ValueError("Taxas e timeouts devem ser positivos")

        self.lock = threading.Lock()
        self.manip_tx_lock = threading.Lock()
        self.connected = False
        self.last_velocity = None
        self.velocity = (0.0,) * 4
        self.sequence = time.time_ns() & 0xFFFF
        self.enc = None
        self.ticks = None
        self.us = None
        self.manip = None
        self.received_at = {}

        self.pub_enc = rospy.Publisher("/encoder_data", encoder_comm, queue_size=10)
        self.pub_us = rospy.Publisher("/ultrasonic_distances", ultrasonic_comm, queue_size=10)
        self.pub_us6 = rospy.Publisher("/ultrasonic_distances_6", Float32MultiArray, queue_size=10)
        self.pub_ticks = rospy.Publisher("/encoder_ticks", Int32MultiArray, queue_size=10)
        self.pub_manip = rospy.Publisher("/manipulator_state", Float32MultiArray, queue_size=10)

        # Paho 1.x (ROS Noetic) e Paho 2.x: selecionar callbacks VERSION1,
        # quando disponibilizados, para manter a assinatura (client,userdata,flags,rc).
        kwargs = {"client_id": "ros_mqtt_bridge", "protocol": mqtt.MQTTv311}
        if hasattr(mqtt, "CallbackAPIVersion"):
            kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION1
        self.client = mqtt.Client(**kwargs)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.connect_async(self.broker, self.port, keepalive=30)
        self.client.loop_start()

        self.sub_vel = rospy.Subscriber("/velocity_cmd", velocity_comm,
                                        self.cb_velocity, queue_size=1)
        self.sub_arm = rospy.Subscriber("/arm_control", Float32MultiArray,
                                        self.cb_arm, queue_size=10)
        self.sub_ee = rospy.Subscriber("/end_effector_control", Float32MultiArray,
                                       self.cb_end_effector, queue_size=10)
        self.vel_timer = rospy.Timer(rospy.Duration(1.0 / self.velocity_rate),
                                     self.velocity_timer)
        self.state_timer = rospy.Timer(rospy.Duration(1.0 / self.ros_rate),
                                       self.publish_ros_state)
        rospy.on_shutdown(self.shutdown)
        rospy.loginfo("MQTT bridge iniciada: %s:%d", self.broker, self.port)

    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            rospy.logerr("MQTT: CONNACK retornou %s", rc)
            return
        with self.lock:
            self.connected = True
        for topic in (TOPIC_ULTRASONIC, TOPIC_ENCODERS, TOPIC_MANIPULATOR):
            result, _ = client.subscribe(topic, qos=0)
            if result != mqtt.MQTT_ERR_SUCCESS:
                rospy.logwarn("Falha ao solicitar subscribe de %s", topic)
        rospy.loginfo("MQTT conectado; telemetrias assinadas")

    def on_disconnect(self, client, userdata, rc):
        with self.lock:
            self.connected = False
        rospy.logwarn("MQTT desconectado (rc=%s)", rc)

    def on_message(self, client, userdata, msg):
        if msg.retain:
            return  # estado retido tambem pode ser obsoleto
        try:
            obj = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(obj, dict):
                raise ValueError("JSON nao e objeto")

            if msg.topic == TOPIC_ULTRASONIC:
                vals = tuple(normal_us(obj[k]) for k in US_KEYS)
                # ts_ms e da ESP, nao e timestamp ROS/Unix.
                stamp = obj.get("ts_ms")
                if not finite_number(stamp) or stamp <= 0:
                    raise ValueError("ts_ms invalido")
                with self.lock:
                    self.us = vals
                    self.received_at[TOPIC_ULTRASONIC] = time.monotonic()

            elif msg.topic == TOPIC_ENCODERS:
                raw_vel = tuple(obj[k] for k in WHEEL_KEYS)
                if not all(finite_number(x) for x in raw_vel):
                    raise ValueError("velocidades nao finitas")
                vals = tuple(float(x) for x in raw_vel)
                ticks_obj = obj.get("ticks")
                ticks = None
                if isinstance(ticks_obj, dict):
                    raw = tuple(ticks_obj[k] for k in WHEEL_KEYS)
                    if all(isinstance(v, int) and not isinstance(v, bool)
                           and -(2**31) <= v < 2**31 for v in raw):
                        ticks = raw
                with self.lock:
                    self.enc = vals
                    self.ticks = ticks
                    self.received_at[TOPIC_ENCODERS] = time.monotonic()

            elif msg.topic == TOPIC_MANIPULATOR:
                degrees = obj["base_angle_deg"]
                radians = obj["base_angle_rad"]
                limit = obj["upper_limit_active"]
                valid = obj["encoder_valid"]
                if not all(finite_number(v) for v in (degrees, radians)):
                    raise ValueError("angulo nao finito")
                if limit not in (0, 1) or valid not in (0, 1):
                    raise ValueError("flags invalidas")
                state = (float(degrees), float(radians), float(limit), float(valid))
                with self.lock:
                    self.manip = state
                    self.received_at[TOPIC_MANIPULATOR] = time.monotonic()

        except (ValueError, KeyError, TypeError, OverflowError, UnicodeError) as exc:
            rospy.logwarn_throttle(5.0, "MQTT descartou estado %s: %s", msg.topic, exc)

    def publish_json(self, topic, data):
        with self.lock:
            connected = self.connected
        if not connected:
            return False
        try:
            payload = json.dumps(data, separators=(",", ":"), allow_nan=False)
            info = self.client.publish(topic, payload, qos=0, retain=False)
            return info.rc == mqtt.MQTT_ERR_SUCCESS
        except (ValueError, TypeError) as exc:
            rospy.logwarn_throttle(5.0, "Payload MQTT invalido: %s", exc)
            return False

    def cb_velocity(self, msg):
        values = (msg.front_left, msg.front_right, msg.rear_left, msg.rear_right)
        if not all(finite_number(v) for v in values):
            rospy.logwarn_throttle(5.0, "Comando de velocidade contem NaN/Inf")
            return
        with self.lock:
            self.velocity = tuple(float(v) for v in values)
            self.last_velocity = time.monotonic()

    def velocity_timer(self, event):
        now = time.monotonic()
        with self.lock:
            values = (self.velocity if self.last_velocity is not None
                      and now - self.last_velocity <= self.command_timeout
                      else (0.0, 0.0, 0.0, 0.0))
        self.publish_json(TOPIC_VELOCITY, dict(zip(WHEEL_KEYS, values)))

    def send_motors(self, mask, elevator=0.0, base=0.0, wrist=0.0, gripper=0.0):
        if not 1 <= mask <= 15:
            return
        values = (elevator, base, wrist, gripper)
        if not all(finite_number(x) for x in values):
            rospy.logwarn("Comando de manipulador nao finito")
            return
        if ((mask & MASK_BASE) and not (0.0 <= base <= 360.0)) or \
           ((mask & MASK_WRIST) and not (0.0 <= wrist <= 180.0)) or \
           ((mask & MASK_GRIPPER) and not (0.0 <= gripper <= 180.0)):
            rospy.logwarn("Comando do manipulador fora dos limites")
            return
        # Trava dedicada: sequencias MQTT e publicacao em ordem mesmo que
        # /arm_control e /end_effector_control cheguem em threads diferentes.
        with self.manip_tx_lock:
            with self.lock:
                seq = self.sequence
                self.sequence = (self.sequence + 1) & 0xFFFF
            self.publish_json(TOPIC_MOTORS, {
                "sequence": seq,
                "motor_mask": mask,
                "elevator_cm": float(elevator),
                "base_angle_deg": float(base),
                "wrist_angle_deg": float(wrist),
                "gripper_angle_deg": float(gripper),
            })

    def cb_arm(self, msg):
        data = msg.data
        # Interface ROS antiga: [base, arm]; arm agora e posicao do elevador em cm.
        mask = 0
        elevator = base = 0.0
        if len(data) > 0 and finite_number(data[0]):
            base = float(data[0]); mask |= MASK_BASE
        if len(data) > 1 and finite_number(data[1]):
            elevator = float(data[1]); mask |= MASK_ELEVATOR
        if mask:
            self.send_motors(mask, elevator=elevator, base=base)

    def cb_end_effector(self, msg):
        data = msg.data
        mask = 0
        wrist = gripper = 0.0
        if len(data) > 0 and finite_number(data[0]):
            wrist = max(0.0, min(180.0, float(data[0]))); mask |= MASK_WRIST
        if len(data) > 1 and finite_number(data[1]):
            gripper = max(0.0, min(180.0, float(data[1]))); mask |= MASK_GRIPPER
        if mask:
            self.send_motors(mask, wrist=wrist, gripper=gripper)

    def publish_ros_state(self, event):
        now = time.monotonic()
        with self.lock:
            enc = self.enc if (now - self.received_at.get(TOPIC_ENCODERS, -1e9)
                               <= self.state_timeout) else None
            ticks = self.ticks if enc is not None else None
            us = self.us if (now - self.received_at.get(TOPIC_ULTRASONIC, -1e9)
                            <= self.state_timeout) else None
            manip = self.manip if (now - self.received_at.get(TOPIC_MANIPULATOR, -1e9)
                                  <= self.state_timeout) else None

        if enc is not None:
            m = encoder_comm()
            m.front_left, m.front_right, m.rear_left, m.rear_right = enc
            self.pub_enc.publish(m)
            if ticks is not None:
                self.pub_ticks.publish(Int32MultiArray(data=list(ticks)))
        if us is not None:
            m = ultrasonic_comm()
            put_ultrasonic_message(m, us)
            self.pub_us.publish(m)
            self.pub_us6.publish(Float32MultiArray(data=list(us)))
        if manip is not None:
            self.pub_manip.publish(Float32MultiArray(data=list(manip)))

    def shutdown(self):
        # A ESP right possui watchdog proprio de 300 ms; o envio zero e adicional.
        try:
            self.publish_json(TOPIC_VELOCITY, dict.fromkeys(WHEEL_KEYS, 0.0))
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            pass


if __name__ == "__main__":
    MQTTBridge()
    rospy.spin()
