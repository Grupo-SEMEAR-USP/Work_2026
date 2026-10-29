#ifndef MQTT_COMMUNICATION_H
#define MQTT_COMMUNICATION_H

/* Importe de bibliotecas */
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

/* Protótipos de funções */
void init_wifi();
void mqtt_start(SemaphoreHandle_t mutex_handle);
void mqtt_publish_encoders();
void mqtt_stop();

#endif // MQTT_COMMUNICATION_H