#ifndef UART_COMMUNICATION_H
#define UART_COMMUNICATION_H

/* Importe de bibliotecas */
#include "esp_err.h"
#include <stdbool.h>

/* Estruturas de Dados */
// Dados enviados pelo ESP (Sensores)
typedef struct {
    float front_left;
    float front_right;
    float rear_left;
} __attribute__((packed)) uart_telemetry_t;

// Dados recebidos pelo ESP (Comandos)
typedef struct {
    float arm_val;
    float base_val;
    float wrist_val;
    float grip_val;
} __attribute__((packed)) uart_command_t;

/* Protótipos das Funções */
// Inicialização
esp_err_t init_uart();
// Envia pacote de telemetria
void uart_send_telemetry(uart_telemetry_t *data);
// Mantém a leitura de possíveis variáveis de comando
bool uart_read(uart_command_t *out_cmd);

#endif // UART_COMMUNICATION_H