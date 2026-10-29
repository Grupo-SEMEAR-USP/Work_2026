#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "driver/uart.h"
#include "esp_timer.h"

#include "uart_communication.h"

#define UART_PORT_NUM      UART_NUM_0
#define UART_BAUD_RATE     115200
#define UART_RX_BUF_SIZE       1024
#define UART_TX_BUF_SIZE       1024
#define UART_MAX_RX_PER_CALL   128
#define UART_PARTIAL_TIMEOUT_US (100000LL)

// Protocolo
#define PROTOCOL_SOF       0xAA
#define PROTOCOL_EOF       0xBB

static const char *TAG = "UART";

/* Máquina de Estados Interna */
typedef enum {
    ST_WAIT_SOF = 0,
    ST_GET_DATA,
    ST_GET_CHK,
    ST_WAIT_EOF
} parser_state_t;

_Static_assert(sizeof(float) == 4, "O protocolo exige float de 32 bits");
_Static_assert(sizeof(uart_command_t) == 19, "Payload de comando incorreto");
_Static_assert(sizeof(uart_telemetry_t) == 10, "Payload de telemetria incorreto");

static bool s_initialized = false;
static parser_state_t s_state = ST_WAIT_SOF;
static size_t s_idx = 0;
static uint8_t s_checksum = 0;
static uint8_t s_rx_buffer[sizeof(uart_command_t)];
static int64_t s_last_byte_time_us = 0;
static bool s_have_sequence = false;
static uint16_t s_last_sequence = 0;

static void parser_reset(void)
{
    s_state = ST_WAIT_SOF;
    s_idx = 0;
    s_checksum = 0;
}

static void parser_start(void)
{
    s_state = ST_GET_DATA;
    s_idx = 0;
    s_checksum = 0;
}

static bool command_is_valid(const uart_command_t *cmd)
{
    if (cmd->motor_mask == 0 || (cmd->motor_mask & (uint8_t)~UART_MOTOR_ALL)) {
        return false;
    }
    if ((cmd->motor_mask & UART_MOTOR_ELEVATOR) && !isfinite(cmd->elevator_cm)) {
        return false;
    }
    if ((cmd->motor_mask & UART_MOTOR_BASE) &&
        (!isfinite(cmd->base_angle_deg) || cmd->base_angle_deg < 0.0f ||
         cmd->base_angle_deg > 360.0f)) {
        return false;
    }
    if ((cmd->motor_mask & UART_MOTOR_WRIST) &&
        (!isfinite(cmd->wrist_angle_deg) || cmd->wrist_angle_deg < 0.0f ||
         cmd->wrist_angle_deg > 180.0f)) {
        return false;
    }
    if ((cmd->motor_mask & UART_MOTOR_GRIPPER) &&
        (!isfinite(cmd->gripper_angle_deg) || cmd->gripper_angle_deg < 0.0f ||
         cmd->gripper_angle_deg > 180.0f)) {
        return false;
    }
    return true;
}

esp_err_t init_uart(void)
{
    if (s_initialized) return ESP_OK;

    const uart_config_t cfg = {
        .baud_rate = UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_APB,
    };

    esp_err_t err = uart_driver_install(UART_PORT_NUM, UART_RX_BUF_SIZE,
                                         UART_TX_BUF_SIZE, 0, NULL, 0);
    if (err != ESP_OK) return err;

    err = uart_param_config(UART_PORT_NUM, &cfg);
    if (err != ESP_OK) {
        (void)uart_driver_delete(UART_PORT_NUM);
        return err;
    }

    parser_reset();
    s_have_sequence = false;
    s_last_byte_time_us = 0;
    s_initialized = true;
    // Nao escrever ESP_LOG* aqui: UART0 transporta frames binarios.
    return ESP_OK;
}

esp_err_t uart_send_telemetry(const uart_telemetry_t *data)
{
    if (!s_initialized) return ESP_ERR_INVALID_STATE;
    if (data == NULL) return ESP_ERR_INVALID_ARG;

    enum { FRAME_BYTES = 1 + sizeof(uart_telemetry_t) + 1 + 1 };
    uint8_t frame[FRAME_BYTES];
    frame[0] = PROTOCOL_SOF;
    memcpy(&frame[1], data, sizeof(*data));

    uint8_t checksum = 0;
    for (size_t i = 0; i < sizeof(*data); ++i) {
        checksum = (uint8_t)(checksum + frame[1 + i]);
    }
    frame[1 + sizeof(*data)] = checksum;
    frame[2 + sizeof(*data)] = PROTOCOL_EOF;

    int written = uart_write_bytes(UART_PORT_NUM, (const char *)frame, FRAME_BYTES);
    return (written == FRAME_BYTES) ? ESP_OK : ESP_FAIL;
}

bool uart_read(uart_command_t *out_cmd)
{
    if (!s_initialized || out_cmd == NULL) return false;

    // Reseta frames incompletos se a comunicacao ficou muito tempo parada.
    int64_t now = esp_timer_get_time();
    if (s_state != ST_WAIT_SOF &&
        now - s_last_byte_time_us > UART_PARTIAL_TIMEOUT_US) {
        parser_reset();
    }

    // Ler um byte por vez: ao encontrar um frame valido, os bytes
    // restantes permanecem na fila RX do driver (nenhuma frame se perde).
    for (unsigned consumed = 0; consumed < UART_MAX_RX_PER_CALL; ++consumed) {
        uint8_t byte = 0;
        int n = uart_read_bytes(UART_PORT_NUM, &byte, 1, 0);
        if (n != 1) break;

        now = esp_timer_get_time();
        if (s_state != ST_WAIT_SOF &&
            now - s_last_byte_time_us > UART_PARTIAL_TIMEOUT_US) {
            parser_reset();
        }
        s_last_byte_time_us = now;

        switch (s_state) {
        case ST_WAIT_SOF:
            if (byte == PROTOCOL_SOF) parser_start();
            break;

        case ST_GET_DATA:
            s_rx_buffer[s_idx++] = byte;
            s_checksum = (uint8_t)(s_checksum + byte);
            if (s_idx == sizeof(s_rx_buffer)) s_state = ST_GET_CHK;
            break;

        case ST_GET_CHK:
            if (byte == s_checksum) {
                s_state = ST_WAIT_EOF;
            } else if (byte == PROTOCOL_SOF) {
                parser_start();
            } else {
                parser_reset();
            }
            break;

        case ST_WAIT_EOF:
            if (byte == PROTOCOL_EOF) {
                uart_command_t cmd;
                memcpy(&cmd, s_rx_buffer, sizeof(cmd));
                parser_reset();
                if (!command_is_valid(&cmd)) break;
                if (s_have_sequence && cmd.sequence == s_last_sequence) break;
                // Importante: confirma recebimento, NAO sucesso de motors_apply().
                s_last_sequence = cmd.sequence;
                s_have_sequence = true;
                *out_cmd = cmd;
                return true;
            }
            if (byte == PROTOCOL_SOF) parser_start();
            else parser_reset();
            break;
        }
    }

    return false;
}
