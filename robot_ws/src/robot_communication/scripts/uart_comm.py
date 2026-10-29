#!/usr/bin/env python3
"""Bridge ROS Noetic <-> UART0 das esp_left, esp_right e esp_center.

Portas padrao: /dev/esp_left, /dev/esp_right, /dev/esp_center.
Podem ser alteradas por parametros privados ~port_left/right/center.
Publica e assina os mesmos topicos ROS do mqtt_bridge.py, exceto
/encoder_ticks, que so existe na telemetria MQTT da esp_right.

UART 115200 8N1, AA + payload + checksum(sum(payload)&0xff) + BB.
    esp_left:   <6f  (RX, 24 B)
    esp_right:  <4f  (RX/TX, 16 B)
    esp_center: <ffBB (RX, 10 B), <HBffff (TX, 19 B)
"""

import math
import struct
import threading
import time

import rospy
import serial
from std_msgs.msg import Float32MultiArray, Int32MultiArray
from robot_communication.msg import encoder_comm, velocity_comm, ultrasonic_comm

FRAME_SOF = 0xAA
FRAME_EOF = 0xBB
BAUD_RATE = 115200

US_KEYS = ("us_esq_1", "us_esq_2", "us_dir_1", "us_dir_2", "us_frt_1", "us_trs_1")
MASK_ELEVATOR, MASK_BASE, MASK_WRIST, MASK_GRIPPER = 1, 2, 4, 8

FMT_US = "<6f"
FMT_WHEELS = "<4f"
FMT_CENTER_CMD = "<HBffff"
FMT_CENTER_STATE = "<ffBB"
assert struct.calcsize(FMT_US) == 24
assert struct.calcsize(FMT_WHEELS) == 16
assert struct.calcsize(FMT_CENTER_CMD) == 19
assert struct.calcsize(FMT_CENTER_STATE) == 10


def finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)))


def pack_frame(fmt, *values):
    payload = struct.pack(fmt, *values)
    return bytes((FRAME_SOF,)) + payload + bytes((sum(payload) & 0xFF, FRAME_EOF))


def put_ultrasonic_message(msg, values):
    """Prioriza os seis campos novos, mas aceita ultrasonic_comm antigo."""
    if all(hasattr(msg, name) for name in US_KEYS):
        for key, value in zip(US_KEYS, values):
            setattr(msg, key, value)
        return
    # Mapeamento legado provisório: lateral 1 frontal, lateral 2 traseiro.
    # O sensor us_frt_1 so aparece no topico /ultrasonic_distances_6.
    for attr, index in (("front_left", 0), ("rear_left", 1),
                        ("front_right", 2), ("rear_right", 3), ("back", 5)):
        if hasattr(msg, attr):
            setattr(msg, attr, values[index])


class FrameParser:
    """Parser incremental: sincroniza apos bytes soltos/logs/frames corrompidos."""

    def __init__(self, fmt):
        self.fmt = fmt
        self.payload_bytes = struct.calcsize(fmt)
        self.frame_bytes = self.payload_bytes + 3
        self.buf = bytearray()

    def feed(self, chunk):
        self.buf.extend(chunk)
        result = []
        while True:
            start = self.buf.find(bytes((FRAME_SOF,)))
            if start == -1:
                self.buf.clear()
                break
            if start:
                del self.buf[:start]
            if len(self.buf) < self.frame_bytes:
                break
            payload = self.buf[1:1 + self.payload_bytes]
            chk = self.buf[1 + self.payload_bytes]
            eof = self.buf[2 + self.payload_bytes]
            if eof == FRAME_EOF and chk == (sum(payload) & 0xFF):
                result.append(struct.unpack(self.fmt, payload))
                del self.buf[:self.frame_bytes]
            else:
                # Avanca um byte, nao descarta indiscriminadamente frames seguintes.
                del self.buf[0]
        return result


class SerialEndpoint:
    """Um lock por porta para impedir writes concorrentes e read durante reopen."""

    def __init__(self, port):
        self.port = port
        self.lock = threading.RLock()
        self.handle = None
        self.retry_after = 0.0
        self.generation = 0

    def _reopen_locked(self):
        if self.handle is not None and self.handle.is_open:
            return True
        if time.monotonic() < self.retry_after:
            return False
        self.retry_after = time.monotonic() + 1.0
        try:
            self.handle = serial.Serial(self.port, BAUD_RATE, timeout=0.03,
                                        write_timeout=0.10)
            self.handle.reset_input_buffer()
            self.generation += 1
            rospy.loginfo("UART conectada: %s", self.port)
            return True
        except (serial.SerialException, OSError) as exc:
            rospy.logwarn_throttle(5.0, "UART %s indisponivel: %s", self.port, exc)
            self.handle = None
            return False

    def _drop_locked(self):
        if self.handle is not None:
            try:
                self.handle.close()
            except Exception:
                pass
        self.handle = None
        self.retry_after = time.monotonic() + 1.0

    def read(self):
        with self.lock:
            if not self._reopen_locked():
                return b"", self.generation
            try:
                n = min(max(self.handle.in_waiting, 1), 256)
                return self.handle.read(n), self.generation
            except (serial.SerialException, OSError) as exc:
                rospy.logwarn_throttle(5.0, "Falha leitura %s: %s", self.port, exc)
                self._drop_locked()
                return b"", self.generation

    def write(self, frame):
        with self.lock:
            if not self._reopen_locked():
                return False
            try:
                return self.handle.write(frame) == len(frame)
            except (serial.SerialException, serial.SerialTimeoutException, OSError) as exc:
                rospy.logwarn_throttle(5.0, "Falha escrita %s: %s", self.port, exc)
                self._drop_locked()
                return False

    def close(self):
        with self.lock:
            self._drop_locked()


class UARTBridge:
    def __init__(self):
        rospy.init_node("uart_bridge", anonymous=False)
        self.ros_rate = float(rospy.get_param("~publish_rate_hz", 50.0))
        self.velocity_rate = float(rospy.get_param("~velocity_rate_hz", 20.0))
        self.command_timeout = float(rospy.get_param("~command_timeout_s", 0.25))
        self.state_timeout = float(rospy.get_param("~state_timeout_s", 1.0))
        if min(self.ros_rate, self.velocity_rate, self.command_timeout,
               self.state_timeout) <= 0:
            raise ValueError("Taxas e timeouts devem ser positivos")

        self.left = SerialEndpoint(rospy.get_param("~port_left", "/dev/esp_left"))
        self.right = SerialEndpoint(rospy.get_param("~port_right", "/dev/esp_right"))
        self.center = SerialEndpoint(rospy.get_param("~port_center", "/dev/esp_center"))
        self.running = True
        self.lock = threading.Lock()
        self.center_command_lock = threading.Lock()  # sequence e write na mesma ordem
        self.sequence = time.time_ns() & 0xFFFF
        self.last_velocity = None
        self.velocity = (0.0,) * 4
        self.enc = self.us = self.manip = None
        self.received_at = {}

        self.pub_enc = rospy.Publisher("/encoder_data", encoder_comm, queue_size=10)
        self.pub_us = rospy.Publisher("/ultrasonic_distances", ultrasonic_comm, queue_size=10)
        self.pub_us6 = rospy.Publisher("/ultrasonic_distances_6", Float32MultiArray, queue_size=10)
        # Ticks nao estao no payload UART da esp_right; publicar somente MQTT.
        self.pub_manip = rospy.Publisher("/manipulator_state", Float32MultiArray, queue_size=10)

        self.threads = [
            threading.Thread(target=self.read_loop,
                             args=(self.left, FMT_US, "left"), daemon=True),
            threading.Thread(target=self.read_loop,
                             args=(self.right, FMT_WHEELS, "right"), daemon=True),
            threading.Thread(target=self.read_loop,
                             args=(self.center, FMT_CENTER_STATE, "center"), daemon=True),
        ]
        for thread in self.threads:
            thread.start()

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
        rospy.loginfo("UART bridge inicializada (3 portas, 115200 bps)")

    def read_loop(self, endpoint, fmt, name):
        parser = FrameParser(fmt)
        last_generation = -1
        while self.running and not rospy.is_shutdown():
            chunk, generation = endpoint.read()
            if generation != last_generation:
                parser = FrameParser(fmt)
                last_generation = generation
            if not chunk:
                time.sleep(0.01)
                continue
            for values in parser.feed(chunk):
                if name == "left":
                    # NaN no UART pode representar uma leitura indisponivel.
                    state = tuple(float(x) for x in values)
                elif name == "right":
                    if not all(math.isfinite(x) for x in values):
                        continue
                    state = tuple(float(x) for x in values)
                else:
                    deg, rad, limit, valid = values
                    if limit not in (0, 1) or valid not in (0, 1):
                        continue
                    if not (math.isfinite(deg) and math.isfinite(rad)):
                        continue
                    state = (float(deg), float(rad), float(limit), float(valid))
                with self.lock:
                    if name == "left":
                        self.us = state
                    elif name == "right":
                        self.enc = state
                    else:
                        self.manip = state
                    self.received_at[name] = time.monotonic()

    def cb_velocity(self, msg):
        values = (msg.front_left, msg.front_right, msg.rear_left, msg.rear_right)
        if not all(finite_number(v) for v in values):
            rospy.logwarn_throttle(5.0, "Velocidade ROS contem NaN/Inf")
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
        self.right.write(pack_frame(FMT_WHEELS, *values))

    def send_center(self, mask, elevator=0.0, base=0.0, wrist=0.0, gripper=0.0):
        values = (elevator, base, wrist, gripper)
        if not (1 <= mask <= 15) or not all(finite_number(v) for v in values):
            return
        if ((mask & MASK_BASE) and not (0 <= base <= 360)) or \
           ((mask & MASK_WRIST) and not (0 <= wrist <= 180)) or \
           ((mask & MASK_GRIPPER) and not (0 <= gripper <= 180)):
            rospy.logwarn("Comando para esp_center fora dos limites")
            return
        with self.center_command_lock:
            seq = self.sequence
            frame = pack_frame(FMT_CENTER_CMD, seq, mask,
                               float(elevator), float(base),
                               float(wrist), float(gripper))
            # Nao perde a sequencia quando a porta esta desconectada.
            if self.center.write(frame):
                self.sequence = (self.sequence + 1) & 0xFFFF

    def cb_arm(self, msg):
        data = msg.data
        mask = 0
        elevator = base = 0.0
        if len(data) > 0 and finite_number(data[0]):
            base = float(data[0]); mask |= MASK_BASE
        if len(data) > 1 and finite_number(data[1]):
            elevator = float(data[1]); mask |= MASK_ELEVATOR
        if mask:
            self.send_center(mask, elevator=elevator, base=base)

    def cb_end_effector(self, msg):
        data = msg.data
        mask = 0
        wrist = gripper = 0.0
        if len(data) > 0 and finite_number(data[0]):
            wrist = max(0.0, min(180.0, float(data[0]))); mask |= MASK_WRIST
        if len(data) > 1 and finite_number(data[1]):
            gripper = max(0.0, min(180.0, float(data[1]))); mask |= MASK_GRIPPER
        if mask:
            self.send_center(mask, wrist=wrist, gripper=gripper)

    def publish_ros_state(self, event):
        now = time.monotonic()
        with self.lock:
            enc = self.enc if now - self.received_at.get("right", -1e9) <= self.state_timeout else None
            us = self.us if now - self.received_at.get("left", -1e9) <= self.state_timeout else None
            manip = self.manip if now - self.received_at.get("center", -1e9) <= self.state_timeout else None
        if enc is not None:
            m = encoder_comm()
            m.front_left, m.front_right, m.rear_left, m.rear_right = enc
            self.pub_enc.publish(m)
        if us is not None:
            m = ultrasonic_comm()
            put_ultrasonic_message(m, us)
            self.pub_us.publish(m)
            self.pub_us6.publish(Float32MultiArray(data=list(us)))
        if manip is not None:
            self.pub_manip.publish(Float32MultiArray(data=list(manip)))

    def shutdown(self):
        self.running = False
        # Comando seguro na parada; nao substitui o watchdog de firmware.
        self.right.write(pack_frame(FMT_WHEELS, 0.0, 0.0, 0.0, 0.0))
        for thread in self.threads:
            thread.join(timeout=0.3)
        self.left.close()
        self.right.close()
        self.center.close()


if __name__ == "__main__":
    UARTBridge()
    rospy.spin()
