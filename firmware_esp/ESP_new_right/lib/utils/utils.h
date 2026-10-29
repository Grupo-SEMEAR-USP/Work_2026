#ifndef DEF_H
#define DEF_H

#include <stdbool.h>
#include "driver/gpio.h"
#include "uart_communication.h"

/*=== Definições ===*/

#define CNTRL_PERIOD_MS 50  
#define COMM_PERIOD_MS  20

#define HIGH 1
#define LOW 0

#define PI 3.14159265359f

// Protocolo de Comunicação
typedef enum {
    UART,
    MQTT,
    NONE
} communication_mode_t;

/*=== GPIO Dir. (2026) ===*/
#define R_H_BRIDGE_LA_PWM GPIO_NUM_15
#define R_H_BRIDGE_LA_IN1 GPIO_NUM_16
#define R_H_BRIDGE_LA_IN2 GPIO_NUM_4
#define R_H_BRIDGE_LB_PWM GPIO_NUM_2
#define R_H_BRIDGE_LB_IN1 GPIO_NUM_17
#define R_H_BRIDGE_LB_IN2 GPIO_NUM_18

#define R_H_BRIDGE_RA_PWM GPIO_NUM_32
#define R_H_BRIDGE_RA_IN1 GPIO_NUM_35
#define R_H_BRIDGE_RA_IN2 GPIO_NUM_34
#define R_H_BRIDGE_RB_PWM GPIO_NUM_14
#define R_H_BRIDGE_RB_IN1 GPIO_NUM_26
#define R_H_BRIDGE_RB_IN2 GPIO_NUM_33

#define R_MOT_A1_ENC_CHA GPIO_NUM_12
#define R_MOT_A1_ENC_CHB GPIO_NUM_13
#define R_MOT_B1_ENC_CHA GPIO_NUM_21
#define R_MOT_B1_ENC_CHB GPIO_NUM_22
#define R_MOT_A2_ENC_CHA GPIO_NUM_27
#define R_MOT_A2_ENC_CHB GPIO_NUM_25
#define R_MOT_B2_ENC_CHA GPIO_NUM_19
#define R_MOT_B2_ENC_CHB GPIO_NUM_23

/*=== Variáveis Globais ===*/

// Modo de Comunicação
extern communication_mode_t COMM_MODE;

// Posição da ESP
typedef enum{
    FRONT,
    REAR
} pos_t;

// Setpoints
extern float G_TARGET_L_F;
extern float G_TARGET_R_F;
extern float G_TARGET_L_R;
extern float G_TARGET_R_R;

// Encoders
extern int G_ENC_L_F;
extern int G_ENC_R_F;
extern int G_ENC_L_R;
extern int G_ENC_R_R;

// Atuadores (PWM)
extern float G_PWM_L_F;
extern float G_PWM_R_F;
extern float G_PWM_L_R;
extern float G_PWM_R_R;

// Feedback (Rad/s)
extern float G_RADS_L_F;
extern float G_RADS_R_F;
extern float G_RADS_L_R;
extern float G_RADS_R_R;

extern bool BREAK_FLAG_F;
extern bool BREAK_FLAG_R;

// Comando Comunicação UART
extern uart_comm_t G_CMD;

#endif // UTILS_H