#include "uart_communication.h"
#include "driver/uart.h"
#include "esp_log.h"
#include <string.h>

#define UART_PORT_NUM      UART_NUM_0
#define UART_BAUD_RATE     115200
#define UART_BUF_SIZE      1024

// Protocolo
#define PROTOCOL_SOF       0xAA
#define PROTOCOL_EOF       0xBB

static const char *TAG = "UART";

/* Máquina de Estados Interna */
typedef enum {
    ST_WAIT_SOF,
    ST_GET_DATA,
    ST_GET_CHK,
    ST_WAIT_EOF
} parser_state_t;

static parser_state_t s_state = ST_WAIT_SOF;
static uint8_t s_idx = 0;
static uint8_t s_checksum = 0;
static uint8_t s_rx_buffer[sizeof(uart_command_t)];

esp_err_t init_uart() {
    const uart_config_t uart_config = {
        .baud_rate = UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_APB,
    };
    
    // Utilização dos pinos padrão para UART0
    ESP_ERROR_CHECK(uart_param_config(UART_PORT_NUM, &uart_config));
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT_NUM, UART_BUF_SIZE * 2, 0, 0, NULL, 0));
    
    ESP_LOGI(TAG, "UART Inicializada (115200 8N1)");
    return ESP_OK;
}

void uart_send_telemetry(uart_telemetry_t *data) {
    // SOF + DATA + CHK + EOF
    uint8_t frame[1 + sizeof(uart_telemetry_t) + 1 + 1]; 
    int p = 0;

    frame[p++] = PROTOCOL_SOF;
    
    memcpy(&frame[p], data, sizeof(uart_telemetry_t));
    
    // Calcula Checksum (Soma simples do payload)
    uint8_t chk = 0;
    uint8_t *payload_ptr = (uint8_t*)data;
    for(size_t i=0; i<sizeof(uart_telemetry_t); i++){
        chk += payload_ptr[i];
    }
    
    p += sizeof(uart_telemetry_t);
    frame[p++] = chk;
    frame[p++] = PROTOCOL_EOF;

    uart_write_bytes(UART_PORT_NUM, frame, p);
}

bool uart_read(uart_command_t *out_cmd) {
    size_t length = 0;
    uart_get_buffered_data_len(UART_PORT_NUM, &length);
    if (length == 0) return false;

    // Lê em blocos pequenos para não travar
    uint8_t data_chunk[64];
    int len = uart_read_bytes(UART_PORT_NUM, data_chunk, sizeof(data_chunk), 0);

    bool packet_ready = false;

    for (int i = 0; i < len; i++) {
        uint8_t byte = data_chunk[i];

        switch (s_state) {
            case ST_WAIT_SOF:
                if (byte == PROTOCOL_SOF) {
                    s_state = ST_GET_DATA;
                    s_idx = 0;
                    s_checksum = 0;
                }
                break;

            case ST_GET_DATA:
                s_rx_buffer[s_idx++] = byte;
                s_checksum += byte;
                if (s_idx >= sizeof(uart_command_t)) {
                    s_state = ST_GET_CHK;
                }
                break;

            case ST_GET_CHK:
                if (byte == s_checksum) {
                    s_state = ST_WAIT_EOF;
                } else {
                    ESP_LOGW(TAG, "Checksum Error");
                    s_state = ST_WAIT_SOF;
                }
                break;

            case ST_WAIT_EOF:
                if (byte == PROTOCOL_EOF) {
                    memcpy(out_cmd, s_rx_buffer, sizeof(uart_command_t));
                    packet_ready = true;
                }
                s_state = ST_WAIT_SOF; 
                break;
        }
    }

    return packet_ready;
}