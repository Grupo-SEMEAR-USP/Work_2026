
#ifndef UTILS_H
#define UTILS_H

#include "driver/gpio.h"
#include <stdbool.h>
#include "uart_communication.h"

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
#define MAG_DIR GPIO_NUM_17
#define MAG_SCL GPIO_NUM_22
#define MAG_SDA GPIO_NUM_21

// Servomotores
#define SERVO_1 GPIO_NUM_32  // Garra
#define SERVO_2 GPIO_NUM_33  // Pulso

// Fim de curso superior
#define FIM_CS GPIO_NUM_14

// DRV8825 - Elevador
#define DRV_STEP_UP GPIO_NUM_4
#define DRV_DIR_UP  GPIO_NUM_23

// DRV8825 - Base rotativa
#define DRV_STEP_DOWN GPIO_NUM_19
#define DRV_DIR_DOWN  GPIO_NUM_18

/*=== Variaveis Globais ===*/

// Modo de comunicacao
extern communication_mode_t COMM_MODE;

// Sensor magnetico AS5600
extern volatile float G_ENCMAG_ANGLE_DEG;
extern volatile float G_ENCMAG_ANGLE_RAD;

extern bool G_FCS_UP;  // Fim de curso superior

extern uart_command_t G_MOTOR_CMD;
extern bool G_MOTOR_CMD_READY;

#endif // UTILS_H