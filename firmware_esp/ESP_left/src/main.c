#include <stdio.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"      
#include "esp_err.h"

#include "utils.h"           
#include "task_manager.h"

static const char *TAG = "APP_MAIN";

void app_main(void) {
    COMM_MODE = UART;
    
    bool enable_tasks = true;
    bool disable_logs = false;
    bool debug_uart = true;

    if (disable_logs) esp_log_level_set("*", ESP_LOG_NONE);

    if (enable_tasks) {
        ESP_LOGI(TAG, "Iniciando tasks");
        esp_err_t ret = init_tasks();
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Falha na inicialização das Tasks.");
            return;
        }
    }
    
    while(1) { 
        if (enable_tasks && debug_uart && COMM_MODE != NONE && !disable_logs) {
            ESP_LOGI(TAG, "=== Variáveis recebidas ===");
            ESP_LOGI(TAG, "Ultra Esq_1: %.2f cm", G_US_CM[0]);
            ESP_LOGI(TAG, "Ultra Esq_2: %.2f cm", G_US_CM[1]);
            ESP_LOGI(TAG, "Ultra Dir_1: %.2f cm", G_US_CM[2]);
            ESP_LOGI(TAG, "Ultra Dir_2: %.2f cm", G_US_CM[3]);
            ESP_LOGI(TAG, "Ultra Esq_Frt: %.2f cm", G_US_CM[4]);
            ESP_LOGI(TAG, "Ultra Dir_Frt: %.2f cm", G_US_CM[5]);
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}