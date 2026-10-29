#ifndef ULTRASONIC_DISTANCE_H
#define ULTRASONIC_DISTANCE_H

/* Importe de bibliotecas */
#include "esp_err.h"

/* Protótipos das Funções */
esp_err_t init_ultrasonic_distance();
void update_ultrasonic_readings();

#endif // ULTRASONIC_DISTANCE_H