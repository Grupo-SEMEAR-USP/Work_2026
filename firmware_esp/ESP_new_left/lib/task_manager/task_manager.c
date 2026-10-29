#include "task_manager.h"
#include "utils.h"

/* Módulos de Lib */
#include "ultrasonic_distance.h"
#include "mqtt_communication.h"
#include "uart_communication.h"

/* Sistema */
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include <math.h>

/* Tags de Log */
static const char *COMM_TAG = "COMM_TASK";
static const char *ACT_TAG = "ACT_TASK";
static const char *TAG = "TASKS";

static void uart_task(void *pvParameters) {
    ESP_ERROR_CHECK(init_uart());
    
    uart_telemetry_t telem;

    while (1) {
        // Envia Telemetria
        telem.us_esq_1 = G_US_CM[0];
        telem.us_esq_2 = G_US_CM[1];
        telem.us_dir_1 = G_US_CM[2];
        telem.us_dir_2 = G_US_CM[3];
        telem.us_frt_1 = G_US_CM[4];
        telem.us_trs_1 = G_US_CM[5];
        uart_send(&telem);

        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }
}

static void mqtt_task(void *pvParameters) {
    init_mqtt();
    while (1) {
        publish_mqtt_telemetry();
        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }

    // Zona inalcançável
    mqtt_stop();
}

static void actuators_task(void *pvParameters) {
    // Inicia sensores (não falha critico, apenas loga)
    if(init_ultrasonic_distance() != ESP_OK) {
        ESP_LOGW(TAG, "Sensores de distancia com falha na inicializacao");
    }

    while (1) {
        update_ultrasonic_readings();
        // O update já tem delay interno
    }
}

esp_err_t init_tasks() {
    // Limpa o nvs_flash e inicializa
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI(TAG, "NVS inicializado.");
    
    // Task 1 (core 0): comunicação
    if (COMM_MODE == MQTT){
        xTaskCreatePinnedToCore(mqtt_task, "mqtt_task", 4096, NULL, 5, NULL, 0);
    } else if (COMM_MODE == UART){
        xTaskCreatePinnedToCore(uart_task, "uart_task", 4096, NULL, 5, NULL, 0);
    }
    
    // Task 2 (core 1): atuação
    xTaskCreatePinnedToCore(actuators_task, "actuators_task", 4096, NULL, 5, NULL, 1);

    return ESP_OK;
}