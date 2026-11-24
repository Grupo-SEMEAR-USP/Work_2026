#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, time, threading, collections
import yaml
import rospy
import rospkg
from robot_communication.msg import SchedulerCommand, SchedulerResponse

BURST_REPEATS = 8
BURST_RATE_HZ = 10
TASK_FILE_NAME = "BMT_seed219748_equipe.yaml"

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
            
            # nova forma do search_block
            # ("search_item",      "block,4-5-6,direita", True, 30),            # payload = tipo de item, identificação do item (número pra bloco, cor pra container), direção
            # ("search_item",      "container,red,direita", True, 30),

        ]

        self.plan = self.generate_plan_BMT()

    def generate_plan_BMT(self):

        task_path = os.path.join(rospkg.RosPack().get_path('robot_scheduler'), 'config', TASK_FILE_NAME)
        with open(task_path, 'r') as f:
            task = yaml.safe_load(f)

        start_state = task['start_state']
        finish_state = task['finish_state']

        # WS de start: a que começa com obj_ids não vazio; a outra é a de finish
        ws_start = next(ws for ws, s in start_state.items() if s.get('obj_ids'))
        ws_finish = next(ws for ws in start_state if ws != ws_start)

        # Blocos que saíram da WS de start entre o estado inicial e o final
        remaining = set(finish_state[ws_start].get('obj_ids') or [])
        blocks = [b for b in start_state[ws_start]['obj_ids'] if b not in remaining]   # vetor de ids
        blocks_formatted = "-".join(str(b) for b in blocks)                            # string do vetor tipo 1-2-3-...

        rospy.loginfo(f"[SCHEDULER] Task {task.get('task_id')}: {ws_start} -> {ws_finish}, blocos {blocks_formatted}")

        dist_approach = 10

        plan = [
            ("navigation", ws_start, True, 60),
            ("move", "parar", False, 2),     # Pausa dramática na mesa
            ("approach_table", f"{self.get_approach_type(ws_start)},{dist_approach}", True, 15),
            ("border_detect",       f"{self.get_border_detect_direction(ws_start)}",      True,  20),     # payload = pra qual lado fazer o alinhamento

            # ============== PEGAR BLOCOS ================
            # 1º primeiro bloco
            ("manipulation",     "rotatory_base,front",   False,  10.0),
            ("search_item",      f"block,{blocks_formatted},{self.get_search_item_direction(ws_start)}", True, 30),            # payload = tipo de item, identificação do item (número pra bloco, cor pra container), direção
            # ("align_block",       "5",      True,  60)              # payload = ID do bloco
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     f"arm,top_to_deposit{self.get_ws_height(ws_start)}",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),
            ("manipulation",     f"arm,deposit{self.get_ws_height(ws_start)}_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,deposit_left",   False,  10.0),
            ("manipulation",     "arm,top_to_deposit_put",   False,  10.0),
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),
            
            # 2º primeiro bloco
            ("manipulation",     "rotatory_base,front",   False,  10.0),
            ("search_item",      f"block,{blocks_formatted},{self.get_search_item_direction(ws_start)}", True, 30),            # payload = tipo de item, identificação do item (número pra bloco, cor pra container), direção
            # ("align_block",       "5",      True,  60)              # payload = ID do bloco
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     f"arm,top_to_deposit{self.get_ws_height(ws_start)}",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),
            ("manipulation",     f"arm,deposit{self.get_ws_height(ws_start)}_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,deposit_middle",   False,  10.0),
            ("manipulation",     "arm,top_to_deposit_put",   False,  10.0),
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),

            # 3º primeiro bloco
            ("manipulation",     "rotatory_base,front",   False,  10.0),
            ("search_item",      f"block,{blocks_formatted},{self.get_search_item_direction(ws_start)}", True, 30),            # payload = tipo de item, identificação do item (número pra bloco, cor pra container), direção
            # ("align_block",       "5",      True,  60)              # payload = ID do bloco
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     f"arm,top_to_deposit{self.get_ws_height(ws_start)}",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),
            ("manipulation",     f"arm,deposit{self.get_ws_height(ws_start)}_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,deposit_right",   False,  10.0),
            ("manipulation",     "arm,top_to_deposit_put",   False,  10.0),
            ("manipulation",     "gripper,open",   False,  10.0),
            # ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            # ("manipulation",     "gripper,close",   False,  10.0),

            # ============== COLOCAR BLOCOS ================
            ("navigation", ws_finish, True, 60),
            ("move", "parar", False, 2),     
            ("approach_table", f"front,{dist_approach}", True, 15),      # para colocar os blocos na ws, sempre de frente
            
            # acha a borda e vai um pouquinho pro lado, pra começar a colocar os blocos
            ("border_detect",       f"{self.get_border_detect_direction(ws_finish)}",      True,  20),     
            ("move", f"{self.get_search_item_direction}", False, 5),
                        
            ("manipulation",     "gripper,close",   False,  10.0),
            ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,front",   False,  10.0),
            ("manipulation",     f"arm,top_to_deposit{self.get_ws_height(ws_finish)}",   False,  10.0),
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     f"arm,deposit{self.get_ws_height(ws_finish)}_to_top",   False,  10.0),
            ("move", f"{self.get_search_item_direction}", False, 5),


            ("manipulation",     "rotatory_base,deposit_middle",   False,  10.0),
            ("manipulation",     "arm,top_to_deposit_pick",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),
            ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,front",   False,  10.0),
            ("manipulation",     f"arm,top_to_deposit{self.get_ws_height(ws_finish)}",   False,  10.0),
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     f"arm,deposit{self.get_ws_height(ws_finish)}_to_top",   False,  10.0),
            ("move", f"{self.get_search_item_direction}", False, 5),

            ("manipulation",     "rotatory_base,deposit_left",   False,  10.0),
            ("manipulation",     "arm,top_to_deposit_pick",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),
            ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,front",   False,  10.0),
            ("manipulation",     f"arm,top_to_deposit{self.get_ws_height(ws_finish)}",   False,  10.0),
            ("manipulation",     "gripper,open",   False,  10.0),
            ("manipulation",     f"arm,deposit{self.get_ws_height(ws_finish)}_to_top",   False,  10.0),
            ("manipulation",     "rotatory_base,deposit_middle",   False,  10.0),
            ("manipulation",     "gripper,close",   False,  10.0),

            ("navigation", "Finish", True, 60),
        ]

        return plan

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

    def get_search_item_direction(self, ws):
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