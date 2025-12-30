#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
from geometry_msgs.msg import Twist
from robot_communication.msg import SchedulerCommand, SchedulerResponse
from std_msgs.msg import String, Int32
import time

# Nome do executor que responde ao Scheduler
TARGET_NAME = "move"

class MoveTime:
    def __init__(self):
        rospy.init_node('move_time', anonymous=True)
        self.last_uid = None
        
        # Publicadores
        self.pub_cmd_vel = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        self.pub_feedback = rospy.Publisher('/scheduler/feedback', SchedulerResponse, queue_size=10)
        
        # Subscribers
        rospy.Subscriber('/scheduler/commands', SchedulerCommand, self._sched_cb)
        
        # Variáveis de Configuração de Velocidade
        self.lin_vel_x = 0.2    
        self.lin_vel_y = 0.2
        self.ang_vel_z = 0.6
        
        rospy.loginfo(f"[{TARGET_NAME.upper()}] Executor iniciado. Aguardando comandos Scheduler.")

    def _send_feedback(self, uid, status):
        fb_msg = SchedulerResponse(uid=uid, target=TARGET_NAME, status=status)
        self.pub_feedback.publish(fb_msg)
        rospy.loginfo(f"[{TARGET_NAME.upper()}] → Feedback enviado: UID={uid}, Status={status}")

    def _get_twist_command(self, direction):
        move_cmd = Twist()

        if direction == 'frente':
            move_cmd.linear.x = self.lin_vel_x
        elif direction == "parar":
            move_cmd.linear.x = 0
            move_cmd.linear.y = 0
            move_cmd.angular.z = 0
        elif direction == 'tras':
            move_cmd.linear.x = -self.lin_vel_x
        elif direction == 'esquerda':
            move_cmd.linear.y = self.lin_vel_y
        elif direction == 'direita':
            move_cmd.linear.y = -self.lin_vel_y
        elif direction == 'horario':
            move_cmd.angular.z = -self.ang_vel_z
        elif direction == 'antihorario':
            move_cmd.angular.z = self.ang_vel_z
        else:
            rospy.logwarn(f"[{TARGET_NAME.upper()}] Direção não reconhecida: {direction}")
            return None, False
            
        return move_cmd, True

    def _execute_move(self, direction, duration, uid, need_ack):
        
        move_cmd, success = self._get_twist_command(direction)
        if not success:
            if need_ack:
                self._send_feedback(uid, "FAIL")
            return

        rate = rospy.Rate(50)  # 50 Hz
        
        start_time = rospy.Time.now()
        duration_time = rospy.Duration(duration)

        rospy.loginfo(f"[{TARGET_NAME.upper()}] Executando: {direction} por {duration:.2f}s...")

        try:
            while rospy.Time.now() - start_time < duration_time and not rospy.is_shutdown():
                self.pub_cmd_vel.publish(move_cmd)
                rate.sleep()
            
            # Parar o robô após a duração
            self.pub_cmd_vel.publish(Twist()) 
            
            if need_ack:
                self._send_feedback(uid, "OK")

        except rospy.ROSInterruptException:
            # Garante que o robô pare em caso de interrupção
            self.pub_cmd_vel.publish(Twist())
            rospy.logerr(f"[{TARGET_NAME.upper()}] Movimento interrompido!")
            if need_ack:
                self._send_feedback(uid, "FAIL")

    def _sched_cb(self, msg: SchedulerCommand):
        
        # Filtra comandos que não são para este nó
        if msg.target != TARGET_NAME:
            return

        # Ignora burst commands repetidos
        if msg.uid == self.last_uid:
            return
        
        # Processa e Executa
        self.last_uid = msg.uid
        
        try:
            # O payload é a direção
            direction = msg.payload
            duration = msg.timeout # A duração do movimento é o timeout do Scheduler
            need_ack = msg.need_ack

            # Execução de movimento (bloqueante)
            self._execute_move(direction, duration, msg.uid, need_ack)
            
        except Exception as e:
            rospy.logerr(f"[{TARGET_NAME.upper()}] Erro no processamento do comando UID={msg.uid}: {str(e)}")
            if msg.need_ack:
                self._send_feedback(msg.uid, "FAIL")

    def run(self):
        rospy.spin()

if __name__ == '__main__':
    try:
        executor = MoveTime()
        executor.run()
    except rospy.ROSInterruptException:
        pass