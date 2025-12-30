#ifndef STEPPER_CONTROL_H
#define STEPPER_CONTROL_H

/* Importe de bibliotecas */
#include "esp_err.h"
#include <stdbool.h>

/* Protótipos das Funções */
// Inicialização
esp_err_t init_steppers();
// Mover uma variação de passos nos steppers
void move_stepper_elevator(int steps);
void move_stepper_base(int steps);
// Loop de processamento para mover até atingir o desejado
void stepper_loop_process();
bool is_stepper_idle(void);

#endif // STEPPER_CONTROL_H