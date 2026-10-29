#ifndef UTILS_H
#define UTILS_H

#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include "driver/gpio.h"

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
    CLI,
    NONE
} communication_mode_t;

/*=== GPIO (2025) ===*/
/* Servos */
#define PIN_SERVO_WRIST     GPIO_NUM_22
#define PIN_SERVO_GRIPPER   GPIO_NUM_32

/* Steppers */
// Elevador (E)
#define PIN_STEP_ELEVATOR   GPIO_NUM_15
#define PIN_DIR_ELEVATOR    GPIO_NUM_2
// Base Rotativa (B)
#define PIN_STEP_BASE       GPIO_NUM_14
#define PIN_DIR_BASE        GPIO_NUM_27

/* Ultrassom (Sensores de Distância) */
// Sensor 1 (Front Left)
#define PIN_US1_TRIG        GPIO_NUM_26
#define PIN_US1_ECHO        GPIO_NUM_25

// Sensor 2 (Front Right)
#define PIN_US2_TRIG        GPIO_NUM_17
#define PIN_US2_ECHO        GPIO_NUM_16

// Sensor 3 (Rear Left)
#define PIN_US3_TRIG        GPIO_NUM_19
#define PIN_US3_ECHO        GPIO_NUM_18

/*=== Variáveis Globais ===*/

// Modo de Comunicação
extern communication_mode_t COMM_MODE;

// Comandos de Movimento (Setpoints/Estado)
extern volatile float G_STEPPER_BASE; // Base Rotativa
extern volatile float G_STEPPER_ARM;  // Elevador

extern volatile float G_SERVO_WRIST;  // Punho
extern volatile float G_SERVO_GRIPPER;// Garra

// Feedback (Sensores Ultrassônicos)
// [0]=Front_Left, [1]=Front_Right, [2]=Rear_Left
extern volatile float    G_US_CM[3];
extern volatile uint64_t G_US_TS_MS;

#endif // UTILS_H