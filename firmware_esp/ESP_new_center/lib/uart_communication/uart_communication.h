#ifndef UART_COMMUNICATION_H
#define UART_COMMUNICATION_H

/* Importe de bibliotecas */
#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

#define UART_MOTOR_ELEVATOR   (1u << 0)
#define UART_MOTOR_BASE       (1u << 1)
#define UART_MOTOR_WRIST      (1u << 2)
#define UART_MOTOR_GRIPPER    (1u << 3)
#define UART_MOTOR_ALL       (UART_MOTOR_ELEVATOR | UART_MOTOR_BASE | \
                              UART_MOTOR_WRIST | UART_MOTOR_GRIPPER)

/* Estruturas de Dados */
// Dados enviados pelo ESP (Sensores)
typedef struct __attribute__((packed)) {
    float base_angle_deg;
    float base_angle_rad;
    uint8_t upper_limit_active; // 1 = GPIO C_FIM_CS em HIGH
    uint8_t encoder_valid;      // 1 = leitura AS5600 teve sucesso
} uart_telemetry_t;

// Dados recebidos pelo ESP (Comandos)
typedef struct __attribute__((packed)) {
    uint16_t sequence;
    uint8_t motor_mask;
    float elevator_cm;       // Relativo: positivo sobe, negativo desce
    float base_angle_deg;    // Absoluto [0,360]
    float wrist_angle_deg;   // Absoluto [0,180]
    float gripper_angle_deg; // Absoluto [0,180]
} uart_command_t;

/* Protótipos das Funções */
// Inicialização
esp_err_t init_uart();
// Envia pacote de telemetria
esp_err_t uart_send_telemetry(const uart_telemetry_t *data);
// Mantém a leitura de possíveis variáveis de comando
bool uart_read(uart_command_t *out_cmd);

#endif // UART_COMMUNICATION_H