#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gerador de comandos e monitor misto de UART0 para esp_left/right/center.

GUI:    python3 frame_test.py
CLI:    python3 frame_test.py --cli
Monitor terminal: python3 frame_test.py --monitor left --port /dev/esp_left
Testes: python3 frame_test.py --test

GUI: Tkinter (sudo apt install python3-tk)
Conexao serial: PySerial (sudo apt install python3-serial)

Protocolo: AA + payload little-endian + sum(payload)&0xFF + BB.
ESP LEFT:   RX <ffffff  (24 bytes de payload; 27 bytes de frame)
ESP RIGHT:  TX/RX <ffff  (16 bytes de payload; 19 bytes de frame)
ESP CENTER: TX <Bffff  (17 bytes de payload; 20 bytes de frame)
ESP CENTER: RX <ffBBB  (11 bytes de payload; 14 bytes de frame)

O programa NAO envia comandos para esp_left: ela so envia telemetria.
"""

import argparse
import errno
import fcntl
import hashlib
import os
import socket
import stat
import tempfile
import math
import queue
import re
import struct
import sys
import threading
import time
import unittest
from dataclasses import dataclass

SOF = 0xAA
EOF = 0xBB
BAUD_RATE = 115200
MOTOR_BITS = {"elevator_cm": 1, "base_angle_deg": 2,
              "wrist_angle_deg": 4, "gripper_angle_deg": 8}

ESP_LABELS = {
    "left": "ESP Left  |  6 ultrassonicos (somente RX)",
    "right": "ESP Right  |  4 motores e encoders",
    "center": "ESP Center  |  manipulador",
}
DEFAULT_PORTS = {key: "/dev/esp_" + key for key in ESP_LABELS}


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    min_value: float = -math.inf
    max_value: float = math.inf


RIGHT_CMD_FIELDS = (
    Field("left_front_data", "Dianteiro esquerdo (rad/s)"),
    Field("right_front_data", "Dianteiro direito (rad/s)"),
    Field("left_rear_data", "Traseiro esquerdo (rad/s)"),
    Field("right_rear_data", "Traseiro direito (rad/s)"),
)
CENTER_CMD_FIELDS = (
    Field("elevator_cm", "Elevador: deslocamento relativo (cm)"),
    Field("base_angle_deg", "Base: angulo absoluto (graus)", 0.0, 360.0),
    Field("wrist_angle_deg", "Pulso: angulo absoluto (graus)", 0.0, 180.0),
    Field("gripper_angle_deg", "Garra: angulo absoluto (graus)", 0.0, 180.0),
)
# Estas constantes sao de DECODIFICACAO de RX, nao geram comandos.
TELEMETRY = {
    "left": ("<ffffff", ("us_esq_1", "us_esq_2", "us_dir_1", "us_dir_2",
                           "us_esq_frt", "us_dir_frt")),
    "right": ("<ffff", ("left_front", "right_front", "left_rear", "right_rear")),
    "center": ("<ffBBB", ("base_angle_deg", "base_angle_rad", "upper_limit_active",
                            "encoder_valid", "mov_complete")),
}
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def hex_spaced(data):
    return " ".join("{:02X}".format(x) for x in data)


def pack_frame(payload):
    """Enquadra o payload binario, inclusive quando contem AA, BB ou '\\n'."""
    return bytes((SOF,)) + payload + bytes((sum(payload) & 0xFF, EOF))


def parse_float32(raw, field):
    try:
        val = float(str(raw).strip().replace(",", "."))
    except ValueError as err:
        raise ValueError("{}: informe um numero valido".format(field.label)) from err
    if not math.isfinite(val):
        raise ValueError("{}: NaN/Infinity nao permitidos".format(field.label))
    if not field.min_value <= val <= field.max_value:
        raise ValueError("{}: fora da faixa [{}, {}]".format(
            field.label, field.min_value, field.max_value))
    try:
        data = struct.pack("<f", val)
    except (struct.error, OverflowError) as err:
        raise ValueError("{}: fora da representacao float32".format(field.label)) from err
    if not math.isfinite(struct.unpack("<f", data)[0]):
        raise ValueError("{}: fora da representacao float32".format(field.label))
    return val


def build_command(esp, values, active=None):
    """Retorna (payload, frame, mask); motor_mask somente para Center."""
    if esp not in ("right", "center"):
        raise ValueError("A ESP Left nao aceita comandos UART (apenas uart_send).")
    active = active or {}
    fields = RIGHT_CMD_FIELDS if esp == "right" else CENTER_CMD_FIELDS
    floats = []
    mask = 0
    for f in fields:
        enabled = esp == "right" or bool(active.get(f.key, False))
        if enabled:
            floats.append(parse_float32(values.get(f.key, "0"), f))
            if esp == "center":
                mask |= MOTOR_BITS[f.key]
        else:
            floats.append(0.0)  # firmware ignora campos desmarcados
    if esp == "center":
        if not mask:
            raise ValueError("ESP Center: habilite pelo menos um motor")
        payload = struct.pack("<Bffff", mask, *floats)
    else:
        payload = struct.pack("<ffff", *floats)
    return payload, pack_frame(payload), mask


def describe_telemetry(esp, values):
    """Human-readable: imprime explicitamente 6 sensores/4 motores/3 flags."""
    names = TELEMETRY[esp][1]
    result = []
    for key, val in zip(names, values):
        if key in ("upper_limit_active", "encoder_valid", "mov_complete"):
            txt = "{} ({})".format(val, "SIM" if val else "NAO")
        elif key in ("base_angle_deg",):
            txt = "{:.4f} graus".format(val)
        elif key in ("base_angle_rad",):
            txt = "{:.5f} rad".format(val)
        elif esp == "left":
            txt = "{:.3f} cm".format(val)
        else:
            txt = "{:.4f} rad/s".format(val)
        result.append("{} = {}".format(key, txt))
    return " | ".join(result)


class MixedUARTParser:
    """Consome fluxo de RX mesclando logs de texto e frames binarios.

    Valida SOF, tamanho EXATO, checksum e EOF antes de chamar de frame.
    Toda a saida usa callback: callback(tipo, conteudo).
    O stream bruto (inclusive frames ruins) deve ser registrado no nivel serial.
    """

    def __init__(self, esp, callback, timeout_s=0.35):
        if esp not in TELEMETRY:
            raise ValueError("ESP invalida")
        self.esp = esp
        self.callback = callback
        self.timeout_s = timeout_s
        self.fmt = TELEMETRY[esp][0]
        self.payload_size = struct.calcsize(self.fmt)
        self.frame_size = self.payload_size + 3
        self.candidate = bytearray()
        self.logbuf = bytearray()
        self.last_byte_at = 0.0

    def feed(self, data):
        for byte in data:
            self._consume(byte)

    def _consume(self, byte):
        if self.candidate:
            self.candidate.append(byte)
            self.last_byte_at = time.monotonic()
            if len(self.candidate) == self.frame_size:
                self._finish_candidate()
            return
        if byte == SOF:
            self._flush_log(partial=True)
            self.candidate.append(byte)
            self.last_byte_at = time.monotonic()
        else:
            self._consume_text(byte)

    def _consume_text(self, byte):
        self.logbuf.append(byte)
        if byte == 0x0A:  # fim de linha
            self._flush_log(partial=False)
        elif len(self.logbuf) >= 1024:
            self._flush_log(partial=True)

    def _flush_log(self, partial):
        if not self.logbuf:
            return
        raw = bytes(self.logbuf)
        self.logbuf.clear()
        if raw.strip(b"\r\n\t ") == b"":
            return
        # Texto UTF-8 nao depende das fronteiras dos read() da PySerial.
        clean = ANSI_PATTERN.sub("", raw.decode("utf-8", errors="replace"))
        clean = clean.strip("\r\n")
        # Evita que lixo binario fora de frame destrua o layout do monitor.
        clean = "".join(c if (c.isprintable() or c == "\t") else "\\x{:02X}".format(ord(c))
                        for c in clean)
        if clean:
            self.callback("log_partial" if partial else "log", clean)

    def _finish_candidate(self):
        raw = bytes(self.candidate)
        self.candidate.clear()
        payload = raw[1:1 + self.payload_size]
        checksum = sum(payload) & 0xFF
        if raw[-1] == EOF and raw[-2] == checksum:
            vals = struct.unpack(self.fmt, payload)
            if self.esp == "center" and any(x not in (0, 1) for x in vals[2:]):
                self.callback("error", "Flags de telemetria Center invalidas: " + hex_spaced(raw))
                self._recover(raw[1:])
                return
            self.callback("frame", (raw, vals))
        else:
            issue = "EOF invalido" if raw[-1] != EOF else "checksum invalido"
            self.callback("error", "Candidato AA rejeitado ({}): {}".format(issue, hex_spaced(raw)))
            self._recover(raw[1:])

    def _recover(self, tail):
        # Rescan a partir do byte seguinte ao primeiro SOF.
        # Recupera frames subsequentes mesmo quando houve ruido no canal.
        for byte in tail:
            self._consume(byte)

    def tick(self):
        """Evita aguardar indefinidamente candidato de frame incompleto."""
        if self.candidate and time.monotonic() - self.last_byte_at > self.timeout_s:
            raw = bytes(self.candidate)
            self.candidate.clear()
            self.callback("error", "Candidato de frame incompleto/timeout: " + hex_spaced(raw))
            self._recover(raw[1:])

    def close(self):
        self.tick()
        self._flush_log(partial=True)



# --- Gerenciamento de propriedade da porta (Linux / Jetson) ------------------
# Um processo nao pode simplesmente fechar o fd serial de outro processo.
# O protocolo abaixo permite que OUTRA INSTANCIA DESTE MESMO SCRIPT libere
# voluntariamente a porta antes da conexao nova. Processos de terceiros
# (GTKTerm, screen, rosserial etc.) sao detectados, nunca terminados.


def find_port_users(path):
    """Tenta identificar processos com um fd aberto para o MESMO device tty.

    Uma verificacao /proc de melhor esforco; em sistemas com hidepid ou
    permissoes restritas, pode nao enxergar todos os processos.
    """
    try:
        target = os.stat(os.path.realpath(path))
    except OSError:
        return []
    if not stat.S_ISCHR(target.st_mode):
        # Testes com PTY sao char devices; dispositivos virtuais podem variar.
        return []
    users = []
    for entry in os.scandir('/proc'):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == os.getpid():
            continue
        try:
            with os.scandir('/proc/{}/fd'.format(pid)) as fds:
                for fd in fds:
                    try:
                        info = os.stat(fd.path)
                    except (OSError, PermissionError):
                        continue
                    if stat.S_ISCHR(info.st_mode) and info.st_rdev == target.st_rdev:
                        try:
                            with open('/proc/{}/comm'.format(pid), encoding='utf-8') as f:
                                name = f.read().strip()
                        except OSError:
                            name = '?'
                        users.append((pid, name))
                        break
        except (OSError, PermissionError):
            continue
    return users


def format_port_users(users):
    return ', '.join('{} (PID {})'.format(name, pid) for pid, name in users)


class SerialPortLease:
    """Lock entre instancias e handoff cooperativo da porta UART (POSIX)."""

    def __init__(self, port, on_release):
        self.port = port
        self.on_release = on_release
        ident = hashlib.sha256(os.path.realpath(port).encode('utf-8')).hexdigest()[:20]
        self.dir_path = os.path.join(tempfile.gettempdir(), 'frame_test_{}'.format(os.getuid()))
        self.lock_path = os.path.join(self.dir_path, ident + '.lock')
        self.socket_path = os.path.join(self.dir_path, ident + '.sock')
        self.lockfd = None
        self.sock = None
        self.server = None
        self.closed = threading.Event()

    def acquire(self):
        os.makedirs(self.dir_path, mode=0o700, exist_ok=True)
        if os.stat(self.dir_path).st_uid != os.getuid():
            raise RuntimeError('Diretorio de locks pertence a outro usuario: ' + self.dir_path)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Se a versao anterior e deste script, pedir que solte a porta.
                self._ask_old_instance_to_release()
                deadline = time.monotonic() + 3.0
                while True:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError(
                                'Outra instancia de frame_test esta conectada. '
                                'Nao foi possivel transferir automaticamente a porta. '
                                'Feche a instancia antiga e tente novamente.')
                        time.sleep(0.05)

            # Depois de tomar o lock, conferir processos nao cooperativos.
            users = find_port_users(self.port)
            if users:
                raise RuntimeError(
                    'Porta ja aberta por outro processo: {}. '
                    'Para evitar disputa de bytes, feche esse programa '
                    '(ex.: GTKTerm ou outro Python) antes de conectar.'.format(format_port_users(users)))
            self.lockfd = fd
        except BaseException:
            os.close(fd)
            raise

    def _ask_old_instance_to_release(self):
        if not os.path.exists(self.socket_path):
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                sock.connect(self.socket_path)
                sock.sendall(b'RELEASE\n')
                sock.recv(64)
        except (OSError, socket.timeout):
            pass

    def start_server(self):
        if self.lockfd is None:
            raise RuntimeError('Lock nao adquirido')
        # So o dono do lock pode criar/substituir o socket deste device.
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(self.socket_path)
            os.chmod(self.socket_path, 0o600)
            sock.listen(1)
            sock.settimeout(0.2)
        except BaseException:
            sock.close()
            raise
        self.sock = sock
        self.server = threading.Thread(target=self._serve, daemon=True)
        self.server.start()

    def _serve(self):
        while not self.closed.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                try:
                    conn.settimeout(0.4)
                    if conn.recv(32).strip() == b'RELEASE':
                        self.on_release()  # O callback deve agendar shutdown na thread apropriada.
                        conn.sendall(b'ACK\n')
                except OSError:
                    pass

    def close(self):
        self.closed.set()
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self.server is not None and self.server is not threading.current_thread():
            self.server.join(timeout=0.35)
            self.server = None
        if self.lockfd is not None:
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
            fcntl.flock(self.lockfd, fcntl.LOCK_UN)
            os.close(self.lockfd)
            self.lockfd = None


def open_managed_serial(port, on_release, timeout=0.1):
    """Adquire lock, fecha outra instancia cooperativa e abre serial exclusiva.

    O exclusive=True usa bloqueio cooperativo na plataforma POSIX; nao remove
    leitores que ja tinham aberto o dispositivo, nem bloqueia todos os apps.
    """
    import serial
    lease = SerialPortLease(port, on_release)
    lease.acquire()
    ser = None
    try:
        ser = serial.Serial(port=port, baudrate=BAUD_RATE, timeout=timeout,
                            write_timeout=0.5, exclusive=True)
        lease.start_server()
    except BaseException:
        if ser is not None:
            ser.close()
        lease.close()
        raise
    return ser, lease


def cli():
    print("Gerador UART 115200 8N1 | Right e Center")
    while True:
        try:
            choice = input("ESP [r]ight, [c]enter, [q] sair: ").strip().lower()
            if choice in ("q", "sair", "0"):
                break
            esp = {"r": "right", "c": "center"}.get(choice)
            if esp is None:
                print("Opcao invalida. A ESP Left nao recebe comandos UART.")
                continue
            vals, active = {}, {}
            fields = RIGHT_CMD_FIELDS if esp == "right" else CENTER_CMD_FIELDS
            for field in fields:
                if esp == "center":
                    active[field.key] = input("Ativar {}? [s/N] ".format(field.label)).strip().lower() in ("s", "sim")
                    if not active[field.key]:
                        continue
                vals[field.key] = input("{} [0]: ".format(field.label)).strip() or "0"
            payload, frame, mask = build_command(esp, vals, active)
            print("PAYLOAD ({} B): {}".format(len(payload), hex_spaced(payload)))
            if esp == "center":
                print("motor_mask: {} / 0x{:02X}".format(mask, mask))
            print("CHECKSUM: {:02X}".format(frame[-2]))
            print("FRAME ({} B): {}\n".format(len(frame), hex_spaced(frame)))
        except ValueError as err:
            print("ERRO: {}\n".format(err))
        except (EOFError, KeyboardInterrupt):
            break


def monitor_cli(esp, port=None, show_raw=False):
    """Le telemetria e logs sem interface grafica, com propriedade exclusiva."""
    try:
        import serial
    except ImportError:
        print('PySerial ausente. Instale: sudo apt install python3-serial', file=sys.stderr)
        return 2

    port = port or DEFAULT_PORTS[esp]
    counts = {'bytes': 0, 'frame': 0, 'log': 0, 'error': 0}
    released = threading.Event()

    def callback(kind, value):
        if kind == 'frame':
            counts['frame'] += 1
            raw, vals = value
            print('[FRAME RX] {} bytes: {}'.format(len(raw), hex_spaced(raw)), flush=True)
            print('           {}'.format(describe_telemetry(esp, vals)), flush=True)
        elif kind.startswith('log'):
            counts['log'] += 1
            print('[ESP LOG] {}'.format(value), flush=True)
        else:
            counts['error'] += 1
            print('[RX ALERTA] {}'.format(value), flush=True)

    parser = MixedUARTParser(esp, callback)
    print('Monitor UART: {} | {} | {} 8N1'.format(esp.upper(), port, BAUD_RATE), flush=True)
    print('Somente leitura; Ctrl+C para sair.', flush=True)
    try:
        ser, lease = open_managed_serial(port, released.set, timeout=0.1)
    except (serial.SerialException, OSError, RuntimeError) as exc:
        print('Falha abrindo porta: {}'.format(exc), file=sys.stderr)
        return 1
    try:
        print('PORTA ABERTA (exclusiva); aguardando RX...', flush=True)
        next_report = time.monotonic() + 3.0
        while not released.is_set():
            data = ser.read(min(ser.in_waiting or 1, 1024))
            if data:
                counts['bytes'] += len(data)
                if show_raw:
                    print('[RX HEX] {}'.format(hex_spaced(data)), flush=True)
                parser.feed(data)
            parser.tick()
            now = time.monotonic()
            if now >= next_report:
                print('[STATUS] bytes={} frames={} logs={} alertas={}'.format(
                    counts['bytes'], counts['frame'], counts['log'], counts['error']), flush=True)
                if counts['bytes'] == 0:
                    print('[AVISO] Porta aberta, mas nenhum byte RX. Confira a ESP e o firmware.', flush=True)
                next_report = now + 5.0
        print('Outra instancia de frame_test assumiu a porta; desconectando.', flush=True)
    except KeyboardInterrupt:
        print('\nMonitor encerrado.', flush=True)
    except (serial.SerialException, OSError) as exc:
        print('Leitura serial interrompida: {}'.format(exc), file=sys.stderr)
        return 1
    finally:
        parser.close()
        ser.close()
        lease.close()
    return 0


def gui():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
    except ImportError:
        sys.exit("Tkinter indisponivel: sudo apt install python3-tk. Ou execute --cli.")

    class App:
        def __init__(self, root):
            self.root = root
            root.title("ESP32 UART | Gerador de comandos + Monitor serial")
            root.geometry("1090x840")
            root.minsize(870, 670)
            self.selected = tk.StringVar(value="right")
            self.port_var = tk.StringVar(value=DEFAULT_PORTS["right"])
            self.status_var = tk.StringVar(value="Desconectado")
            self.show_raw = tk.BooleanVar(value=False)
            self.values = {"right": {}, "center": {}}
            self.checked = {}
            self.entries = {}
            self.motor_checks = {}
            self.frame = None
            self.payload = None
            self.serial = None
            self.lease = None
            self.reader = None
            self.stop_event = threading.Event()
            self.session_id = 0
            self.rx_overflow = threading.Event()
            self.takeover_request = threading.Event()
            self.rx_queue = queue.Queue(maxsize=4096)
            self.parser = None
            self.auto_scroll = tk.BooleanVar(value=True)  # painel Frames
            self.auto_scroll_logs = tk.BooleanVar(value=True)  # painel ESP logs
            self.max_display_lines = 1800
            self.rx_stats_var = tk.StringVar(value="RX: desconectado")
            self.rx_bytes = 0
            self.rx_frames = 0
            self.rx_logs = 0
            self.rx_alerts = 0
            self.rx_connected_at = 0.0
            self.rx_last_at = 0.0
            self.rx_no_data_warned = False
            self.last_stats_update = 0.0

            outer = ttk.Frame(root, padding=12)
            outer.pack(fill="both", expand=True)
            outer.columnconfigure(0, weight=1)

            ttk.Label(outer, text="Gerador e monitor UART para ESP32",
                      font=("Sans", 16, "bold")).grid(row=0, column=0, sticky="w")
            ttk.Label(outer, text="Protocolo AA + payload + checksum + BB | 115200 baud, 8N1 | Little-endian").grid(
                row=1, column=0, sticky="w", pady=(3, 12))

            conn = ttk.LabelFrame(outer, text="Conexao serial (sem GTKTerm aberto)", padding=10)
            conn.grid(row=2, column=0, sticky="ew")
            conn.columnconfigure(3, weight=1)
            ttk.Label(conn, text="ESP:").grid(row=0, column=0, padx=(0, 6))
            self.esp_cb = ttk.Combobox(conn, state="readonly", width=37,
                                       values=list(ESP_LABELS.values()))
            self.esp_cb.current(1)
            self.esp_cb.grid(row=0, column=1, padx=(0, 12), sticky="w")
            self.esp_cb.bind("<<ComboboxSelected>>", self.switch_esp)
            ttk.Label(conn, text="Porta:").grid(row=0, column=2, padx=(0, 6))
            self.port_cb = ttk.Combobox(conn, textvariable=self.port_var, width=24)
            self.port_cb.grid(row=0, column=3, sticky="ew")
            ttk.Button(conn, text="Listar portas", command=self.refresh_ports).grid(
                row=0, column=4, padx=(7, 7))
            self.conn_btn = ttk.Button(conn, text="Conectar", command=self.toggle_connection)
            self.conn_btn.grid(row=0, column=5)
            ttk.Label(conn, textvariable=self.status_var).grid(row=1, column=0, columnspan=6,
                                                                sticky="w", pady=(9, 0))
            ttk.Label(conn, textvariable=self.rx_stats_var).grid(row=2, column=0, columnspan=6,
                                                                   sticky="w", pady=(4, 0))

            self.tabs = ttk.Notebook(outer)
            self.tabs.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
            outer.rowconfigure(3, weight=1)
            self.cmd_tab = ttk.Frame(self.tabs, padding=14)
            self.mon_tab = ttk.Frame(self.tabs, padding=10)
            self.logs_tab = ttk.Frame(self.tabs, padding=10)
            self.tabs.add(self.cmd_tab, text="Gerar / Enviar comandos")
            self.tabs.add(self.mon_tab, text="Frames RX")
            self.tabs.add(self.logs_tab, text="ESP logs (texto)")
            self.make_command_ui()
            self.make_monitor_ui()
            self.make_logs_ui()
            self.render_fields()
            self.refresh_ports()
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.root.after(60, self.drain_queue)

        def switch_esp(self, event=None):
            if self.serial is not None:
                return  # combobox e bloqueado enquanto conectado
            self.save_fields()
            idx = self.esp_cb.current()
            esp = list(ESP_LABELS.keys())[idx]
            self.selected.set(esp)
            self.port_var.set(DEFAULT_PORTS[esp])
            self.render_fields()

        def refresh_ports(self):
            found = list(DEFAULT_PORTS.values())
            try:
                from serial.tools import list_ports
                for info in list_ports.comports():
                    if info.device not in found:
                        found.append(info.device)
            except ImportError:
                pass
            self.port_cb["values"] = found

        def make_command_ui(self):
            tab = self.cmd_tab
            tab.columnconfigure(0, weight=1)
            self.cmd_desc = ttk.Label(tab, text="", wraplength=900)
            self.cmd_desc.grid(row=0, column=0, sticky="ew")
            self.fields_area = ttk.LabelFrame(tab, text="Variaveis a enviar", padding=10)
            self.fields_area.grid(row=1, column=0, sticky="ew", pady=(10, 6))
            self.fields_area.columnconfigure(1, weight=1)
            self.mask_lbl = ttk.Label(tab, text="")
            self.mask_lbl.grid(row=2, column=0, sticky="w", pady=(0, 9))

            ttk.Label(tab, text="PAYLOAD (hex):").grid(row=3, column=0, sticky="w")
            self.payload_box = tk.Text(tab, height=2, wrap="word",
                                       font=("DejaVu Sans Mono", 10))
            self.payload_box.grid(row=4, column=0, sticky="ew", pady=(2, 7))
            ttk.Label(tab, text="FRAME completo (HEX, pronto para GTKTerm):").grid(
                row=5, column=0, sticky="w")
            self.frame_box = tk.Text(tab, height=3, wrap="word",
                                     font=("DejaVu Sans Mono", 11))
            self.frame_box.grid(row=6, column=0, sticky="ew", pady=(2, 8))
            buttons = ttk.Frame(tab)
            buttons.grid(row=7, column=0, sticky="ew")
            self.copy_btn = ttk.Button(buttons, text="Copiar frame HEX", command=self.copy_frame)
            self.copy_btn.pack(side="left")
            self.send_btn = ttk.Button(buttons, text="Enviar direto pela porta", command=self.send_frame)
            self.send_btn.pack(side="left", padx=(8, 0))
            self.checksum_lbl = ttk.Label(tab, text="")
            self.checksum_lbl.grid(row=8, column=0, sticky="w", pady=(9, 3))
            self.command_feedback = ttk.Label(tab, text="", wraplength=880)
            self.command_feedback.grid(row=9, column=0, sticky="w", pady=(3, 0))
            ttk.Label(tab, text="Copiar HEX funciona sem conexao. Para monitorar e enviar diretamente, feche o GTKTerm e conecte aqui.",
                      wraplength=880).grid(row=10, column=0, sticky="w", pady=(11, 0))

        def build_text_monitor(self, tab):
            """Cada painel recebe widget e scrollbar independentes."""
            wrap = ttk.Frame(tab)
            wrap.grid(row=2, column=0, sticky="nsew")
            wrap.columnconfigure(0, weight=1)
            wrap.rowconfigure(0, weight=1)
            monitor = tk.Text(wrap, wrap="word", font=("DejaVu Sans Mono", 10),
                              state="disabled", bg="#fcfcfc")
            monitor.grid(row=0, column=0, sticky="nsew")
            yscroll = ttk.Scrollbar(wrap, orient="vertical", command=monitor.yview)
            yscroll.grid(row=0, column=1, sticky="ns")
            monitor["yscrollcommand"] = yscroll.set
            for tag, color in [("frame", "#084ea2"), ("log", "#202020"),
                               ("warning", "#925600"), ("log_partial", "#676767"),
                               ("error", "#ae2828"), ("raw", "#777777"),
                               ("tx", "#187b3e"), ("info", "#555555")]:
                monitor.tag_configure(tag, foreground=color)
            return monitor

        def make_monitor_ui(self):
            """Somente frames, erros de protocolo, RX HEX bruto e TX local."""
            tab = self.mon_tab
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(2, weight=1)
            opt = ttk.Frame(tab)
            opt.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            ttk.Checkbutton(opt, text="Exibir HEX bruto de todo RX", variable=self.show_raw).pack(side="left")
            ttk.Checkbutton(opt, text="Rolagem automatica", variable=self.auto_scroll).pack(side="left", padx=14)
            ttk.Button(opt, text="Limpar frames", command=self.clear_monitor).pack(side="right")
            ttk.Button(opt, text="Salvar frames .txt", command=self.save_monitor).pack(side="right", padx=8)
            ttk.Label(tab,
                      text="Somente frames decodificados, TX, erros de protocolo e (opcionalmente) RX bruto. "
                           "Mensagens ESP_LOGI/W/E ficam na aba ESP logs (texto).",
                      wraplength=900).grid(row=1, column=0, sticky="w", pady=(0, 8))
            self.monitor = self.build_text_monitor(tab)
            self.add_monitor("info", "Selecione a ESP, informe a porta e clique em Conectar.")

        def make_logs_ui(self):
            """Somente mensagens textuais vindas da ESP (sem inundacao dos frames)."""
            tab = self.logs_tab
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(2, weight=1)
            opt = ttk.Frame(tab)
            opt.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            ttk.Checkbutton(opt, text="Rolagem automatica", variable=self.auto_scroll_logs).pack(side="left")
            ttk.Button(opt, text="Limpar logs", command=self.clear_logs).pack(side="right")
            ttk.Button(opt, text="Salvar logs .txt", command=self.save_logs).pack(side="right", padx=8)
            ttk.Label(tab,
                      text="Mensagens de texto transmitidas pela UART0: ESP_LOGI, ESP_LOGW, ESP_LOGE e outros textos. "
                           "Este painel nao mostra frames, mesmo com telemetria em alta frequencia.",
                      wraplength=900).grid(row=1, column=0, sticky="w", pady=(0, 8))
            self.log_monitor = self.build_text_monitor(tab)
            self.add_log("info", "Aguardando conexao serial para receber mensagens ESP_LOG.")

        def save_fields(self):
            esp = self.selected.get()
            if esp not in ("right", "center"):
                return
            self.values[esp] = {k: v.get() for k, v in self.entries.items()}
            if esp == "center":
                self.checked = {k: v.get() for k, v in self.motor_checks.items()}

        def render_fields(self):
            for child in self.fields_area.winfo_children():
                child.destroy()
            self.entries = {}
            self.motor_checks = {}
            esp = self.selected.get()
            if esp == "left":
                self.cmd_desc["text"] = "ESP Left: o firmware fornecido tem somente uart_send(). Nao existe comando UART a gerar. Use o Monitor para receber os seis ultrassonicos e os ESP_LOGI."
                ttk.Label(self.fields_area, text="Somente recebimento de telemetria.\nSelecione ESP Right ou Center para gerar comandos.",
                          justify="left").grid(row=0, column=0, sticky="w")
            else:
                self.cmd_desc["text"] = ("ESP Right: envie quatro velocidades desejadas em rad/s." if esp == "right"
                                          else "ESP Center: habilite so os atuadores a comandar. A mascara e calculada automaticamente.")
                fields = RIGHT_CMD_FIELDS if esp == "right" else CENTER_CMD_FIELDS
                for row, f in enumerate(fields):
                    if esp == "center":
                        check_var = tk.BooleanVar(value=self.checked.get(f.key, False))
                        self.motor_checks[f.key] = check_var
                        ttk.Checkbutton(self.fields_area, text="Ativar (bit {})".format(MOTOR_BITS[f.key]),
                                        variable=check_var, command=self.refresh_command).grid(
                            row=row, column=0, sticky="w", padx=(0, 12), pady=5)
                    else:
                        ttk.Label(self.fields_area, text="Motor {}".format(row + 1)).grid(
                            row=row, column=0, sticky="w", padx=(0, 12), pady=5)
                    panel = ttk.Frame(self.fields_area)
                    panel.grid(row=row, column=1, sticky="ew", pady=4)
                    ttk.Label(panel, text=f.label, width=39).pack(side="left")
                    sv = tk.StringVar(value=self.values.get(esp, {}).get(f.key, "0"))
                    ent = ttk.Entry(panel, textvariable=sv, width=18)
                    ent.pack(side="left", padx=(6, 0))
                    self.entries[f.key] = sv
                    sv.trace_add("write", lambda *_: self.refresh_command())
            self.refresh_command()

        @staticmethod
        def set_box(box, data):
            box.delete("1.0", "end")
            box.insert("1.0", data)

        def refresh_command(self):
            esp = self.selected.get()
            self.frame = None
            self.payload = None
            if esp == "left":
                self.mask_lbl["text"] = ""
                self.checksum_lbl["text"] = ""
                self.command_feedback["text"] = "A ESP Left nao recebe comandos pelo protocolo informado."
                self.set_box(self.payload_box, "")
                self.set_box(self.frame_box, "")
            else:
                vals = {k: v.get() for k, v in self.entries.items()}
                enabled = {k: v.get() for k, v in self.motor_checks.items()}
                try:
                    payload, frame, mask = build_command(esp, vals, enabled)
                    self.payload, self.frame = payload, frame
                    self.set_box(self.payload_box, hex_spaced(payload))
                    self.set_box(self.frame_box, hex_spaced(frame))
                    self.checksum_lbl["text"] = ("Payload: {} bytes | Checksum: 0x{:02X} | Frame: {} bytes".format(
                        len(payload), frame[-2], len(frame)))
                    self.command_feedback["text"] = "Frame pronto."
                except ValueError as err:
                    self.set_box(self.payload_box, "")
                    self.set_box(self.frame_box, "")
                    self.checksum_lbl["text"] = ""
                    self.command_feedback["text"] = "Preenchimento: " + str(err)
                    mask = sum(MOTOR_BITS[k] for k, v in enabled.items() if v)
                self.mask_lbl["text"] = ("motor_mask = {} (0x{:02X})".format(mask, mask)
                                          if esp == "center" else "")
            self.copy_btn["state"] = "normal" if self.frame else "disabled"
            self.send_btn["state"] = "normal" if self.frame and self.serial else "disabled"

        def copy_frame(self):
            if not self.frame:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(hex_spaced(self.frame))
            self.root.update_idletasks()
            self.command_feedback["text"] = "Frame HEX copiado para a area de transferencia."

        def send_frame(self):
            if not self.frame or not self.serial:
                return
            try:
                n = self.serial.write(self.frame)
                if n != len(self.frame):
                    raise OSError("escrita parcial: {}/{} bytes".format(n, len(self.frame)))
                self.add_monitor("tx", "TX PC -> {} ({} B): {}".format(
                    self.selected.get().upper(), n, hex_spaced(self.frame)))
                self.command_feedback["text"] = "Comando transmitido localmente (nao e confirmacao de execucao)."
                self.tabs.select(self.logs_tab)
            except Exception as err:
                self.add_monitor("error", "Falha ao enviar UART: " + str(err))
                messagebox.showerror("Falha na UART", str(err))

        def toggle_connection(self):
            if self.serial is not None:
                self.disconnect()
            else:
                self.connect()

        def connect(self):
            # Caso a mesma janela ja esteja conectada, fechar primeiro.
            if self.serial is not None:
                self.disconnect()
            path = self.port_var.get().strip()
            if not path:
                messagebox.showwarning('Porta', 'Informe uma porta, como /dev/esp_center.')
                return
            try:
                import serial
            except ImportError:
                messagebox.showerror('PySerial nao encontrado',
                    'Instale: sudo apt install python3-serial')
                return
            self.session_id += 1
            this_session = self.session_id
            try:
                ser, lease = open_managed_serial(
                    path,
                    self.takeover_request.set)
            except (serial.SerialException, OSError, RuntimeError) as err:
                messagebox.showerror('Porta ocupada ou indisponivel', str(err))
                self.status_var.set('Falha ao abrir: {}'.format(path))
                return

            self.serial = ser
            self.lease = lease
            self.stop_event = threading.Event()
            self.rx_overflow.clear()
            self.takeover_request.clear()
            self.rx_bytes = self.rx_frames = self.rx_logs = self.rx_alerts = 0
            self.rx_connected_at = time.monotonic()
            self.rx_last_at = 0.0
            self.rx_no_data_warned = False
            self.rx_stats_var.set('RX: 0 bytes | 0 frames | 0 logs | 0 alertas (aguardando dados)')
            self.parser = MixedUARTParser(self.selected.get(), self.on_parser_event)
            self.conn_btn['text'] = 'Desconectar'
            self.port_cb.configure(state='disabled')
            self.esp_cb.configure(state='disabled')
            self.status_var.set('Conectado exclusivo em {} | {} 8N1 | {}'.format(
                path, BAUD_RATE, self.selected.get().upper()))
            self.add_monitor('info', 'Porta {} aberta de modo exclusivo.'.format(path))
            self.add_log('info', 'Conectado a {}. Monitor de logs ativo.'.format(path))
            self.reader = threading.Thread(
                target=self.read_worker, args=(ser, self.stop_event, this_session), daemon=True)
            self.reader.start()
            self.refresh_command()

        def read_worker(self, ser, stop_event, session_id):
            while not stop_event.is_set():
                try:
                    data = ser.read(ser.in_waiting or 1)
                    if data:
                        self.rx_queue.put_nowait(("rx", data, session_id))
                except queue.Full:
                    # A GUI ficou atrasada: nao garantir continuidade de bytes.
                    self.rx_overflow.set()
                except Exception as err:
                    if not stop_event.is_set():
                        try:
                            self.rx_queue.put_nowait(("serial_error", str(err), session_id))
                        except queue.Full:
                            self.rx_overflow.set()
                    break

        def disconnect(self):
            self.stop_event.set()
            self.session_id += 1
            ser, lease, reader = self.serial, self.lease, self.reader
            self.serial = self.lease = self.reader = None
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
            if reader is not None and reader.is_alive():
                reader.join(timeout=0.3)
            if self.parser is not None:
                self.parser.close()
            self.parser = None
            # Soltar lock SOMENTE depois que serial e reader forem fechados.
            if lease is not None:
                lease.close()
            self.conn_btn['text'] = 'Conectar'
            self.port_cb.configure(state='normal')
            self.esp_cb.configure(state='readonly')
            self.status_var.set('Desconectado')
            self.rx_stats_var.set('RX: desconectado')
            self.add_monitor('info', 'Porta fechada e lock liberado')
            self.add_log('info', 'Porta fechada e lock liberado')
            self.refresh_command()

        def on_parser_event(self, kind, value):
            if kind == "frame":
                self.rx_frames += 1
                raw, vals = value
                self.add_monitor("frame", "RX FRAME OK ({} bytes): {}".format(len(raw), hex_spaced(raw)))
                self.add_monitor("frame", "  " + describe_telemetry(self.selected.get(), vals))
            else:
                is_log = kind.startswith("log")
                if kind == "log" and re.match(r"^W\s*\(", value):
                    kind = "warning"
                elif kind == "log" and re.match(r"^E\s*\(", value):
                    kind = "error"
                if is_log:
                    self.rx_logs += 1
                    self.add_log(kind, "ESP_LOG: " + value)
                else:
                    self.rx_alerts += 1
                    self.add_monitor(kind, "RX: " + value)

        def drain_queue(self):
            try:
                if self.takeover_request.is_set():
                    self.takeover_request.clear()
                    if self.serial:
                        self.add_monitor('info', 'Nova instancia solicitou acesso: desconectando...')
                        self.add_log('info', 'Nova instancia solicitou acesso: desconectando...')
                        self.disconnect()
                if self.rx_overflow.is_set():
                    self.rx_overflow.clear()
                    self.add_monitor("error", "RX atrasado: bytes descartados pela fila; verifique perda de frames")
                    if self.parser:
                        self.parser = MixedUARTParser(self.selected.get(), self.on_parser_event)
                count = 0
                while count < 180:
                    try:
                        typ, value, session_id = self.rx_queue.get_nowait()
                    except queue.Empty:
                        break
                    count += 1
                    if session_id != self.session_id:
                        continue  # bytes de conexao anterior
                    if typ == "rx" and self.parser:
                        self.rx_bytes += len(value)
                        self.rx_last_at = time.monotonic()
                        if self.show_raw.get():
                            self.add_monitor("raw", "RX HEX bruto ({} B): {}".format(len(value), hex_spaced(value)))
                        self.parser.feed(value)
                    elif typ == "serial_error":
                        self.add_monitor("error", "Leitura serial interrompida: " + value)
                        self.add_log("error", "Leitura serial interrompida: " + value)
                        if self.serial:
                            self.disconnect()
                if self.parser:
                    self.parser.tick()

                if self.serial:
                    now = time.monotonic()
                    if self.rx_bytes == 0 and not self.rx_no_data_warned and \
                            now - self.rx_connected_at >= 3.0:
                        self.rx_no_data_warned = True
                        self.add_monitor("warning", "Sem bytes recebidos apos 3s: verifique porta, firmware e se o GTKTerm esta fechado.")
                        self.add_log("warning", "Porta aberta, mas nenhum byte RX apos 3s. Verifique se a ESP esta transmitindo pela UART0.")
                    if now - self.last_stats_update > 0.5:
                        idle = ""
                        if self.rx_last_at:
                            idle = " | ultimo RX ha {:.1f}s".format(now - self.rx_last_at)
                        self.rx_stats_var.set("RX: {} bytes | {} frames | {} logs | {} alertas{}".format(
                            self.rx_bytes, self.rx_frames, self.rx_logs, self.rx_alerts, idle))
                        self.last_stats_update = now
            finally:
                self.root.after(60, self.drain_queue)

        def append_text(self, widget, tag, line, auto_scroll):
            """Historico limitado, com rolagem independente por painel."""
            widget.configure(state="normal")
            stamp = time.strftime("%H:%M:%S")
            widget.insert("end", "[{}] {}\n".format(stamp, line), tag)
            lines = int(widget.index("end-1c").split(".")[0])
            if lines > self.max_display_lines:
                widget.delete("1.0", "500.0")
            widget.configure(state="disabled")
            if auto_scroll.get():
                widget.see("end")

        def add_monitor(self, tag, line):
            self.append_text(self.monitor, tag, line, self.auto_scroll)

        def add_log(self, tag, line):
            self.append_text(self.log_monitor, tag, line, self.auto_scroll_logs)

        @staticmethod
        def clear_text(widget):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.configure(state="disabled")

        def clear_monitor(self):
            self.clear_text(self.monitor)

        def clear_logs(self):
            self.clear_text(self.log_monitor)

        @staticmethod
        def save_text(widget, suggested_name):
            path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
                                                initialfile=suggested_name)
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(widget.get("1.0", "end-1c"))
            except OSError as err:
                messagebox.showerror("Falha ao salvar", str(err))

        def save_monitor(self):
            self.save_text(self.monitor, "uart_frames.txt")

        def save_logs(self):
            self.save_text(self.log_monitor, "esp_logs.txt")

        def on_close(self):
            self.disconnect() if self.serial else None
            self.root.destroy()

    try:
        root = tk.Tk()
    except tk.TclError as err:
        sys.exit("Nao foi possivel abrir janela: {}. Use --cli.".format(err))
    app = App(root)
    try:
        root.mainloop()
    finally:
        if app.serial is not None:
            app.disconnect()


def tests():
    class TestUART(unittest.TestCase):
        def test_right_cmd(self):
            payload, frame, mask = build_command("right", {"left_front_data": "1"})
            self.assertEqual((len(payload), len(frame), mask), (16, 19, 0))
            self.assertEqual(payload[:4], b"\x00\x00\x80\x3f")
            self.assertEqual(frame, pack_frame(payload))

        def test_center_cmd(self):
            payload, frame, mask = build_command("center", {"base_angle_deg": "90"},
                                                 {"base_angle_deg": True})
            self.assertEqual((len(payload), len(frame), mask), (17, 20, 2))
            self.assertEqual(struct.unpack("<Bffff", payload), (2, 0., 90., 0., 0.))

        def test_center_validation(self):
            with self.assertRaises(ValueError):
                build_command("center", {}, {})
            with self.assertRaises(ValueError):
                build_command("center", {"base_angle_deg": "361"}, {"base_angle_deg": True})
            with self.assertRaises(ValueError):
                build_command("left", {})

        def test_left_telemetry_and_log(self):
            got = []
            p = MixedUARTParser("left", lambda *item: got.append(item))
            rx_frame = pack_frame(struct.pack("<ffffff", 1, 2, 3, 4, 5, 6))
            p.feed(b"I (450) SENSOR: ultrassons atualizados\r\n" + rx_frame[:4])
            p.feed(rx_frame[4:] + b"I (451) MQTT: conectado\r\n")
            self.assertEqual(len([x for x in got if x[0] == "frame"]), 1)
            self.assertTrue(any(x[0] == "log" and "SENSOR" in x[1] for x in got))
            self.assertTrue(any(x[0] == "log" and "MQTT" in x[1] for x in got))
            self.assertEqual(got[1][1][1], (1., 2., 3., 4., 5., 6.))

        def test_right_rx(self):
            got = []
            p = MixedUARTParser("right", lambda *args: got.append(args))
            p.feed(pack_frame(struct.pack("<ffff", 1.5, -2., 3., 4.)))
            self.assertEqual(got[0][0], "frame")
            self.assertEqual(got[0][1][1], (1.5, -2., 3., 4.))

        def test_center_telemetry(self):
            got = []
            p = MixedUARTParser("center", lambda *args: got.append(args))
            frame = pack_frame(struct.pack("<ffBBB", 90., math.pi / 2, 0, 1, 1))
            self.assertEqual(len(frame), 14)
            p.feed(frame)
            self.assertEqual(got[0][0], "frame")
            self.assertEqual(got[0][1][1][2:], (0, 1, 1))

        def test_checksum_fail(self):
            got = []
            p = MixedUARTParser("right", lambda *args: got.append(args))
            frame = bytearray(pack_frame(struct.pack("<ffff", 1, 2, 3, 4)))
            frame[-2] ^= 0xAA
            p.feed(frame)
            self.assertEqual(len([x for x in got if x[0] == "frame"]), 0)
            self.assertTrue(any(x[0] == "error" for x in got))

        def test_bad_frame_then_good_frame(self):
            got = []
            p = MixedUARTParser("center", lambda *args: got.append(args))
            f = bytearray(pack_frame(struct.pack("<ffBBB", 1, 2, 1, 1, 0)))
            f[-1] = 0x66
            good = pack_frame(struct.pack("<ffBBB", 3, 4, 0, 1, 0))
            p.feed(f + good)
            self.assertEqual(len([x for x in got if x[0] == "frame"]), 1)
            self.assertEqual([x for x in got if x[0] == "frame"][0][1][1][0], 3.)

        def test_sof_and_eof_inside_payload(self):
            got = []
            p = MixedUARTParser("right", lambda *args: got.append(args))
            payload = b"\xAA\xBB\x00\x00" * 4  # payload pode conter delimitadores
            p.feed(pack_frame(payload))
            self.assertEqual(len([x for x in got if x[0] == "frame"]), 1)

        def test_incomplete_frame_timeout(self):
            got = []
            p = MixedUARTParser("right", lambda *args: got.append(args))
            p.feed(b"\xAA\x00\x00")
            p.last_byte_at = time.monotonic() - 1
            p.tick()
            self.assertTrue(any(x[0] == "error" and "timeout" in x[1] for x in got))
            p.feed(pack_frame(struct.pack("<ffff", 0., 1., 2., 3.)))
            self.assertEqual(len([x for x in got if x[0] == "frame"]), 1)

        def test_log_accented(self):
            got = []
            p = MixedUARTParser("right", lambda *args: got.append(args))
            p.feed("I (102) MAIN: velocidade recebida: direção\n".encode("utf-8"))
            self.assertEqual(got[0][1], "I (102) MAIN: velocidade recebida: direção")

        def test_lease_takes_and_releases_lock(self):
            import pty
            master, slave = pty.openpty()
            path = os.ttyname(slave)
            lease = SerialPortLease(path, lambda: None)
            try:
                lease.acquire()
                self.assertIsNotNone(lease.lockfd)
                lease.start_server()
                self.assertTrue(os.path.exists(lease.socket_path))
            finally:
                lease.close()
                os.close(slave)
                os.close(master)
            self.assertFalse(os.path.exists(lease.socket_path))

        def test_external_port_user_detected(self):
            import pty
            import multiprocessing
            master, slave = pty.openpty()
            path = os.ttyname(slave)
            ready = multiprocessing.Event()
            finish = multiprocessing.Event()

            def holder():
                fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
                ready.set()
                finish.wait(3)
                os.close(fd)

            proc = multiprocessing.Process(target=holder)
            proc.start()
            try:
                self.assertTrue(ready.wait(2))
                users = find_port_users(path)
                self.assertTrue(any(pid == proc.pid for pid, _ in users), users)
                lease = SerialPortLease(path, lambda: None)
                with self.assertRaisesRegex(RuntimeError, 'Porta ja aberta'):
                    lease.acquire()
            finally:
                finish.set()
                proc.join(timeout=2)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=1)
                os.close(slave)
                os.close(master)

        def test_old_instance_releases_cooperatively(self):
            import pty
            master, slave = pty.openpty()
            path = os.ttyname(slave)
            callback_fired = threading.Event()
            first = SerialPortLease(path, callback_fired.set)
            second = SerialPortLease(path, lambda: None)
            def release_worker():
                self.assertTrue(callback_fired.wait(1.5))
                first.close()
            try:
                first.acquire()
                first.start_server()
                th = threading.Thread(target=release_worker)
                th.start()
                second.acquire()
                self.assertIsNotNone(second.lockfd)
                th.join(timeout=2)
                self.assertFalse(th.is_alive())
            finally:
                first.close()
                second.close()
                os.close(slave)
                os.close(master)

        def test_flags_invalid(self):
            got = []
            p = MixedUARTParser("center", lambda *args: got.append(args))
            p.feed(pack_frame(struct.pack("<ffBBB", 90., 2., 3, 1, 1)))
            self.assertFalse(any(x[0] == "frame" for x in got))

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestUART))
    return result.wasSuccessful()


def main():
    ap = argparse.ArgumentParser(description="ESP32 UART: gerar hex, enviar, monitorar esp_log e telemetria")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="gerador de comandos via terminal")
    mode.add_argument("--test", action="store_true", help="testes de protocolo, sem hardware")
    mode.add_argument("--monitor", choices=("left", "right", "center"),
                      help="monitora telemetria e ESP_LOG pelo terminal (sem janela)")
    ap.add_argument("--port", help="porta serial, ex.: /dev/ttyUSB0 (usado com --monitor)")
    ap.add_argument("--raw", action="store_true", help="mostra todos os bytes RX em HEX no --monitor")
    args = ap.parse_args()
    if args.test:
        return 0 if tests() else 1
    if args.monitor:
        return monitor_cli(args.monitor, args.port, args.raw)
    if args.cli:
        cli()
    else:
        gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())