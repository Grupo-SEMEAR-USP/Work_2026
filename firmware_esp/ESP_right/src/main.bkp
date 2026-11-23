#include <stdio.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"      
#include "esp_err.h"

#include "utils.h"           
#include "task_manager.h"

#include "h_bridge.h"
#include "encoder.h"

static const char *TAG = "APP_MAIN";

void app_main(void) {
    COMM_MODE = UART;

    bool enable_tasks = true;
    bool debug_motors = false;
    bool debug_encoders = false;
    bool debug_uart = true;
    bool disable_logs = false;

    pcnt_unit_handle_t encoder_unit_r_f = NULL;
    pcnt_unit_handle_t encoder_unit_l_f = NULL;
    pcnt_unit_handle_t encoder_unit_r_r = NULL;
    pcnt_unit_handle_t encoder_unit_l_r = NULL;
    
    if (disable_logs) esp_log_level_set("*", ESP_LOG_NONE);

    if (enable_tasks) {
        ESP_LOGI(TAG, "Iniciando tasks");
        esp_err_t ret = init_tasks();
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Falha na inicialização das Tasks.");
            return;
        }
    }

    if (debug_motors) {
        init_h_bridge(FRONT,MOTOR_RIGHT);
        init_h_bridge(FRONT,MOTOR_LEFT);
        init_h_bridge(REAR,MOTOR_RIGHT);
        init_h_bridge(REAR,MOTOR_LEFT);
    }

    if (debug_encoders) {
        encoder_unit_r_f = init_encoder(FRONT,ENC_RIGHT);
        encoder_unit_l_f = init_encoder(FRONT,ENC_LEFT);
        encoder_unit_r_r = init_encoder(REAR,ENC_RIGHT);
        encoder_unit_l_r = init_encoder(REAR,ENC_LEFT);
    }
    
    while(1) {
        if (debug_motors) {
            update_motor(FRONT,MOTOR_LEFT, LEDC_MAX_DUTY);
            update_motor(FRONT,MOTOR_RIGHT, LEDC_MAX_DUTY);
            update_motor(REAR,MOTOR_LEFT, LEDC_MAX_DUTY);
            update_motor(REAR,MOTOR_RIGHT, LEDC_MAX_DUTY);
        }

        if (debug_encoders) {
            int left_pos_f = get_encoder_position(encoder_unit_l_f);
            int right_pos_f = get_encoder_position(encoder_unit_r_f);
            int right_pos_r = get_encoder_position(encoder_unit_r_r);
            int left_pos_r = get_encoder_position(encoder_unit_l_r);
            ESP_LOGI(TAG, "LF: %d | RF: %d | LR: %d | RR: %d", left_pos_f, right_pos_f, left_pos_r, right_pos_r);
        }

        if (enable_tasks && debug_uart && COMM_MODE != NONE && !disable_logs) {
            ESP_LOGI(TAG, "=== Variaveis recebidas ===");
            ESP_LOGI(TAG, "Target LF: %.2f rad/s", G_TARGET_L_F);
            ESP_LOGI(TAG, "Target RF: %.2f rad/s", G_TARGET_R_F);
            ESP_LOGI(TAG, "Target LR: %.2f rad/s", G_TARGET_L_R);
            ESP_LOGI(TAG, "Target RR: %.2f rad/s", G_TARGET_R_R);

            ESP_LOGI(TAG, "=== Variaveis enviadas ===");
            ESP_LOGI(TAG, "Rads LF: %.2f rad/s", G_RADS_L_F);
            ESP_LOGI(TAG, "Rads RF: %.2f rad/s", G_RADS_R_F);
            ESP_LOGI(TAG, "Rads LR: %.2f rad/s", G_RADS_L_R);
            ESP_LOGI(TAG, "Rads RR: %.2f rad/s", G_RADS_R_R);

            ESP_LOGI(TAG, "=== Posicao dos encoders ===");
            ESP_LOGI(TAG, "Encoder LF: %d", G_ENC_L_F);
            ESP_LOGI(TAG, "Encoder RF: %d", G_ENC_R_F);
            ESP_LOGI(TAG, "Encoder LR: %d", G_ENC_L_R);
            ESP_LOGI(TAG, "Encoder RR: %d", G_ENC_R_R);
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}