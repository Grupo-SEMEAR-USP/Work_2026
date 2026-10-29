#include "utils.h"

/* Definições Iniciais */
communication_mode_t COMM_MODE = UART;

float G_TARGET_L_F = 0;
float G_TARGET_R_F = 0;
float G_TARGET_L_R = 0;
float G_TARGET_R_R = 0;

int G_ENC_L_F = 0;
int G_ENC_R_F = 0;
int G_ENC_L_R = 0;
int G_ENC_R_R = 0;

float G_PWM_L_F = 0;
float G_PWM_R_F = 0;
float G_PWM_L_R = 0;
float G_PWM_R_R = 0;

float G_RADS_L_F = 0;
float G_RADS_R_F = 0;
float G_RADS_L_R = 0;
float G_RADS_R_R = 0;

// PID stop on zero
bool BREAK_FLAG_F = false;
bool BREAK_FLAG_R = false;

uart_comm_t G_CMD = { 
    .left_front_data = 0.0, 
    .right_front_data = 0.0 , 
    .left_rear_data = 0.0, 
    .right_rear_data = 0.0 };