#ifndef UART_COMMUNICATION_H
#define UART_COMMUNICATION_H

/* Importe de bibliotecas */
#include "esp_err.h"
#include <stdbool.h>

/* Estrutura da Comunicação */
typedef struct {
    float left_data;
    float right_data;
} uart_comm_t;

/* Protótipos das Funções */
esp_err_t init_uart();
void uart_send(uart_comm_t *cmd);
bool uart_read(uart_comm_t *cmd);

#endif // UART_COMMUNICATION_H