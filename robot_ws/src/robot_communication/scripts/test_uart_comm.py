#!/usr/bin/env python3
"""Testes de protocolo e ponte UART sem ROS, serial fisica ou ESP32."""
import importlib.util
import math
import struct
import sys
import threading
import time
import types
import unittest
from pathlib import Path

# Stubs de modulos presentes na Jetson/ROS Noetic.
rospy = types.ModuleType('rospy')
rospy.logwarn = lambda *a, **kw: None
rospy.logwarn_throttle = lambda *a, **kw: None
rospy.logerr = lambda *a, **kw: None
rospy.loginfo = lambda *a, **kw: None
sys.modules['rospy'] = rospy
serial = types.ModuleType('serial')
serial.SerialException = type('SerialException', (Exception,), {})
serial.SerialTimeoutException = type('SerialTimeoutException', (Exception,), {})
serial.EIGHTBITS = 8
serial.PARITY_NONE = 'N'
serial.STOPBITS_ONE = 1
sys.modules['serial'] = serial

std_msgs = types.ModuleType('std_msgs')
std_msgs_msg = types.ModuleType('std_msgs.msg')
class Float32MultiArray:
    def __init__(self, data=None): self.data = data or []
std_msgs_msg.Float32MultiArray = Float32MultiArray
sys.modules['std_msgs'] = std_msgs
sys.modules['std_msgs.msg'] = std_msgs_msg

robot = types.ModuleType('robot_communication')
robot_msg = types.ModuleType('robot_communication.msg')
class encoder_comm:
    def __init__(self):
        self.front_left = self.front_right = self.rear_left = self.rear_right = 0.0
class velocity_comm(encoder_comm): pass
class ultrasonic_comm:
    def __init__(self):
        self.us_esq_1 = self.us_esq_2 = self.us_dir_1 = self.us_dir_2 = 0.0
        self.us_esq_frt = self.us_dir_frt = 0.0
robot_msg.encoder_comm = encoder_comm
robot_msg.velocity_comm = velocity_comm
robot_msg.ultrasonic_comm = ultrasonic_comm
sys.modules['robot_communication'] = robot
sys.modules['robot_communication.msg'] = robot_msg

spec = importlib.util.spec_from_file_location('uart_comm', str(Path(__file__).with_name('uart_comm.py')))
uart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uart)

class Pub:
    def __init__(self): self.items = []
    def publish(self, v): self.items.append(v)

class Port:
    def __init__(self): self.frames = []
    def write(self, data, reconnect=True):
        self.frames.append(bytes(data))
        return True

class TestUARTComm(unittest.TestCase):
    def bridge(self):
        b = uart.UARTBridge.__new__(uart.UARTBridge)
        b.data_lock = threading.Lock()
        b.center_tx_lock = threading.Lock()
        b.velocity = (0.,) * 4
        b.velocity_received_at = None
        b.velocity_timeout_s = 0.5
        b.state_timeout_s = 1.0
        b.states = {'left': None, 'right': None, 'center': None}
        b.received_at = {}
        b.ports = {'left': Port(), 'right': Port(), 'center': Port()}
        b.pub_encoder = Pub()
        b.pub_ultrasonic = Pub()
        b.pub_manipulator = Pub()
        return b

    def test_frame_sizes_and_checksum(self):
        for fmt, values, length in [
            (uart.FMT_LEFT_RX, (1., 2., 3., 4., 5., 6.), 27),
            (uart.FMT_RIGHT, (1., -2., 3., -4.), 19),
            (uart.FMT_CENTER_TX, (15, 1., 90., 45., 120.), 20),
            (uart.FMT_CENTER_RX, (90., 1.5, 0, 1, 1), 14),
        ]:
            with self.subTest(fmt=fmt):
                f = uart.pack_frame(fmt, *values)
                self.assertEqual(len(f), length)
                self.assertEqual((f[0], f[-1]), (0xaa, 0xbb))
                self.assertEqual(f[-2], sum(f[1:-2]) & 255)
                self.assertEqual(uart.FrameParser(fmt).feed(f)[0], values)

    def test_parser_fragments_logs_corrupt_frame_recovery(self):
        p = uart.FrameParser(uart.FMT_LEFT_RX)
        good = uart.pack_frame(uart.FMT_LEFT_RX, 1., 2., 3., 4., 5., 6.)
        bad = bytearray(good)
        bad[-2] ^= 0x3f
        self.assertEqual(p.feed(b'I (1) APP_MAIN: ola\n' + good[:8]), [])
        self.assertEqual(p.feed(good[8:]), [(1., 2., 3., 4., 5., 6.)])
        self.assertEqual(p.feed(bytes(bad) + good), [(1., 2., 3., 4., 5., 6.)])

    def test_right_speed_order(self):
        b = self.bridge()
        msg = velocity_comm()
        msg.front_left, msg.front_right = 1.0, -2.0
        msg.rear_left, msg.rear_right = 3.0, -4.0
        b.cb_velocity(msg)
        b.publish_velocity_uart(None)
        self.assertEqual(uart.FrameParser(uart.FMT_RIGHT).feed(b.ports['right'].frames[0]),
                         [(1., -2., 3., -4.)])

    def test_velocity_timeout_zeros(self):
        b = self.bridge()
        b.velocity = (1., 2., 3., 4.)
        b.velocity_received_at = time.monotonic() - 2
        b.publish_velocity_uart(None)
        self.assertEqual(uart.FrameParser(uart.FMT_RIGHT).feed(b.ports['right'].frames[0]),
                         [(0., 0., 0., 0.)])

    def test_velocity_timeout_can_be_disabled(self):
        b = self.bridge()
        b.velocity_timeout_s = 0.0
        b.velocity = (1., 2., 3., 4.)
        b.velocity_received_at = time.monotonic() - 2
        b.publish_velocity_uart(None)
        self.assertEqual(uart.FrameParser(uart.FMT_RIGHT).feed(b.ports['right'].frames[0]),
                         [(1., 2., 3., 4.)])

    def test_center_arm_mask_no_old_relative_replay(self):
        b = self.bridge()
        b.cb_arm(Float32MultiArray([90., 2.]))
        b.cb_end_effector(Float32MultiArray([45., 120.]))
        p = uart.FrameParser(uart.FMT_CENTER_TX)
        got = p.feed(b''.join(b.ports['center'].frames))
        self.assertEqual(got, [(3, 2., 90., 0., 0.), (12, 0., 0., 45., 120.)])

    def test_center_one_motor(self):
        b = self.bridge()
        b.cb_arm(Float32MultiArray([30.]))
        self.assertEqual(uart.FrameParser(uart.FMT_CENTER_TX).feed(b.ports['center'].frames[0]),
                         [(2, 0., 30., 0., 0.)])
        self.assertEqual(b.send_center_command(8, gripper=90), True)
        self.assertEqual(uart.FrameParser(uart.FMT_CENTER_TX).feed(b.ports['center'].frames[1]),
                         [(8, 0., 0., 0., 90.)])

    def test_center_reject_out_of_bounds(self):
        b = self.bridge()
        self.assertFalse(b.send_center_command(2, base=400))
        self.assertFalse(b.send_center_command(1, elevator=float('nan')))
        self.assertEqual(b.ports['center'].frames, [])

    def test_six_sensors_and_state_output(self):
        b = self.bridge()
        b.states = {'left': (1., 2., 3., 4., 5., 6.),
                    'right': (10., 20., 30., 40.),
                    'center': (90., 1.570796, 0., 1., 1.)}
        b.received_at = {k: time.monotonic() for k in b.states}
        b.publish_ros_state(None)
        self.assertEqual(len(b.pub_ultrasonic.items), 1)
        m = b.pub_ultrasonic.items[0]
        self.assertEqual(tuple(getattr(m, k) for k in uart.US_FIELDS), (1., 2., 3., 4., 5., 6.))
        self.assertEqual(len(b.pub_encoder.items), 1)
        self.assertEqual((b.pub_encoder.items[0].front_left, b.pub_encoder.items[0].rear_right), (10., 40.))
        self.assertEqual(b.pub_manipulator.items[0].data, [90., 1.570796, 0., 1., 1.])

    def test_stale_state_not_republished(self):
        b = self.bridge()
        b.states['right'] = (1., 2., 3., 4.)
        b.received_at['right'] = time.monotonic() - 9
        b.publish_ros_state(None)
        self.assertEqual(b.pub_encoder.items, [])

    def test_not_stale_center_state(self):
        p = uart.FrameParser(uart.FMT_CENTER_RX)
        s = uart.pack_frame(uart.FMT_CENTER_RX, 30., 0.5235988, 1, 0, 0)
        self.assertEqual(p.feed(s)[0][2:], (1, 0, 0))

    def test_corrupt_after_random_noise(self):
        p = uart.FrameParser(uart.FMT_RIGHT)
        good = uart.pack_frame(uart.FMT_RIGHT, 1., -2., 3., -4.)
        self.assertEqual(p.feed(b'\x00\x7f\xff\x01' + good[:4]), [])
        self.assertEqual(p.feed(good[4:]), [(1., -2., 3., -4.)])

if __name__ == '__main__':
    unittest.main(verbosity=2)
