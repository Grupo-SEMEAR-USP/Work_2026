#ifndef HW_INTERFACE_HPP
#define HW_INTERFACE_HPP

#define HW_IF_UPDATE_FREQ 10
#define HW_IF_TICK_PERIOD (1.0 / HW_IF_UPDATE_FREQ)

// Inclusão de bibliotecas
#include <ros/ros.h>
#include <ros/console.h>
#include <cmath>
#include <algorithm>

// TF e TF2
#include <tf/transform_broadcaster.h>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2/utils.h>                         
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>

// Mensagens padrão
#include <geometry_msgs/Twist.h>
#include <geometry_msgs/TransformStamped.h>
#include <nav_msgs/Odometry.h>
#include <sensor_msgs/Imu.h>

// Mensagens customizadas
#include "robot_communication/velocity_comm.h"
#include "robot_communication/encoder_comm.h"

class HwInterface {
public:
    HwInterface(ros::NodeHandle& nh);

    // Callbacks
    void cb_cmdVel(const geometry_msgs::Twist::ConstPtr& msg); 
    void cb_encoder(const robot_communication::encoder_comm::ConstPtr& msg);
    void cb_imu(const sensor_msgs::Imu::ConstPtr& msg);
    void cb_cmdTimeout(const ros::TimerEvent&); 

    // Métodos Principais
    void publishWheelSpeeds();
    void updateOdometry();

    // Utilitários e Segurança
    void updateWheelSpeedForDeceleration();
    double clampSpeed(double v_input);

private:
    /*——— ROS ———*/
    ros::NodeHandle nh_;
    ros::Publisher velocity_command_pub_;
    ros::Publisher odom_pub_;
    ros::Subscriber cmd_vel_sub_;
    ros::Subscriber encoder_sub_;
    ros::Subscriber imu_sub_;
    ros::Subscriber camera_imu_sub_;
    
    ros::Timer command_timeout_;
    tf::TransformBroadcaster odom_broadcaster_;

    /*——— Comando para Hardware ———*/
    robot_communication::velocity_comm commanded_vel_msg_;

    // Velocidades alvo [rad/s]
    double cmd_vel_fl_ = 0.0; // Front Left
    double cmd_vel_fr_ = 0.0; // Front Right
    double cmd_vel_rl_ = 0.0; // Rear Left
    double cmd_vel_rr_ = 0.0; // Rear Right

    /*——— Parâmetros Físicos ———*/
    float wheel_radius_ = 0.0;            // [m]
    float wheel_separation_width_ = 0.0;  // Distância lateral entre rodas [m]
    float wheel_separation_length_ = 0.0; // Distância longitudinal entre rodas [m]
    float base_geometry_sum_ = 0.0;       // (L + W) / 2 ou soma direta dependendo da fórmula   

    float deceleration_rate_ = 0.0;       // [rad/s por tick]
    float max_speed_ = 0.0;               // [rad/s]
    float min_speed_ = 0.0;               // [rad/s]

    /*——— Odometria ———*/
    double odom_x_ = 0.0;  // [m]
    double odom_y_ = 0.0;  // [m]
    double odom_yaw_ = 0.0; // [rad]

    /*——— Estado Atual do Robô ———*/
    double current_vel_x_ = 0.0;     // Linear X [m/s]
    double current_vel_y_ = 0.0;     // Linear Y [m/s]
    double current_vel_omega_ = 0.0; // Angular Z [rad/s]

    /*——— Dados IMU ———*/
    double imu_yaw_ = 0.0;          
    double imu_angular_vel_z_ = 0.0;
    double imu_initial_offset_ = 0.0;
    bool imu_initialized_ = false;

    /*——— Controle de Tempo ———*/
    ros::Time current_time_;
    ros::Time last_time_;
};

#endif // HW_INTERFACE_HPP