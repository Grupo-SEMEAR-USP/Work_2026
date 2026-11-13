#ifndef UTILS_H
#define UTILS_H

#include <stdint.h>
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

/*=== GPIO Esq. (2026) ===*/
#define TRIG_ESQ_1 GPIO_NUM_19
#define ECHO_ESQ_1 GPIO_NUM_35
#define ECHO_ESQ_2 GPIO_NUM_34
#define TRIG_ESQ_2 GPIO_NUM_18

#define TRIG_DIR_1 GPIO_NUM_14
#define ECHO_DIR_1 GPIO_NUM_13
#define TRIG_DIR_2 GPIO_NUM_26
#define ECHO_DIR_2 GPIO_NUM_27

#define TRIG_ESQ_FRT GPIO_NUM_17
#define ECHO_ESQ_FRT GPIO_NUM_16
#define TRIG_DIR_FRT GPIO_NUM_4
#define ECHO_DIR_FRT GPIO_NUM_2

/*=== Variáveis Globais ===*/

// Modo de Comunicação
extern communication_mode_t COMM_MODE;

// Feedback (Sensores Ultrassônicos)
// [0]=Esq_1, [1]=Esq_2, [2]=Dir_1, [3]=Dir_2, [4]=Esq_Frt, [5]=Dir_Frt
extern volatile float    G_US_CM[6];
extern volatile uint64_t G_US_TS_MS;

#endif // UTILS_H