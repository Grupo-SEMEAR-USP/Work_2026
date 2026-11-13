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
#define PH_TE_PWM GPIO_NUM_15
#define PH_TE_IN1 GPIO_NUM_16
#define PH_TE_IN2 GPIO_NUM_4
#define PH_TD_PWM GPIO_NUM_2
#define PH_TD_IN1 GPIO_NUM_17
#define PH_TD_IN2 GPIO_NUM_18

#define PH_FE_PWM GPIO_NUM_32
#define PH_FE_IN1 GPIO_NUM_27
#define PH_FE_IN2 GPIO_NUM_25
#define PH_FD_PWM GPIO_NUM_14
#define PH_FD_IN1 GPIO_NUM_26
#define PH_FD_IN2 GPIO_NUM_33

#define ENC_FE_CHA GPIO_NUM_12
#define ENC_FE_CHB GPIO_NUM_13
#define ENC_FD_CHA GPIO_NUM_21
#define ENC_FD_CHB GPIO_NUM_22
#define ENC_TE_CHA GPIO_NUM_35
#define ENC_TE_CHB GPIO_NUM_34
#define ENC_TD_CHA GPIO_NUM_19
#define ENC_TD_CHB GPIO_NUM_23

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