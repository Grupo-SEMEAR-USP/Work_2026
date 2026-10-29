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

// Posição da ESP
typedef enum{
    LEFT,
    CENTER,
    RIGHT
} esp_pos_t;

// Protocolo de Comunicação
typedef enum {
    UART,
    MQTT,
    NONE
} communication_mode_t;



/*=== GPIO (2026) ===*/
/* Ultrassônicos */

/*--- Left ---*/
#define L_TRIG_ESQ_1 GPIO_NUM_19
#define L_ECHO_ESQ_1 GPIO_NUM_35
#define L_TRIG_ESQ_2 GPIO_NUM_34
#define L_ECHO_ESQ_2 GPIO_NUM_18

#define L_TRIG_DIR_1 GPIO_NUM_14
#define L_ECHO_DIR_1 GPIO_NUM_13
#define L_TRIG_DIR_2 GPIO_NUM_26
#define L_ECHO_DIR_2 GPIO_NUM_27

#define L_TRIG_FRT_1 GPIO_NUM_17
#define L_ECHO_FRT_1 GPIO_NUM_16
#define L_TRIG_TRS_1 GPIO_NUM_4
#define L_ECHO_TRS_1 GPIO_NUM_2

/*--- Center ---*/
#define C_ENCMAG_DIR GPIO_NUM_17
#define C_ENCMAG_SCL GPIO_NUM_22
#define C_ENCMAG_SDA GPIO_NUM_21

#define C_SERVO_1 GPIO_NUM_32
#define C_SERVO_2 GPIO_NUM_33
#define C_FIM_CS GPIO_NUM_14

#define C_DRV_STEP_UP GPIO_NUM_4
#define C_DRV_DIR_UP GPIO_NUM_23
#define C_DRV_STEP_DOWN GPIO_NUM_19
#define C_DRV_DIR_DOWN GPIO_NUM_18

/*--- Right ---*/
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

/*=== GPIO (2025) ===*/
/*--- Front ---*/
/* Encoder */
// Motor esquerdo (A)
#define F_ENCODER_LA        GPIO_NUM_15
#define F_ENCODER_LB        GPIO_NUM_14
// Motor direito (B)
#define F_ENCODER_RA        GPIO_NUM_19
#define F_ENCODER_RB        GPIO_NUM_18

/* Ponte H */
#define F_STBY              GPIO_NUM_33
// Motor esquerdo (A)
#define F_INPUT_LEFT_1      GPIO_NUM_2
#define F_INPUT_LEFT_2      GPIO_NUM_4
#define F_PWM_LEFT          GPIO_NUM_25
// Motor direito (B)
#define F_INPUT_RIGHT_1     GPIO_NUM_32
#define F_INPUT_RIGHT_2     GPIO_NUM_27
#define F_PWM_RIGHT         GPIO_NUM_26

/*--- Rear ---*/
/* Encoder */
// Motor esquerdo (B)
#define R_ENCODER_LA        GPIO_NUM_15
#define R_ENCODER_LB        GPIO_NUM_14
// Motor direito (A)
#define R_ENCODER_RA        GPIO_NUM_19
#define R_ENCODER_RB        GPIO_NUM_18

/* Ponte H */
#define R_STBY              GPIO_NUM_33
// Motor esquerdo (B)
#define R_INPUT_LEFT_1      GPIO_NUM_27
#define R_INPUT_LEFT_2      GPIO_NUM_32
#define R_PWM_LEFT          GPIO_NUM_25
// Motor direito (A)
#define R_INPUT_RIGHT_1     GPIO_NUM_4
#define R_INPUT_RIGHT_2     GPIO_NUM_2
#define R_PWM_RIGHT         GPIO_NUM_26

/*=== Variáveis Globais ===*/

// Modo de Comunicação
extern communication_mode_t COMM_MODE;

// Posição da ESP
extern esp_pos_t ESP_POSITION;

// Setpoints
extern float G_TARGET_L;
extern float G_TARGET_R;

// Encoders
extern int G_ENC_L;
extern int G_ENC_R;

// Atuadores (PWM)
extern float G_PWM_L;
extern float G_PWM_R;

// Feedback (Rad/s)
extern float G_RADS_L;
extern float G_RADS_R;

extern bool BREAK_FLAG;

// Comando Comunicação UART
extern uart_comm_t G_CMD;

#endif // UTILS_H