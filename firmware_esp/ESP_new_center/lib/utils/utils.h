
#ifndef UTILS_H
#define UTILS_H

#include "driver/gpio.h"

/*=== Definicoes ===*/
#define CNTRL_PERIOD_MS 50
#define COMM_PERIOD_MS  20

#define HIGH 1
#define LOW  0
#define PI   3.14159265359f

// Modo de comunicacao
typedef enum {
    UART,
    MQTT,
    NONE
} communication_mode_t;

/*=== GPIO Center (2026) ===*/

// Encoder magnetico AS5600
#define C_ENCMAG_DIR GPIO_NUM_17
#define C_ENCMAG_SCL GPIO_NUM_22
#define C_ENCMAG_SDA GPIO_NUM_21

// Servomotores
#define C_SERVO_1 GPIO_NUM_32  // Garra
#define C_SERVO_2 GPIO_NUM_33  // Pulso

// Fim de curso superior
#define C_FIM_CS GPIO_NUM_14

// DRV8825 - Elevador
#define C_DRV_STEP_UP GPIO_NUM_4
#define C_DRV_DIR_UP  GPIO_NUM_23

// DRV8825 - Base rotativa
#define C_DRV_STEP_DOWN GPIO_NUM_19
#define C_DRV_DIR_DOWN  GPIO_NUM_18

/*=== Variaveis Globais ===*/

// Modo de comunicacao
extern communication_mode_t COMM_MODE;

// Sensor magnetico AS5600
extern volatile float G_ENCMAG_ANGLE_DEG;
extern volatile float G_ENCMAG_ANGLE_RAD;

#endif // UTILS_H