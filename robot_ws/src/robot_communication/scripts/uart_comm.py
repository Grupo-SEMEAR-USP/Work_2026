#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math
import struct
import threading
import time

import rospy
import serial
from std_msgs.msg import Float32MultiArray
from robot_communication.msg import encoder_comm, velocity_comm, ultrasonic_comm, manipulation_comm

BAUD_RATE = 115200
FRAME_SOF = 0xAA
FRAME_EOF = 0xBB

FMT_LEFT_RX = "<ffffff"
FMT_RIGHT = "<ffff"          # TX e RX (4 velocidades, rad/s)
FMT_CENTER_TX = "<Bffff"     # mask + elevador, base, pulso, garra
FMT_CENTER_RX = "<ffBBB"     # base_deg, base_rad, upper_limit, encoder_valid, mov_complete

US_FIELDS = (
    "us_esq_1", "us_esq_2", "us_dir_1", "us_dir_2",
    "us_esq_frt", "us_dir_frt",
)

MOTOR_ELEVATOR = 1
MOTOR_BASE = 2
MOTOR_WRIST = 4
MOTOR_GRIPPER = 8
MOTOR_ALL = MOTOR_ELEVATOR | MOTOR_BASE | MOTOR_WRIST | MOTOR_GRIPPER

assert struct.calcsize(FMT_LEFT_RX) == 24
assert struct.calcsize(FMT_RIGHT) == 16
assert struct.calcsize(FMT_CENTER_TX) == 17
assert struct.calcsize(FMT_CENTER_RX) == 11


def is_finite(value):
    """Aceita valores numericos ROS finitos, rejeitando bool, NaN e Inf."""
    try:
        return not isinstance(value, bool) and math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def pack_frame(fmt, *values):
    payload = struct.pack(fmt, *values)
    return bytes((FRAME_SOF,)) + payload + bytes((sum(payload) & 0xFF, FRAME_EOF))


class FrameParser:
    """Parser incremental resiliente a chunks incompletos, logs e ruido UART0."""

    def __init__(self, fmt):
        self.fmt = fmt
        self.payload_size = struct.calcsize(fmt)
        self.frame_size = self.payload_size + 3
        self.buffer = bytearray()

    def feed(self, chunk):
        if not chunk:
            return []
        self.buffer.extend(chunk)
        frames = []
        sof = bytes((FRAME_SOF,))

        while True:
            pos = self.buffer.find(sof)
            if pos < 0:
                self.buffer.clear()  # descarta log textual / ruido
                break
            if pos:
                del self.buffer[:pos]

            if len(self.buffer) < self.frame_size:
                break  # aguarda complemento do frame na proxima leitura

            payload = self.buffer[1:1 + self.payload_size]
            chk = self.buffer[1 + self.payload_size]
            eof = self.buffer[2 + self.payload_size]

            if eof == FRAME_EOF and chk == (sum(payload) & 0xFF):
                frames.append(struct.unpack(self.fmt, payload))
                del self.buffer[:self.frame_size]
            else:
                # Re-sincroniza byte a byte; preserva frames validos subsequentes.
                del self.buffer[0]

        return frames


class SerialEndpoint:
    """Porta UART com reconexao e exclusao mutua entre RX e TX."""

    def __init__(self, path, reconnect_interval_s):
        self.path = path
        self.reconnect_interval_s = reconnect_interval_s
        self.lock = threading.RLock()
        self.serial = None
        self.retry_after = 0.0
        self.generation = 0

    def _connect_locked(self):
        if self.serial is not None and self.serial.is_open:
            return True
        if time.monotonic() < self.retry_after:
            return False
        self.retry_after = time.monotonic() + self.reconnect_interval_s
        try:
            port = serial.Serial(
                port=self.path,
                baudrate=BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.03,
                write_timeout=0.2,
                exclusive=True, # impede outra abertura pyserial
            )
            self.serial = port
            self.generation += 1
            rospy.loginfo("UART conectada: %s", self.path)
            return True
        except (serial.SerialException, OSError, ValueError) as exc:
            self.serial = None
            rospy.logwarn_throttle(5.0, "UART %s indisponivel: %s", self.path, exc)
            return False

    def _disconnect_locked(self):
        port = self.serial
        self.serial = None
        self.retry_after = time.monotonic() + self.reconnect_interval_s
        if port is not None:
            try:
                port.close()
            except Exception:
                pass

    def read(self):
        with self.lock:
            if not self._connect_locked():
                return b"", self.generation
            try:
                count = min(max(self.serial.in_waiting, 1), 256)
                return self.serial.read(count), self.generation
            except (serial.SerialException, OSError) as exc:
                rospy.logwarn_throttle(5.0, "Erro RX %s: %s", self.path, exc)
                self._disconnect_locked()
                return b"", self.generation

    def write(self, frame, reconnect=True):
        with self.lock:
            if not reconnect and (self.serial is None or not self.serial.is_open):
                return False
            if reconnect and not self._connect_locked():
                return False
            try:
                n = self.serial.write(frame)
                if n != len(frame):
                    rospy.logwarn_throttle(5.0, "UART %s: escrita parcial %d/%d",
                                           self.path, n, len(frame))
                    self._disconnect_locked()
                    return False
                return True
            except (serial.SerialException, serial.SerialTimeoutException, OSError) as exc:
                rospy.logwarn_throttle(5.0, "Erro TX %s: %s", self.path, exc)
                self._disconnect_locked()
                return False

    def close(self):
        with self.lock:
            self._disconnect_locked()


class UARTBridge:
    def __init__(self):
        rospy.init_node("uart_bridge", anonymous=False)

        self.publish_rate_hz = float(rospy.get_param("~publish_rate_hz", 50.0))
        self.velocity_rate_hz = float(rospy.get_param("~velocity_rate_hz", 20.0))
        self.velocity_timeout_s = float(rospy.get_param("~velocity_timeout_s", 0.5))
        self.state_timeout_s = float(rospy.get_param("~state_timeout_s", 1.0))
        reconnect_interval_s = float(rospy.get_param("~reconnect_interval_s", 1.0))
        if (self.publish_rate_hz <= 0 or self.velocity_rate_hz <= 0 or
                self.velocity_timeout_s < 0 or self.state_timeout_s <= 0 or
                reconnect_interval_s <= 0):
            raise ValueError("Parametros ROS de taxas e timeouts invalidos")

        self.ports = {
            "left": SerialEndpoint(rospy.get_param("~port_left", "/dev/esp_left"),
                                   reconnect_interval_s),
            "right": SerialEndpoint(rospy.get_param("~port_right", "/dev/esp_right"),
                                    reconnect_interval_s),
            "center": SerialEndpoint(rospy.get_param("~port_center", "/dev/esp_center"),
                                     reconnect_interval_s),
        }
        self.running = True
        self.data_lock = threading.Lock()
        self.center_tx_lock = threading.Lock()

        # Ultimas informacoes ROS/serial validas.
        self.velocity = (0.0, 0.0, 0.0, 0.0)
        self.velocity_received_at = None
        self.states = {"left": None, "right": None, "center": None}
        self.received_at = {}

        # Publishers
        self.pub_encoder = rospy.Publisher(
            "/encoder_data", encoder_comm, queue_size=10)
        self.pub_ultrasonic = rospy.Publisher(
            "/ultrasonic_distances", ultrasonic_comm, queue_size=10)
        self.pub_manipulator = rospy.Publisher(
            "/manipulator_state", manipulation_comm, queue_size=10)

        # Threads de leitura: um parser por ESP, sem compartilhar buffers.
        self.threads = [
            threading.Thread(target=self.read_loop,
                             args=("left", FMT_LEFT_RX), daemon=True),
            threading.Thread(target=self.read_loop,
                             args=("right", FMT_RIGHT), daemon=True),
            threading.Thread(target=self.read_loop,
                             args=("center", FMT_CENTER_RX), daemon=True),
        ]
        for thread in self.threads:
            thread.start()

        # Subscribers
        self.sub_velocity = rospy.Subscriber(
            "/velocity_cmd", velocity_comm, self.cb_velocity, queue_size=1)
        self.sub_arm = rospy.Subscriber(
            "/arm_control", Float32MultiArray, self.cb_arm, queue_size=10)
        self.sub_end_effector = rospy.Subscriber(
            "/end_effector_control", Float32MultiArray,
            self.cb_end_effector, queue_size=10)

        self.velocity_timer = rospy.Timer(
            rospy.Duration(1.0 / self.velocity_rate_hz), self.publish_velocity_uart)
        self.state_timer = rospy.Timer(
            rospy.Duration(1.0 / self.publish_rate_hz), self.publish_ros_state)
        rospy.on_shutdown(self.shutdown)
        rospy.loginfo("UART bridge iniciada: esp_left, esp_right e esp_center")

    def read_loop(self, name, fmt):
        port = self.ports[name]
        parser = FrameParser(fmt)
        generation = -1

        while self.running and not rospy.is_shutdown():
            raw, current_generation = port.read()
            if current_generation != generation:
                parser = FrameParser(fmt)  # descarta fragmentos da conexao anterior
                generation = current_generation
            if not raw:
                time.sleep(0.01)
                continue

            for values in parser.feed(raw):
                if name == "right":
                    if not all(is_finite(v) for v in values):
                        continue
                elif name == "center":
                    deg, rad, limit, encoder_valid, mov_complete = values
                    if not (is_finite(deg) and is_finite(rad)):
                        continue
                    if any(flag not in (0, 1) for flag in
                           (limit, encoder_valid, mov_complete)):
                        continue
                else:  # ESP Left: NaN pode representar um ultrassom sem leitura.
                    if any(math.isinf(v) for v in values):
                        continue

                with self.data_lock:
                    self.states[name] = tuple(float(v) for v in values)
                    self.received_at[name] = time.monotonic()

    def cb_velocity(self, msg):
        values = (msg.front_left, msg.front_right,
                  msg.rear_left, msg.rear_right)
        if not all(is_finite(v) for v in values):
            rospy.logwarn_throttle(5.0, "Comando /velocity_cmd invalido (NaN/Inf)")
            return
        with self.data_lock:
            self.velocity = tuple(float(x) for x in values)
            self.velocity_received_at = time.monotonic()

    def publish_velocity_uart(self, event):
        now = time.monotonic()
        with self.data_lock:
            if (self.velocity_received_at is None or
                    (self.velocity_timeout_s > 0 and
                     now - self.velocity_received_at > self.velocity_timeout_s)):
                speeds = (0.0, 0.0, 0.0, 0.0)
            else:
                speeds = self.velocity
        self.ports["right"].write(pack_frame(FMT_RIGHT, *speeds))

    def send_center_command(self, mask, elevator=0.0, base=0.0,
                            wrist=0.0, gripper=0.0):
        if mask < 1 or (mask & ~MOTOR_ALL):
            rospy.logwarn("ESP Center: motor_mask invalida")
            return False
        values = (elevator, base, wrist, gripper)
        if not all(is_finite(v) for v in values):
            rospy.logwarn("ESP Center: comando contem NaN ou Inf")
            return False
        if ((mask & MOTOR_BASE) and not 0.0 <= base <= 360.0) or \
           ((mask & MOTOR_WRIST) and not 0.0 <= wrist <= 180.0) or \
           ((mask & MOTOR_GRIPPER) and not 0.0 <= gripper <= 180.0):
            rospy.logwarn("ESP Center: comando fora dos limites")
            return False

        # Cada evento ROS cria somente o comando para os atuadores solicitados.
        # Assume tratamento de redundância no UID
        try:
            frame = pack_frame(FMT_CENTER_TX, mask, *values)
        except (struct.error, OverflowError) as exc:
            rospy.logwarn("ESP Center: valor fora de float32: %s", exc)
            return False

        with self.center_tx_lock:
            return self.ports["center"].write(frame)

    def cb_arm(self, msg):
        values = list(msg.data)
        # Interface ROS historica: [base_deg, elevator_cm].
        mask = 0
        elevator = base = 0.0
        if len(values) >= 1 and is_finite(values[0]):
            base = float(values[0])
            mask |= MOTOR_BASE
        if len(values) >= 2 and is_finite(values[1]):
            elevator = float(values[1])
            mask |= MOTOR_ELEVATOR
        if mask:
            self.send_center_command(mask, elevator=elevator, base=base)

    def cb_end_effector(self, msg):
        values = list(msg.data)
        mask = 0
        wrist = gripper = 0.0
        if len(values) >= 1 and is_finite(values[0]):
            wrist = max(0.0, min(180.0, float(values[0])))
            mask |= MOTOR_WRIST
        if len(values) >= 2 and is_finite(values[1]):
            gripper = max(0.0, min(180.0, float(values[1])))
            mask |= MOTOR_GRIPPER
        if mask:
            self.send_center_command(mask, wrist=wrist, gripper=gripper)

    def publish_ros_state(self, event):
        now = time.monotonic()
        with self.data_lock:
            fresh = {
                name: self.states[name]
                if now - self.received_at.get(name, float("-inf")) <= self.state_timeout_s
                else None
                for name in ("left", "right", "center")
            }

        if fresh["right"] is not None:
            msg = encoder_comm()
            (msg.front_left, msg.front_right,
             msg.rear_left, msg.rear_right) = fresh["right"]
            self.pub_encoder.publish(msg)

        if fresh["left"] is not None:
            msg = ultrasonic_comm()
            for field, value in zip(US_FIELDS, fresh["left"]):
                setattr(msg, field, value)
            self.pub_ultrasonic.publish(msg)

        if fresh["center"] is not None:
            msg = manipulation_comm()

            msg.base_angle_deg = fresh["center"][0]
            msg.base_angle_rad = fresh["center"][1]
            msg.upper_limit_active = fresh["center"][2]
            msg.encoder_valid = fresh["center"][3]
            msg.manip_feedback = fresh["center"][4]

            self.pub_manipulator.publish(msg)

    def shutdown(self):
        self.running = False
        if hasattr(self, "velocity_timer"):
            self.velocity_timer.shutdown()
        if hasattr(self, "state_timer"):
            self.state_timer.shutdown()

        # Parada segura na ESP Right, sem abrir novas conexoes durante shutdown.
        self.ports["right"].write(
            pack_frame(FMT_RIGHT, 0.0, 0.0, 0.0, 0.0), reconnect=False)

        for thread in self.threads:
            thread.join(timeout=0.5)
        for port in self.ports.values():
            port.close()


if __name__ == "__main__":
    try:
        UARTBridge()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass