#include <stdio.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

#include "task_manager.h"
#include "utils.h"

static const char* TAG = "APP_MAIN";

void app_main(void){
    // Modo de comunicação (Escolher entre UART, MQTT, CLI ou NONE)
    COMM_MODE = MQTT; 
    
    bool enable_tasks = true;
    bool disable_logs = false;

    if (disable_logs) esp_log_level_set("*", ESP_LOG_NONE);

    if (enable_tasks) {
        ESP_LOGI(TAG, "Iniciando tasks");
        esp_err_t ret = init_tasks();
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Falha na inicialização das Tasks.");
            return;
        }
    }
}