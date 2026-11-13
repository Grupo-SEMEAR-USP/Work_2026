#ifndef SERVO_CONTROL_H
#define SERVO_CONTROL_H

/* Importe de bibliotecas */
#include "esp_err.h"

/* Protótipos das Funções */
// Inicialização
esp_err_t init_servos();
// Escrever ângulo em graus [0, 180]
esp_err_t set_servo_gripper(float angle_deg);
esp_err_t set_servo_wrist(float angle_deg);
// Obtenção do último valor aplicado
float get_servo_gripper();
float get_servo_wrist();

#endif // SERVO_CONTROL_H