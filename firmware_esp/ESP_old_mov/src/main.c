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
    ESP_POSITION = FRONT;

    bool enable_tasks = true;
    bool debug_motors = false;
    bool debug_encoders = false;
    bool disable_logs = false;

    pcnt_unit_handle_t encoder_unit_r = NULL;
    pcnt_unit_handle_t encoder_unit_l = NULL;
    
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
        init_h_bridge(MOTOR_RIGHT);
        init_h_bridge(MOTOR_LEFT);
    }

    if (debug_encoders) {
        encoder_unit_r = init_encoder(ENC_RIGHT);
        encoder_unit_l = init_encoder(ENC_LEFT);
    }
    
    while(1) {
        if (debug_motors) {
            update_motor(MOTOR_LEFT, LEDC_MAX_DUTY);
            update_motor(MOTOR_RIGHT, LEDC_MAX_DUTY);
        }

        if (debug_encoders) {
            int left_pos = get_encoder_vel(encoder_unit_r);
            int right_pos = get_encoder_vel(encoder_unit_l);
            ESP_LOGI(TAG, "Encoder L: %d | Encoder R: %d", left_pos, right_pos);
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}