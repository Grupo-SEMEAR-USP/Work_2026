#ifndef UART_COMMUNICATION_H
#define UART_COMMUNICATION_H

/* Importe de bibliotecas */
#include "esp_err.h"
#include <stdbool.h>

/* Estruturas de Dados */
// Dados enviados pelo ESP (Sensores)
typedef struct {
    float us_esq_1;
    float us_esq_2;
    float us_dir_1;
    float us_dir_2;
    float us_frt_1;
    float us_trs_1;
} __attribute__((packed)) uart_telemetry_t;

/* Protótipos das Funções */
// Inicialização
esp_err_t init_uart();
// Envia pacote de telemetria
void uart_send(uart_telemetry_t *data);

#endif // UART_COMMUNICATION_H