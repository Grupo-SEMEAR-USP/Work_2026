
#ifndef MQTT_COMMUNICATION_H
#define MQTT_COMMUNICATION_H

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

/* Inicialização Wi-Fi */
esp_err_t init_wifi(void);

/* Inicialização e encerramento MQTT */
esp_err_t mqtt_start(SemaphoreHandle_t data_mutex);
void mqtt_stop(void);

/* Publicação de feedback dos encoders */
void mqtt_publish_encoders(void);

/* Verificação de perda de comandos */
void mqtt_check_timeout(void);

#endif // MQTT_COMMUNICATION_H
