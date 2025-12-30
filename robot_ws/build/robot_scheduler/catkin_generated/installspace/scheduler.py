#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time, threading, collections
import rospy
from robot_communication.msg import SchedulerCommand, SchedulerResponse

BURST_REPEATS = 8
BURST_RATE_HZ = 10

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
            ("navigation", "WS1", True, 60), # Timeout longo para nav
            ("move", "parar", False, 2),     # Pausa dramática na mesa

            # Navegação para WS2
            ("navigation", "WS2", True, 60),
            ("move", "parar", False, 2),

            # Navegação para WS3
            ("navigation", "WS3", True, 60),
            ("move", "parar", False, 2),
            
            # Volta para Start
            ("navigation", "Start", True, 60),
            ("move", "parar", False, 2)
            # Fim do plano

            # ("manipulation",     "arm,deposit_to_top",   False,  10.0),
            # ("align_table", "10", True, 15),
            # ("search_block",      "4,direita", True, 30),
            # ("move", "parar", False, 1),
            # ("navigation",       "WS1",      True,  30)
        ]

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