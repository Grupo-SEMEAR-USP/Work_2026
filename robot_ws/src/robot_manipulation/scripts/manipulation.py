#!/usr/bin/env python3
import rospy
from std_msgs.msg import Float32MultiArray
from robot_communication.msg import SchedulerCommand, SchedulerResponse
from robot_communication.msg import manipulation_comm


TARGET_NAME = "manipulation"

arm_vals = [0.0, 0.0] #[base, arm]
ee_vals = [0.0, 0.0] #[wrist, gripper]

ACTION_MAP = {
    "gripper": {
        "open": 15.0, #270 é o max da garra (tava 160.0)
        "close": 1.0 #0 é o min da garra (tava 10.0 - valor com o bloco)
    },
    "wrist": {
        "center": 80.0,
    },
    "rotatory_base": {
        # valores de ângulo mockados por enquanto

        "deposit_left": 15.0,
        "deposit_middle": 0.0,  
        "deposit_right": 345.0,
        "front": 180.0,
        "back": 0.0,
        "left": 90.0,
        "right": 270.0,
    },
    "arm": {
        "top": 40028922.0,  # playstation!

        # Alterar esses valores para centímetros 
        "deposit_to_top": 10100.0,
        "top_to_deposit": -10100.0,
        
        "top_to_deposit_put": -9600.0,
        "top_to_deposit_pick": -9900.0,

        "top_to_bottom0": -14400.0,
        "bottom0_to_top": 14400.0,
        "top_to_bottom5": -12100.0,
        "bottom5_to_top": 12100.0,
        "top_to_bottom10": -10200.0,
        "bottom10_to_top": 10200.0,
        "top_to_bottom15": -8000.0,
        "bottom15_to_top": 8000.0, #botton15 = altura da mesa de 15

        "bottom15_to_deposit": -2900.0, #medidas intermediarias

        "deposit_to_bottom10": -1.0,
    }
}

class ManipulationInterface:
    def __init__(self):
        self.last_processed_uid = None

        rospy.init_node("manipulation")

        self.pub_arm = rospy.Publisher("/arm_control", Float32MultiArray, queue_size=10)
        self.pub_ee = rospy.Publisher("/end_effector_control", Float32MultiArray, queue_size=10)
        self.pub_fb = rospy.Publisher("/scheduler/feedback", SchedulerResponse, queue_size=10)

        rospy.Subscriber("/manipulator_state", manipulation_comm, self.cb_manipulator_state, queue_size=10)
        rospy.Subscriber("/scheduler/commands",
                         SchedulerCommand, self.cb_command, queue_size=10)

        rospy.loginfo("[manipulation] Inicializado e aguardando comandos...")

    def cb_command(self, msg):
        if msg.target != TARGET_NAME:
            return

        if self.last_processed_uid == msg.uid:
            # rospy.logdebug(f"[manipulation] Ignorando comando duplicado UID: {msg.uid}")
            return
        
        self.last_processed_uid = msg.uid

        rospy.loginfo(f"[manipulation] Recebido uid={msg.uid} payload='{msg.payload}'")

        parts = [p.strip().lower() for p in msg.payload.split(",")]
        if len(parts) != 2:
            rospy.logerr("Payload inválido. Esperado formato: '<componente>, <ação>'")
            return

        component, action = parts

        if component not in ACTION_MAP:
            rospy.logerr(f"Componente desconhecido: '{component}'")
            return

        if action not in ACTION_MAP[component]:
            rospy.logerr(f"Ação desconhecida: '{action}' para componente '{component}'")
            return

        value = ACTION_MAP[component][action]

        if component in ["rotatory_base", "arm"]:
            idx = 0 if component == "rotatory_base" else 1
            arm_vals[idx] = value
            self.pub_arm.publish(Float32MultiArray(data=arm_vals))
            rospy.loginfo(f"[manipulation] Publicado arm_control: {arm_vals}")
        else:
            idx = 0 if component == "wrist" else 1
            ee_vals[idx] = value
            self.pub_ee.publish(Float32MultiArray(data=ee_vals))
            rospy.loginfo(f"[manipulation] Publicado end_effector_control: {ee_vals}")

    def cb_manipulator_state(self, msg):
        # Aqui: recebe os valores de ângulo da base (deg e rad), booleano do fim de curso, 
        # booleano de validade do encoder e booleano de ack do angulo da base (para o scheduler).

        rospy.loginfo(f"[manipulation] Estado do manipulador recebido: base={msg.base_angle_deg:.2f}°, arm={msg.arm_angle:.2f}, upper_limit_active={msg.upper_limit_active}, encoder_ack={msg.encoder_ack}")

        # Devolve o feedback para o scheduler (do angulo ou do fim de curso)
        # Apenas um deles deve ser 1, senão um pode interferir no ack do outro.
        if (msg.encoder_ack == 1 or msg.upper_limit_active == 1):
            feedback_msg = SchedulerResponse()
            feedback_msg.uid = self.last_processed_uid
            feedback_msg.target = TARGET_NAME
            feedback_msg.status = "OK"
            self.pub_fb.publish(feedback_msg)


    def run(self):
        rospy.spin()

if __name__ == "__main__":
    try:
        ManipulationInterface().run()
    except rospy.ROSInterruptException:
        pass
