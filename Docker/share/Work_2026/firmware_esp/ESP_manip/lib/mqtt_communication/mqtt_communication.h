#ifndef MQTT_COMMUNICATION_H
#define MQTT_COMMUNICATION_H

/* Importe de bibliotecas */
#include "esp_err.h"

/* Protótipos das Funções */
// Inicialização e finalização
void init_mqtt();
void mqtt_stop();
// Publica dados de ultrassonicos
void publish_mqtt_telemetry();

#endif // MQTT_COMMUNICATION_H