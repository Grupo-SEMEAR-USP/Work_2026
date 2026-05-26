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
    FRONT,
    REAR
} esp_pos_t;

// Protocolo de Comunicação
typedef enum {
    UART,
    MQTT,
    NONE
} communication_mode_t;

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