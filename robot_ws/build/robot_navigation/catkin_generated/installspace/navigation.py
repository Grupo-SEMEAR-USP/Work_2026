#!/usr/bin/env python3
import rospy
import actionlib
import yaml
import os
import rospkg
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseWithCovarianceStamped
from robot_communication.msg import SchedulerCommand, SchedulerResponse

class NavigationNode:
    def __init__(self):
        rospy.init_node("navigation_node")
        
        self.last_processed_uid = None

        # Carrega o arquivo YAML
        rospack = rospkg.RosPack()
        
        self.file_path = os.path.join(rospack.get_path('robot_scheduler'), 'config', 'points.yaml')
        self.waypoints = {}
        
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                self.waypoints = yaml.safe_load(f) or {}
            rospy.loginfo(f"Carregados {len(self.waypoints)} pontos.")
        else:
            rospy.logerr(f"ARQUIVO {self.file_path} NÃO ENCONTRADO!")

        # Configurar Move Base Client
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        rospy.loginfo("Aguardando move_base server...")
        self.client.wait_for_server()
        rospy.loginfo("Conectado ao move_base.")

        # Publicadores e Assinantes do Scheduler
        self.pub_fb = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)
        self.pub_initial_pose = rospy.Publisher('/initialpose', PoseWithCovarianceStamped, queue_size=1, latch=True)
        
        rospy.Subscriber("/scheduler/commands", SchedulerCommand, self.command_cb)

        # Automaticamente define a pose inicial
        # Se existir um ponto chamado 'Start' ou 'INITIAL_POSE' no yaml, ele usa.
        self.set_initial_pose("Start") 

    def set_initial_pose(self, point_name):
        if point_name not in self.waypoints:
            rospy.logwarn(f"Ponto de inicialização '{point_name}' não encontrado no YAML. Configure manualmente no RViz.")
            return

        data = self.waypoints[point_name]
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = rospy.Time.now()
        
        # Posição
        msg.pose.pose.position.x = data['x']
        msg.pose.pose.position.y = data['y']
        msg.pose.pose.position.z = data['z']
        msg.pose.pose.orientation.x = data['qx']
        msg.pose.pose.orientation.y = data['qy']
        msg.pose.pose.orientation.z = data['qz']
        msg.pose.pose.orientation.w = data['qw']
        
        # Covariância (Confiança): Diagonal principal com valores baixos = alta confiança
        cov = [0.0] * 36
        cov[0] = 0.25  # X
        cov[7] = 0.25  # Y
        cov[35] = 0.06 # Yaw (rotação)
        msg.pose.covariance = cov

        rospy.sleep(1.0) # Espera conexões
        self.pub_initial_pose.publish(msg)
        rospy.loginfo(f"*** POSE INICIAL DEFINIDA AUTOMATICAMENTE PARA '{point_name}' ***")

    def command_cb(self, msg: SchedulerCommand):
        # Filtra comandos apenas para este nó
        if msg.target != "navigation":
            return
        
        if self.last_processed_uid == msg.uid:
            # rospy.logdebug(f"[NAV] Ignorando comando duplicado UID: {msg.uid}")
            return
        
        self.last_processed_uid = msg.uid

        point_name = msg.payload
        rospy.loginfo(f"[NAV] Comando recebido: Ir para '{point_name}' (UID: {msg.uid})")

        if point_name not in self.waypoints:
            rospy.logwarn(f"[NAV] Ponto '{point_name}' desconhecido!")
            self.send_feedback(msg.uid, point_name, "FAIL")
            return

        # Executa a navegação
        result_status = self.go_to_point(point_name)
        
        # Responde ao Scheduler
        status_str = "OK" if result_status else "FAIL"
        self.send_feedback(msg.uid, point_name, status_str)

    def go_to_point(self, name):
        data = self.waypoints[name]
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        
        goal.target_pose.pose.position.x = data['x']
        goal.target_pose.pose.position.y = data['y']
        goal.target_pose.pose.position.z = data['z']
        goal.target_pose.pose.orientation.x = data['qx']
        goal.target_pose.pose.orientation.y = data['qy']
        goal.target_pose.pose.orientation.z = data['qz']
        goal.target_pose.pose.orientation.w = data['qw']

        self.client.send_goal(goal)
        self.client.wait_for_result()
        
        state = self.client.get_state()
        return state == GoalStatus.SUCCEEDED

    def send_feedback(self, uid, target, status):
        resp = SchedulerResponse()
        resp.uid = uid
        resp.target = target
        resp.status = status
        self.pub_fb.publish(resp)

if __name__ == "__main__":
    NavigationNode()
    rospy.spin()