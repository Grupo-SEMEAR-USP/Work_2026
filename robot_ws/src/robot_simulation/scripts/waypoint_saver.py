#!/usr/bin/env python3
import rospy
import yaml
import os
import rospkg
from geometry_msgs.msg import PoseStamped

# Define onde salvar. Usando rospkg para achar a pasta do pacote automaticamente
rospack = rospkg.RosPack()

PACKAGE_PATH = rospack.get_path('robot_scheduler') 
FILE_PATH = os.path.join(PACKAGE_PATH, 'config', 'points.yaml')

class WaypointSaver:
    def __init__(self):
        rospy.init_node('waypoint_saver')
        self.points = {}

        # Tenta carregar pontos existentes para não perder o que já gravou
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH, 'r') as f:
                self.points = yaml.safe_load(f) or {}
            rospy.loginfo(f"Carregados {len(self.points)} pontos existentes de {FILE_PATH}")
        else:
            rospy.loginfo(f"Criando novo arquivo em: {FILE_PATH}")

        # Escuta o clique do RViz
        rospy.Subscriber("/move_base_simple/goal", PoseStamped, self.save_cb)
        rospy.loginfo("--- AGUARDANDO '2D Nav Goal' NO RVIZ ---")

    def save_cb(self, msg):
        print("\nCoordenada recebida!")
        name = input("Digite o nome para este ponto (ex: WS1, Start, Base): ").strip()
        
        if not name:
            print("Nome vazio. Ponto ignorado.")
            return

        # Estrutura do dado
        point_data = {
            'x': msg.pose.position.x,
            'y': msg.pose.position.y,
            'z': msg.pose.position.z,
            'qx': msg.pose.orientation.x,
            'qy': msg.pose.orientation.y,
            'qz': msg.pose.orientation.z,
            'qw': msg.pose.orientation.w
        }

        self.points[name] = point_data
        
        # Salva no arquivo
        os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
        with open(FILE_PATH, 'w') as f:
            yaml.dump(self.points, f)
            
        print(f"Ponto '{name}' salvo! Total de pontos: {len(self.points)}")

if __name__ == '__main__':
    WaypointSaver()
    rospy.spin()