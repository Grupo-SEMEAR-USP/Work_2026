#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, time, threading, heapq, itertools, math
import yaml
import rospy
import rospkg
from robot_communication.msg import SchedulerCommand, SchedulerResponse

BURST_REPEATS = 8
BURST_RATE_HZ = 10
TASK_FILE_NAME = "BMT_seed219748_equipe.yaml"   # padrão; pode ser trocado pelo param ~task_file

# Depósitos do robô, na ordem em que são preenchidos
DEPOSIT_SLOTS = ["deposit_left", "deposit_middle", "deposit_right"]
DIST_APPROACH = 10   # cm

class Scheduler:
    def __init__(self):
        # Tópicos
        self.pub_cmd = rospy.Publisher("/scheduler/commands",
                                       SchedulerCommand, queue_size=30)
        rospy.Subscriber("/scheduler/feedback",
                         SchedulerResponse, self._fb_cb, queue_size=30)

        self.rate = rospy.Rate(BURST_RATE_HZ)
        self._pending = {} 
        self.index = 0 

        # ---------------------------------------------------------
        # PLANO DE AÇÕES DO ROBÔ
        # Estrutura: (target, payload, expect_ack, timeout)
        # ---------------------------------------------------------
        self.plan = [
            # Inicia no Start
            # Navegação para WS1
            # ("navigation", "WS1", True, 60), # Timeout longo para nav
            # ("move", "parar", False, 2),     # Pausa dramática na mesa

            # Navegação para WS2
            # ("navigation", "WS2", True, 60),
            # ("move", "parar", False, 2),

            # Navegação para WS3
            # ("navigation", "WS3", True, 60),
            # ("move", "parar", False, 2),
            
            # Volta para Start
            # ("navigation", "Start", True, 60),
            # ("move", "parar", False, 2)
            # Fim do plano

            # ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            # ("manipulation",     "rotatory_base,front",   False,  10.0),
            # ("approach_table", "front,10", True, 15),      # front, right ou left, distância da mesa
            # ("move", "parar", False, 1),
            # ("navigation",       "WS1",      True,  30)
            
            # ("align_block",       "5",      True,  60),              # payload = ID do bloco
            # ("border_detect",       "esquerda",      True,  20),     # payload = pra qual lado fazer o alinhamento
            # ("move",                "frente",      True,  20),       # payload = direção do omvimento do robô (frente, para, tras, esquerda, direita, horario, antihorario)
            # ("search_block",      "4,direita", True, 30),           # payload = ID do bloco, direção do movimento
            
            # nova forma do search_block (n implementada ainda -- só na bracnh visao)
            # ("search_block",      "block, 4-5-6,direita", True, 30),            # payload = tipo de item, identificação do item (número pra bloco, cor pra container), direção
            # ("search_block",      "container,red,direita", True, 30),

        ]

        task_file = rospy.get_param("~task_file", TASK_FILE_NAME)
        self.waypoints = self.load_waypoints()
        self.plan = self.generate_plan(self.load_task(task_file))

    # =====================================================================
    # LEITURA DO ARQUIVO DE TASK
    # =====================================================================
    @staticmethod
    def config_path(file_name):
        if os.path.isabs(file_name):
            return file_name
        return os.path.join(rospkg.RosPack().get_path('robot_scheduler'), 'config', file_name)

    def load_task(self, file_name):
        with open(self.config_path(file_name), 'r') as f:
            return yaml.safe_load(f)

    def load_waypoints(self):
        """Pontos de navegação (points.yaml): usados só pra estimar distâncias da rota."""
        try:
            with open(self.config_path('points.yaml'), 'r') as f:
                return yaml.safe_load(f) or {}
        except (IOError, OSError, yaml.YAMLError):
            rospy.logwarn("[SCHEDULER] points.yaml não encontrado: rota escolhida sem distâncias")
            return {}

    @staticmethod
    def get_transports(task):
        """Compara start_state x finish_state e devolve [(id, ws_origem, ws_destino)]
        só dos objetos que mudam de área (obj_ids lista TODOS os objetos de cada área)."""
        def where(state):
            loc = {}
            for ws, s in (state or {}).items():
                for obj in (s or {}).get('obj_ids') or []:
                    loc[obj] = ws
            return loc

        start = where(task['start_state'])
        finish = where(task['finish_state'])

        transports = []
        for obj in sorted(start):
            if obj not in finish:
                rospy.logwarn(f"[SCHEDULER] Objeto {obj} não aparece no finish_state: ignorado")
                continue
            if start[obj] == finish[obj]:
                continue   # fica onde está (ex.: bloco 5 no BMT de teste)
            dst_state = task['finish_state'][finish[obj]]
            if obj not in (dst_state.get('table') or []):
                rospy.logwarn(f"[SCHEDULER] Objeto {obj} não termina solto na mesa de {finish[obj]} "
                              f"(container/prateleira/slot/pilha ainda não implementado): será só colocado na mesa")
            transports.append((obj, start[obj], finish[obj]))
        return transports

    # =====================================================================
    # PLANEJAMENTO DA ROTA
    # =====================================================================
    def _distance(self, a, b):
        pa, pb = self.waypoints.get(a), self.waypoints.get(b)
        if not pa or not pb:
            return 0.0
        return math.hypot(pa['x'] - pb['x'], pa['y'] - pb['y'])

    def plan_route(self, transports):
        """Busca a sequência de visitas às WS com o MENOR número de paradas (desempate:
        menor distância pelos pontos do points.yaml), respeitando os 3 depósitos.

        Devolve [(ws, ids_para_pegar, ids_para_colocar), ...]
        """
        src = {o: s for o, s, _ in transports}
        dst = {o: d for o, _, d in transports}
        areas = list(dict.fromkeys([s for _, s, _ in transports] + [d for _, _, d in transports]))
        all_objs = frozenset(src)
        cap = len(DEPOSIT_SLOTS)

        # estado = (onde o robô está, objetos carregados, objetos já entregues)
        start = ("Start", frozenset(), frozenset())
        tie = itertools.count()
        heap = [(0, 0.0, next(tie), start, [])]
        visited = set()
        while heap:
            n_visits, dist, _, state, visits = heapq.heappop(heap)
            if state in visited:
                continue
            visited.add(state)
            loc, carried, done = state
            if done == all_objs:
                return visits

            for ws in areas:
                if ws == loc:
                    continue
                places = frozenset(o for o in carried if dst[o] == ws)
                available = sorted(o for o in all_objs - carried - done if src[o] == ws)
                free = cap - len(carried) + len(places)
                for k in range(min(free, len(available)), -1, -1):
                    for picks in itertools.combinations(available, k):
                        if not picks and not places:
                            continue   # visita inútil
                        new_state = (ws, (carried - places) | frozenset(picks), done | places)
                        if new_state in visited:
                            continue
                        heapq.heappush(heap, (n_visits + 1, dist + self._distance(loc, ws), next(tie),
                                              new_state, visits + [(ws, list(picks), sorted(places))]))
        return None

    # =====================================================================
    # GERAÇÃO DO PLANO (BMT, BTT1, BTT2)
    # =====================================================================
    def generate_plan(self, task):
        """BMT é o caso particular de 1 WS de origem -> 1 WS de destino;
        BTT1/BTT2 têm várias origens/destinos. O mesmo gerador serve pros três."""
        task_id = task.get('task_id')
        if task_id not in ("BMT", "BTT1", "BTT2"):
            rospy.logerr(f"[SCHEDULER] Task '{task_id}' não suportada")
            return []

        transports = self.get_transports(task)
        dest = {o: d for o, _, d in transports}
        for obj, s, d in transports:
            rospy.loginfo(f"[SCHEDULER] Task {task_id}: bloco {obj}: {s} -> {d}")

        visits = self.plan_route(transports)
        if visits is None:
            rospy.logerr(f"[SCHEDULER] Não foi possível montar uma rota para a task {task_id}")
            return []

        # carrying: depósito -> WS de destino do bloco guardado nele
        # arm_at:   depósito onde o braço ficou parado com a garra aberta (ou None)
        st = {'carrying': {}, 'arm_at': None, 'gripper_open': False}
        plan = []
        for ws, picks, places in visits:
            rospy.loginfo(f"[SCHEDULER] Visita {ws}: pegar {picks or '-'} | colocar {places or '-'}")

            plan += [
                ("navigation", ws, True, 60),
                ("move", "parar", False, 2),     # Pausa dramática na mesa
                # para só colocar os blocos na ws, sempre de frente
                ("approach_table", f"{self.get_approach_type(ws) if picks else 'front'},{DIST_APPROACH}", True, 15),
            ]

            # Pega primeiro (libera a mesa antes de colocar blocos nela), a não ser
            # que não caiba nos depósitos: aí coloca primeiro pra liberar espaço.
            if len(st['carrying']) + len(picks) <= len(DEPOSIT_SLOTS):
                plan += self.pick_phase(ws, picks, dest, st)
                plan += self.place_phase(ws, st)
            else:
                plan += self.place_phase(ws, st)
                plan += self.pick_phase(ws, picks, dest, st)

        plan += self.release_arm(st)
        plan += [
            # estaciona o braço
            ("manipulation",     "rotatory_base,deposit_middle",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),

            ("navigation", "Finish", True, 60),
        ]
        return plan

    def pick_phase(self, ws, picks, dest, st):
        """Pega os blocos `picks` da WS, um depósito livre para cada.

        A busca é feita por grupo de destino: o search_block recebe todos os IDs que vão
        pra mesma WS e pega o primeiro que achar, então o scheduler sabe pra onde vai
        cada depósito mesmo sem saber qual ID exato ficou nele.
        """
        if not picks:
            return []
        routine = [("border_detect", self.get_border_detect_direction(ws), True, 20)]   # payload = pra qual lado fazer o alinhamento

        groups = {}
        for obj in picks:
            groups.setdefault(dest[obj], []).append(obj)

        for dst, ids in groups.items():
            ids_formatted = "-".join(str(b) for b in ids)   # string do vetor tipo 1-2-3-...
            for _ in ids:
                slot = next(s for s in DEPOSIT_SLOTS if s not in st['carrying'])
                routine += self.release_arm(st)
                # braço fica no depósito com a garra aberta: se o próximo passo for tirar
                # esse mesmo bloco, economiza a subida/descida
                routine += self.pick_block_routine(ws, ids_formatted, slot, return_arm=False)
                st['carrying'][slot] = dst
                st['arm_at'] = slot
                st['gripper_open'] = True
        return routine

    def place_phase(self, ws, st):
        """Coloca na WS todos os blocos carregados que têm ela como destino."""
        slots = [s for s in reversed(DEPOSIT_SLOTS) if st['carrying'].get(s) == ws]   # direita -> esquerda
        if not slots:
            return []
        if st['arm_at'] in slots:   # começa pelo depósito onde o braço já está
            slots.remove(st['arm_at'])
            slots.insert(0, st['arm_at'])

        routine = [
            # acha a borda e vai um pouquinho pro lado, pra começar a colocar os blocos
            ("border_detect", self.get_border_detect_direction(ws), True, 20),
            ("move", self.get_search_block_direction(ws), False, 5),
        ]
        for i, slot in enumerate(slots):
            arm_in_deposit = (st['arm_at'] == slot)
            if not arm_in_deposit:
                routine += self.release_arm(st)
            routine += self.place_block_routine(ws, slot,
                                                arm_in_deposit=arm_in_deposit,
                                                open_gripper=not arm_in_deposit and not st['gripper_open'],
                                                move_after=(i < len(slots) - 1))   # último: não anda pro lado depois
            del st['carrying'][slot]
            st['arm_at'] = None
            st['gripper_open'] = True   # place termina com o braço em cima e a garra aberta
        return routine

    def release_arm(self, st):
        """Se o braço ficou parado num depósito, volta pro topo e fecha a garra."""
        if st['arm_at'] is None:
            return []
        st['arm_at'] = None
        st['gripper_open'] = False
        return [
            ("manipulation", "arm,deposit_to_top",         False, 10.0),
            ("manipulation", "gripper,close",              False, 10.0),
        ]

    def pick_block_routine(self, ws, blocks_formatted, deposit_slot, return_arm=True):
        """Procura um bloco na WS, pega e guarda no depósito indicado.

        deposit_slot: deposit_left, deposit_middle ou deposit_right
        return_arm:   se True, volta o braço pro topo e fecha a garra no final
        """
        h = self.get_ws_height(ws)
        routine = [
            ("manipulation", "rotatory_base,front",            False, 10.0),
            ("search_block", f"{blocks_formatted},{self.get_search_block_direction(ws)}", True, 30),  # search_block chama o align_block sozinho
            ("manipulation", "gripper,open",                   False, 10.0),
            ("manipulation", f"arm,top_to_bottom{h}",          False, 10.0),
            ("manipulation", "gripper,close",                  False, 10.0),
            ("manipulation", f"arm,bottom{h}_to_top",          False, 10.0),
            ("manipulation", f"rotatory_base,{deposit_slot}",  False, 10.0),
            ("manipulation", "arm,top_to_deposit_put",         False, 10.0),
            ("manipulation", "gripper,open",                   False, 10.0),
        ]
        if return_arm:
            routine += [
                ("manipulation", "arm,deposit_to_top",         False, 10.0),
                ("manipulation", "gripper,close",              False, 10.0),
            ]
        return routine

    def place_block_routine(self, ws, deposit_slot, arm_in_deposit=False, open_gripper=False, move_after=True):
        """Pega um bloco do depósito indicado e coloca na WS.

        deposit_slot:   deposit_left, deposit_middle ou deposit_right
        arm_in_deposit: se True, o braço já está no depósito com a garra aberta
                        (caso do último bloco pego), então só fecha a garra
        open_gripper:   se True, abre a garra antes de descer no depósito
                        (necessário quando ela foi fechada no topo)
        move_after:     se True, anda pro lado no final pra abrir espaço pro próximo bloco
        """
        h = self.get_ws_height(ws)
        routine = []
        if not arm_in_deposit:
            routine.append(("manipulation", f"rotatory_base,{deposit_slot}", False, 10.0))
            if open_gripper:
                routine.append(("manipulation", "gripper,open",              False, 10.0))
            routine.append(("manipulation", "arm,top_to_deposit_pick",       False, 10.0))
        routine += [
            ("manipulation", "gripper,close",                  False, 10.0),
            ("manipulation", "arm,deposit_to_top",             False, 10.0),
            ("manipulation", "rotatory_base,front",            False, 10.0),
            ("manipulation", f"arm,top_to_bottom{h}",          False, 10.0),
            ("manipulation", "gripper,open",                   False, 10.0),
            ("manipulation", f"arm,bottom{h}_to_top",          False, 10.0),
        ]
        if move_after:
            routine.append(("move", self.get_search_block_direction(ws), False, 5))
        return routine

    # Completamente de exemplo -- VERIFICAR NA ARENA
    def get_approach_type(self, ws):
        if ws in ["WS_1", "WS_2", "WS_3", "WS_4"]:
            return "front"
        elif ws in ["WS_5", "WS_6", "WS_7"]:
            return "right"
        else:
            return "left"

    # Completamente de exemplo -- VERIFICAR NA ARENA
    def get_border_detect_direction(self, ws):
        if ws in ["WS_1", "WS_2", "WS_3", "WS_4"]:
            return "direita"
        else:
            return "esquerda"

    def get_search_block_direction(self, ws):
        return "esquerda" if self.get_border_detect_direction(ws) == "direita" else "direita"

    # Completamente de exemplo -- VERIFICAR NA ARENA
    def get_ws_height(self, ws):
        if ws in ["WS_1", "WS_2", "WS_3", "WS_4"]:
            return 0
        elif ws in ["WS_5", "WS_6", "WS_7"]:
            return 10
        else:
            return 15

    @staticmethod
    def new_uid():
        return int(time.time() * 1e6)

    def _send_burst(self, target, payload, need_ack, timeout):
        uid = self.new_uid()
        cmd = SchedulerCommand()
        cmd.uid = uid
        cmd.target = target
        cmd.payload = payload
        cmd.need_ack = need_ack
        cmd.timeout = float(timeout) # Garante que seja float

        for _ in range(BURST_REPEATS):
            self.pub_cmd.publish(cmd)
            self.rate.sleep()

        rospy.loginfo(f"[SCHEDULER] → {target} uid={uid} ack={need_ack}")
        return uid
    
    def _fb_cb(self, fb: SchedulerResponse):
        # Recupera o evento de espera associado a este UID
        ev = self._pending.get(fb.uid)
        
        if ev:
            status = fb.status.upper()
            
            # Faz a verificação: o status precisa ser 'OK' para liberar a espera
            if status == "OK":
                rospy.loginfo(f"[SCHEDULER] <<< Sucesso: {fb.target} (uid={fb.uid})")
                ev.set() # Libera o wait_ack
            
            elif status == "FAIL":
                rospy.logwarn(f"[SCHEDULER] <<< FALHA relatada pelo nó: {fb.target} (uid={fb.uid})")
                ev.set() # Libera o wait_ack, mas é possível tratar isso melhor futuramente

            elif status == "SKIP":
                rospy.loginfo(f"[SCHEDULER] <<< SKIP: {fb.target}")
                self.index += 1 # Pula lógica interna


    def wait_ack(self, uid, timeout):
        ev = threading.Event()
        self._pending[uid] = ev
        ok = ev.wait(timeout)
        self._pending.pop(uid, None)
        return ok

    def run(self):
        rospy.loginfo("Scheduler iniciado. Aguardando para estabilizar o sistema")
        rospy.sleep(5) # Dá tempo pro navigation.py setar a pose inicial

        self.index = 0
        while not rospy.is_shutdown():
            if self.index >= len(self.plan):
                break

            task = self.plan[self.index]
            target, payload, expect_ack, t_limit = task

            # Envia comando
            uid = self._send_burst(target, payload, expect_ack, t_limit)

            # Lógica de Espera
            if expect_ack:
                rospy.loginfo(f"[SCHEDULER] Aguardando confirmação... (Max {t_limit}s)")
                if not self.wait_ack(uid, t_limit):
                    rospy.logwarn(f"[SCHEDULER] TIMEOUT: Não recebeu OK para {target} (uid={uid})")
            else:
                # Comandos open-loop (como mover tempo) apenas dormem
                rospy.sleep(t_limit)

            self.index += 1

        rospy.loginfo("[SCHEDULER] PLANO CONCLUÍDO!")

if __name__ == "__main__":
    rospy.init_node("scheduler")
    Scheduler().run()