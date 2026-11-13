#ifndef MQTT_COMMUNICATION_H
#define MQTT_COMMUNICATION_H

#include <stdbool.h>
#include "esp_err.h"
#include "uart_communication.h" // Mesmos tipos e bits do protocolo UART

// Inicializa o Wi-Fi STA e programa reconexao automatica
esp_err_t init_wifi(void);

// Inicializa o cliente MQTT e a fila interna de comandos
esp_err_t mqtt_start(void);

// Nao bloqueante: devolve um comando recebido/validado por chamada
bool mqtt_read(uart_command_t *out_cmd);
esp_err_t mqtt_publish_telemetry(const uart_telemetry_t *data);

// Consulta simples do estado da conexao com o broker.
bool mqtt_is_connected(void);
void mqtt_stop(void);

#endif // MQTT_COMMUNICATION_H
