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

void uart_send(uart_telemetry_t *data) {
    // Fallback
    if (data == NULL) {
        return;
    } 

    // SOF + DATA + CHK + EOF
    uint8_t frame[1 + sizeof(uart_telemetry_t) + 1 + 1]; 
    int p = 0;

    // SOF
    frame[p++] = PROTOCOL_SOF;
    
    // Payload
    memcpy(&frame[p], data, sizeof(uart_telemetry_t));
    
    // Calcula Checksum (Soma simples do payload)
    uint8_t chk = 0;
    for (size_t i = 0; i < sizeof(uart_telemetry_t); i++) {
        chk += frame[p + i];
    }
    
    // Avanço do payload
    p += sizeof(uart_telemetry_t);
    
    // Checksum
    frame[p++] = chk;
    
    // EOF
    frame[p++] = PROTOCOL_EOF;

    uart_write_bytes(UART_PORT_NUM, frame, p);
}