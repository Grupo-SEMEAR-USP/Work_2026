
#ifndef STEPPER_CONTROL_H
#define STEPPER_CONTROL_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

typedef enum {
    STEPPER_ELEVATOR = 0,
    STEPPER_BASE = 1
} stepper_motor_t;

// Inicializacao dos dois motores
esp_err_t init_steppers();

// Comando nao bloqueante de movimento relativo
esp_err_t stepper_move(stepper_motor_t motor, int32_t steps);

// Estado dos motores
bool is_stepper_idle();
bool is_stepper_motor_idle(stepper_motor_t motor);

// Resultado da ultima execucao concluida
esp_err_t stepper_get_last_error(stepper_motor_t motor);

#endif
