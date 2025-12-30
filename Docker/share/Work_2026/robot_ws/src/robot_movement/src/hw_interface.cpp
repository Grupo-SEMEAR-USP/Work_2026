#include "hw_interface.hpp"

HwInterface::HwInterface(ros::NodeHandle& nh)
: nh_(nh), // Inicializa a cópia do NodeHandle
  command_timeout_(nh_.createTimer(ros::Duration(0.2), 
                                   &HwInterface::cb_cmdTimeout,
                                   this, true, false))
{
    /*——— Publishers e Subscribers ———*/
    cmd_vel_sub_ = nh_.subscribe("cmd_vel", 10, &HwInterface::cb_cmdVel, this);
    encoder_sub_ = nh_.subscribe("encoder_data", 10, &HwInterface::cb_encoder, this);
    imu_sub_     = nh_.subscribe("/imu/data_filtered", 10, &HwInterface::cb_imu, this);
        
    velocity_command_pub_ = nh_.advertise<robot_communication::velocity_comm>("velocity_cmd", 10);
    odom_pub_             = nh_.advertise<nav_msgs::Odometry>("odom", 50);
    
    /*——— Carregamento de Parâmetros ———*/
    nh_.getParam("wheel_specification/wheel_radius",            wheel_radius_);
    nh_.getParam("wheel_specification/wheel_separation_width",  wheel_separation_width_);
    nh_.getParam("wheel_specification/wheel_separation_length", wheel_separation_length_);
    nh_.getParam("wheel_specification/deceleration_rate",       deceleration_rate_);
    nh_.getParam("wheel_specification/max_speed",               max_speed_);
    nh_.getParam("wheel_specification/min_speed",               min_speed_);
    
    base_geometry_sum_ = wheel_separation_width_ + wheel_separation_length_;

    /*——— Inicialização ———*/
    odom_x_ = 0.0; 
    odom_y_ = 0.0; 
    odom_yaw_ = 0.0;
    
    current_vel_x_ = 0.0; 
    current_vel_y_ = 0.0; 
    current_vel_omega_ = 0.0;

    current_time_ = ros::Time::now();
    last_time_    = ros::Time::now();
}

/* ——————————————————— Callbacks ———————————————————————— */

void HwInterface::cb_cmdVel(const geometry_msgs::Twist::ConstPtr& msg)
{
    double vx = msg->linear.x;
    double vy = msg->linear.y;
    double w  = msg->angular.z;

    /*——— Cinemática Inversa (Omnidirecional) ———*/
    // FL = vx - vy - w(geo)
    // FR = vx + vy + w(geo)
    // RL = vx + vy - w(geo)
    // RR = vx - vy + w(geo)

    double v_fl = (vx - vy - (w * base_geometry_sum_)) / wheel_radius_;
    double v_fr = (vx + vy + (w * base_geometry_sum_)) / wheel_radius_;
    double v_rl = (vx + vy - (w * base_geometry_sum_)) / wheel_radius_;
    double v_rr = (vx - vy + (w * base_geometry_sum_)) / wheel_radius_;

    // Aplica limitação e armazena
    cmd_vel_fl_ = clampSpeed(v_fl);
    cmd_vel_fr_ = clampSpeed(v_fr);
    cmd_vel_rl_ = clampSpeed(v_rl);
    cmd_vel_rr_ = clampSpeed(v_rr);

    // Reinicia Watchdog
    command_timeout_.stop();
    command_timeout_.setPeriod(ros::Duration(0.2), true);
    command_timeout_.start();
}

void HwInterface::cb_encoder(const robot_communication::encoder_comm::ConstPtr& msg)
{
    // Converte velocidades de roda de rad/s para m/s
    double v_fl = msg->front_left  * wheel_radius_;
    double v_fr = msg->front_right * wheel_radius_;
    double v_rl = msg->rear_left   * wheel_radius_;
    double v_rr = msg->rear_right  * wheel_radius_;

    /*——— Cinemática Direta (Omnidirecional) ———*/
    // vx = (FL + FR + RL + RR) / 4
    // vy = (-FL + FR + RL - RR) / 4
    // w  = (-FL + FR - RL + RR) / (4 * geometry) 
    
    current_vel_x_ = (v_fl + v_fr + v_rl + v_rr) / 4.0;
    current_vel_y_ = (-v_fl + v_fr + v_rl - v_rr) / 4.0;
    
    current_vel_omega_ = (-v_fl + v_fr - v_rl + v_rr) / (4.0 * base_geometry_sum_);

    // Filtro de sanidade
    if (std::abs(current_vel_x_) > max_speed_ * wheel_radius_) current_vel_x_ = 0.0;
    if (std::abs(current_vel_y_) > max_speed_ * wheel_radius_) current_vel_y_ = 0.0;
}

void HwInterface::cb_imu(const sensor_msgs::Imu::ConstPtr& msg)
{
    // Extrai Orientação
    tf::Quaternion q(
        msg->orientation.x,
        msg->orientation.y,
        msg->orientation.z,
        msg->orientation.w
    );
    tf::Matrix3x3 m(q);
    double roll, pitch, yaw;
    m.getRPY(roll, pitch, yaw);

    // Zera a orientação no início
    if (!imu_initialized_) {
        imu_initial_offset_ = yaw;
        imu_initialized_ = true;
        ROS_INFO("IMU Inicializada. Offset: %.2f", imu_initial_offset_);
    }

    // Calcula o yaw relativo ao offset inicial
    double relative_yaw = yaw - imu_initial_offset_;

    // Normaliza para garantir -PI a PI
    while (relative_yaw > M_PI) relative_yaw -= 2.0 * M_PI;
    while (relative_yaw < -M_PI) relative_yaw += 2.0 * M_PI;

    imu_yaw_ = relative_yaw;
    // Extrai a velocidade angular
    imu_angular_vel_z_ = msg->angular_velocity.z;

    ROS_DEBUG_THROTTLE(5.0, "cb_imu received (yaw=%.3f ang_z=%.3f)", imu_yaw_, imu_angular_vel_z_);
}

/* ——————————————————— Funções Auxiliares ———————————————————————— */

double HwInterface::clampSpeed(double v_input)
{
    return std::min(std::max(v_input, (double)min_speed_), (double)max_speed_);
}

void HwInterface::publishWheelSpeeds()
{
    // Preenche mensagem para o hardware
    commanded_vel_msg_.front_left  = (float)cmd_vel_fl_;
    commanded_vel_msg_.front_right = (float)cmd_vel_fr_;
    commanded_vel_msg_.rear_left   = (float)cmd_vel_rl_;
    commanded_vel_msg_.rear_right  = (float)cmd_vel_rr_;

    velocity_command_pub_.publish(commanded_vel_msg_);
}

void HwInterface::cb_cmdTimeout(const ros::TimerEvent&)
{
    updateWheelSpeedForDeceleration();
}

void HwInterface::updateWheelSpeedForDeceleration()
{
    // Lambda para desacelerar
    auto decel = [this](double& v){
        if (std::abs(v) > deceleration_rate_) 
            v -= deceleration_rate_ * ((v > 0) ? 1 : -1);
        else 
            v = 0.0;
    };

    decel(cmd_vel_fl_);
    decel(cmd_vel_fr_);
    decel(cmd_vel_rl_);
    decel(cmd_vel_rr_);

    // Se alguma roda ainda estiver girando, mantém o loop de desaceleração
    if (cmd_vel_fl_ != 0.0 || cmd_vel_fr_ != 0.0 || 
        cmd_vel_rl_ != 0.0 || cmd_vel_rr_ != 0.0)
    {
        command_timeout_.stop();
        command_timeout_.setPeriod(ros::Duration(0.05), true);
        command_timeout_.start();
    }
}

void HwInterface::updateOdometry()
{
    current_time_ = ros::Time::now();
    double dt = (current_time_ - last_time_).toSec();
    
    if (dt <= 0.0) {
        // Primeira iteração ou erro de clock
        last_time_ = current_time_;
        return; 
    }

    /*——— Integração da Odometria ———*/
    
    // Preferência pela IMU para rotação
    double yaw_for_calculation;
    double angular_vel_for_odom;
    if (imu_initialized_) {
        odom_yaw_ = imu_yaw_; 
        yaw_for_calculation = imu_yaw_;
        angular_vel_for_odom = imu_angular_vel_z_;
    } else {
        double delta_th = current_vel_omega_ * dt;
        odom_yaw_ += delta_th;
        yaw_for_calculation = odom_yaw_;
        angular_vel_for_odom = current_vel_omega_;
    }

    double delta_x = (current_vel_x_ * cos(odom_yaw_) - current_vel_y_ * sin(odom_yaw_)) * dt;
    double delta_y = (current_vel_x_ * sin(odom_yaw_) + current_vel_y_ * cos(odom_yaw_)) * dt;

    odom_x_ += delta_x;
    odom_y_ += delta_y;

    last_time_ = current_time_;

    /*——— Publicação (TF e Odom) ———*/
    
    // Quaternion
    tf2::Quaternion q;
    q.setRPY(0.0, 0.0, odom_yaw_);
    q.normalize();
    geometry_msgs::Quaternion odom_quat = tf2::toMsg(q);

    // TF
    geometry_msgs::TransformStamped odom_trans;
    odom_trans.header.stamp = current_time_;
    odom_trans.header.frame_id = "odom";
    odom_trans.child_frame_id = "base_footprint";
    odom_trans.transform.translation.x = odom_x_;
    odom_trans.transform.translation.y = odom_y_;
    odom_trans.transform.translation.z = 0.0;
    odom_trans.transform.rotation = odom_quat;
    odom_broadcaster_.sendTransform(odom_trans);

    // Topic Message
    nav_msgs::Odometry odom;
    odom.header.stamp = current_time_;
    odom.header.frame_id = "odom";
    odom.child_frame_id = "base_footprint";
    
    // Pose
    odom.pose.pose.position.x = odom_x_;
    odom.pose.pose.position.y = odom_y_;
    odom.pose.pose.position.z = 0.0;
    odom.pose.pose.orientation = odom_quat;

    // Twist (Velocidade relativa ao robô)
    odom.twist.twist.linear.x  = current_vel_x_;
    odom.twist.twist.linear.y  = current_vel_y_; // Importante para Omni
    odom.twist.twist.angular.z = angular_vel_for_odom;

    odom_pub_.publish(odom);
}

int main(int argc, char** argv)
{
    ros::init(argc, argv, "hw_interface");
    ros::NodeHandle nh;

    HwInterface hw(nh);

    ros::Rate rate(HW_IF_UPDATE_FREQ);
    ros::AsyncSpinner spinner(4);
    spinner.start();

    while (ros::ok())
    {
        hw.publishWheelSpeeds();
        hw.updateOdometry();
        rate.sleep();
    }
    return 0;
}