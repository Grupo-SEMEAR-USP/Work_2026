#include "task_manager.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "nvs_flash.h"

#include "mqtt_communication.h"
#include "uart_communication.h"
#include "utils.h"           
#include "encoder.h"
#include "h_bridge.h"
#include "pid.h"

/* Mutex para proteção de dados compartilhados */
static SemaphoreHandle_t xDataMutex = NULL;

/* Tags de Log */
static const char *COMM_TAG = "COMM_TASK";
static const char *ACT_TAG = "ACT_TASK";
static const char *TAG = "TASKS";

static void mqtt_task(void *pvParameters) {
    init_wifi();

    mqtt_start(xDataMutex);

    while (1) {
        if (xDataMutex != NULL) {   
            if (xSemaphoreTake(xDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                mqtt_publish_encoders();

                xSemaphoreGive(xDataMutex);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }
    // Não deve chegar aqui
    mqtt_stop();
}

static void uart_task(void *pvParameters) {
    esp_err_t ret;
    ESP_LOGI(COMM_TAG, "Inicializando comunicação serial (UART0/USB)");
    ret = init_uart();
    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha catastrofica ao iniciar a UART. Deleta Task");
        vTaskDelete(NULL); 
        return;
    }
    ESP_LOGI(COMM_TAG, "Comunicação serial inicializada.");
    while(1){
        uart_read(&G_CMD);
        if (xDataMutex != NULL) {   
            if (xSemaphoreTake(xDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                // Atualizando globais de comando
                G_TARGET_L = G_CMD.left_data;
                G_TARGET_R = G_CMD.right_data;
                
                // Lendo globais de feedback para enviar
                uart_comm_t to_send;
                to_send.left_data = G_RADS_L;
                to_send.right_data = G_RADS_R;

                xSemaphoreGive(xDataMutex); // Libera o mutex
                
                // Envia as cópias
                uart_send(&to_send);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }
}

static void actuators_task(void *pvParameters) {
    ESP_LOGI(ACT_TAG, "Inicializando módulos de ponte H");
    init_h_bridge(MOTOR_LEFT);
    init_h_bridge(MOTOR_RIGHT);

    ESP_LOGI(ACT_TAG, "Inicializando encoders");
    pcnt_unit_handle_t encoder_unit_r = init_encoder(ENC_RIGHT);
    pcnt_unit_handle_t encoder_unit_l = init_encoder(ENC_LEFT);

    ESP_LOGI(ACT_TAG, "Inicializando controladores PID");
    pid_ctrl_block_handle_t pid_block_r = init_pid(PID_RIGHT);
    pid_ctrl_block_handle_t pid_block_l = init_pid(PID_LEFT);

    // Variável para manter o tempo de execução periódico
    TickType_t xLastWakeTime;
    const TickType_t xFrequency = pdMS_TO_TICKS(CNTRL_PERIOD_MS);
    xLastWakeTime = xTaskGetTickCount();

    while(1) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);

        if (xDataMutex != NULL) {
            if (xSemaphoreTake(xDataMutex, pdMS_TO_TICKS(5)) == pdTRUE) {
                               
                // Como pid_calculate usa as globais G_TARGET e G_RADS, é necessário proteger sua execução
                pid_calculate(pid_block_l, pid_block_r, encoder_unit_l, encoder_unit_r);
                
                xSemaphoreGive(xDataMutex);
            }
        }

        update_motor(MOTOR_LEFT, G_PWM_L);
        update_motor(MOTOR_RIGHT, G_PWM_R);

        // Debug
        // ESP_LOGI(ACT_TAG, "Status: L_Target=%.2f | L_Rads=%.2f | PWM_L=%.0f", 
        //     G_TARGET_L, G_RADS_L, G_PWM_L);
        // ESP_LOGI(ACT_TAG, "Status: R_Target=%.2f | R_Rads=%.2f | PWM_R=%.0f", 
        //     G_TARGET_R, G_RADS_R, G_PWM_R);
    }
}

esp_err_t init_tasks() {
    // Criar o Mutex
    xDataMutex = xSemaphoreCreateMutex();
    if (xDataMutex == NULL) {
        ESP_LOGE(TAG, "Erro ao criar Mutex");
        return ESP_FAIL;
    }

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