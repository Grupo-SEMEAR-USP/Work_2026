#ifndef H_BRIDGE_H
#define H_BRIDGE_H

/* Importe de bibliotecas */
#include "esp_err.h"
#include "driver/ledc.h"

#define LEDC_DUTY_RES      LEDC_TIMER_13_BIT
#define LEDC_MAX_DUTY      ((1 << LEDC_DUTY_RES) - 1) // 2^res - 1
#define LEDC_MIN_DUTY      (0)

/* Identificador de lado */
typedef enum{
    MOTOR_RIGHT,
    MOTOR_LEFT
} motor_side_t;

/* Protótipos das Funções */
esp_err_t init_h_bridge(motor_side_t side);
esp_err_t update_motor(motor_side_t side, float u);

#endif // H_BRIDGE_H