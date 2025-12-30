#include "uart_communication.h"
#include <stdint.h>
#include <string.h>
#include "esp_log.h"
#include "driver/uart.h"

/* Configuração UART */
#define UART_PORT_NUM      UART_NUM_0
#define BUF_SIZE           1024
#define RD_BUF_SIZE        1024

/* Definições */
#define FRAME_SOF 0xAA
#define FRAME_EOF 0xBB
#define PAYLOAD_SIZE sizeof(uart_comm_t)

typedef enum {
    STATE_WAIT_SOF,     // Start of Frame
    STATE_WAIT_DATA,    // Payload
    STATE_WAIT_CHK,     // Validação por Checksum
    STATE_WAIT_EOF      // End of Frame
} parser_state_t;

static const char *TAG = "UART";

// Variáveis estáticas para guardar o estado do parser
static parser_state_t s_current_state = STATE_WAIT_SOF;
static uint8_t s_data_index = 0;

// Buffer para armazenar o payload recebido
static union {
    uint8_t bytes[PAYLOAD_SIZE];
    uart_comm_t data;
} s_payload_buffer;

// Calcula o checksum do payload recebido
static uint8_t calculate_checksum() {
    uint8_t chk = 0;
    for (int i = 0; i < PAYLOAD_SIZE; i++) {
        chk += s_payload_buffer.bytes[i];
    }
    return chk & 0xFF; // Mascara para descartar caso exceda 1 byte
}

// Processa um byte recebido pela UART
static bool process_received_byte(uint8_t byte, uart_comm_t *cmd) {
    bool frame_completed = false;

    switch (s_current_state)
    {
    case STATE_WAIT_SOF:
        if (byte == FRAME_SOF) {
            s_current_state = STATE_WAIT_DATA;
            s_data_index = 0; // Reseta o contador do payload
        }
        break;

    case STATE_WAIT_DATA:
        s_payload_buffer.bytes[s_data_index] = byte;
        s_data_index++;

        // Verificação se já recebeu todos os 8 bytes
        if (s_data_index >= PAYLOAD_SIZE) {
            s_current_state = STATE_WAIT_CHK;
        }
        break;

    case STATE_WAIT_CHK:
        {
            uint8_t calculated_chk = calculate_checksum();
            
            if (byte == calculated_chk) {
                s_current_state = STATE_WAIT_EOF;
            } else {
                ESP_LOGW(TAG, "Checksum falhou! Esperado: 0x%02X, Recebido: 0x%02X", calculated_chk, byte);
                s_current_state = STATE_WAIT_SOF;
            }
        }
        break;

    case STATE_WAIT_EOF:
        if (byte == FRAME_EOF) {
            // Frame válido recebido!
            memcpy(cmd, &s_payload_buffer.data, PAYLOAD_SIZE);
            frame_completed = true;

            ESP_LOGI(TAG, "Frame válido! Left: %.2f, Right: %.2f", 
                     cmd->left_data, cmd->right_data);
        } else {
            ESP_LOGW(TAG, "EOF falhou! Esperado: 0x%02X, Recebido: 0x%02X", FRAME_EOF, byte);
        }
        
        s_current_state = STATE_WAIT_SOF;
        break;
    
    default:
        s_current_state = STATE_WAIT_SOF;
        break;
    }
    return frame_completed;
}

static esp_err_t uart_send_frame(uart_comm_t *cmd){
    const int frame_size = 1 + PAYLOAD_SIZE + 1 + 1; // SOF + Payload + Checksum + EOF

    uint8_t frame[frame_size];
    int index = 0;

    // Start of Frame
    frame[index++] = FRAME_SOF;

    // Payload
    memcpy(&frame[index], cmd, PAYLOAD_SIZE);
    index += PAYLOAD_SIZE;

    // Checksum
    uint8_t chk = 0;

    uint8_t *cmd_bytes = (uint8_t *)cmd; // Converte a struct para bytes

    for (int i = 0; i < PAYLOAD_SIZE; i++) {
        chk += cmd_bytes[i];
    }
    frame[index++] = chk & 0xFF;

    // End of Frame
    frame[index++] = FRAME_EOF;

    // Envia os bytes de uma vez
    int bytes_sent = uart_write_bytes(UART_PORT_NUM, frame, frame_size);

    if (bytes_sent == frame_size) {
        return ESP_OK;
    } else {
        ESP_LOGW(TAG, "Falha ao enviar frame, bytes_sent=%d (esperado %d)", bytes_sent, frame_size);
        return ESP_FAIL;
    }
}

esp_err_t init_uart() {
    // Configuração do UART
    const uart_config_t uart_config = {
        .baud_rate = 115200, // Velocidade padrão para comunicação USB/Console
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_APB,
    };
    
    // Configura os parâmetros da UART
    ESP_ERROR_CHECK(uart_param_config(UART_PORT_NUM, &uart_config));

    // Instala o driver da UART. 
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT_NUM, BUF_SIZE * 2, 0, 0, NULL, 0));
    
    ESP_LOGI(TAG, "Driver UART0 (USB) inicializado a 115200 bps.");
    return ESP_OK;
}

bool uart_read(uart_comm_t *cmd) {
    // Aloca o buffer de leitura estático para evitar Heap fragmentation
    static uint8_t data[RD_BUF_SIZE];
    bool new_packet_received = false;

    int len = uart_read_bytes(UART_PORT_NUM, data, RD_BUF_SIZE, pdMS_TO_TICKS(10));

    if (len > 0) {
        // Processa cada byte que chegou
        for (int i = 0; i < len; i++) {
            if (process_received_byte(data[i], cmd)) {
                new_packet_received = true;
            }
        }
    }
    return new_packet_received;
}

void uart_send(uart_comm_t *cmd){
    esp_err_t ret = uart_send_frame(cmd);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Falha ao enviar dados via UART");
    }
}