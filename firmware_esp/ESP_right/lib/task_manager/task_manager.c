#include "task_manager.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "math.h"

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
    (void)pvParameters;

    ESP_LOGI(COMM_TAG, "Inicializando Wi-Fi");

    esp_err_t ret = init_wifi();

    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha ao inicializar Wi-Fi");
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(COMM_TAG, "Inicializando MQTT");

    ret = mqtt_start(xDataMutex);

    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha ao iniciar MQTT");
        mqtt_stop();
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(COMM_TAG, "MQTT inicializado");

    TickType_t xLastWakeTime = xTaskGetTickCount();

    const TickType_t xFrequency =
        pdMS_TO_TICKS(COMM_PERIOD_MS);

    while (1) {

        // Verifica perda de comunicação
        mqtt_check_timeout();

        // Publica feedback dos quatro encoders
        mqtt_publish_encoders();

        // Mantém período de comunicação
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}


static void uart_task(void *pvParameters) {
    ESP_ERROR_CHECK(init_uart());

    TickType_t last_valid_rx = xTaskGetTickCount();

    const TickType_t timeout = pdMS_TO_TICKS(300);

    while (1) {
        uart_comm_t received_cmd = {0};
        uart_comm_t to_send = {0};

        bool received = uart_read(&received_cmd);

        bool valid = received &&
            isfinite(received_cmd.left_front_data) &&
            isfinite(received_cmd.right_front_data) &&
            isfinite(received_cmd.left_rear_data) &&
            isfinite(received_cmd.right_rear_data);

        TickType_t now = xTaskGetTickCount();

        if (xSemaphoreTake(xDataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {

            if (valid) {
                G_TARGET_L_F = received_cmd.left_front_data;
                G_TARGET_R_F = received_cmd.right_front_data;
                G_TARGET_L_R = received_cmd.left_rear_data;
                G_TARGET_R_R = received_cmd.right_rear_data;

                last_valid_rx = now;
            }
            else if ((now - last_valid_rx) >= timeout) {
                // Parada por perda de comunicação
                G_TARGET_L_F = 0.0f;
                G_TARGET_R_F = 0.0f;
                G_TARGET_L_R = 0.0f;
                G_TARGET_R_R = 0.0f;
            }

            // Feedback das quatro rodas
            to_send.left_front_data  = G_RADS_L_F;
            to_send.right_front_data = G_RADS_R_F;
            to_send.left_rear_data   = G_RADS_L_R;
            to_send.right_rear_data  = G_RADS_R_R;

            xSemaphoreGive(xDataMutex);

            uart_send(&to_send);
        }

        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }
}

static void actuators_task(void *pvParameters) {
    ESP_LOGI(ACT_TAG, "Inicializando módulos de ponte H");
    init_h_bridge(FRONT,MOTOR_LEFT);
    init_h_bridge(FRONT,MOTOR_RIGHT);
    init_h_bridge(REAR,MOTOR_LEFT);
    init_h_bridge(REAR,MOTOR_RIGHT);

    ESP_LOGI(ACT_TAG, "Inicializando encoders");
    pcnt_unit_handle_t encoder_unit_r_f = init_encoder(FRONT,ENC_RIGHT);
    pcnt_unit_handle_t encoder_unit_l_f = init_encoder(FRONT,ENC_LEFT);
    pcnt_unit_handle_t encoder_unit_r_r = init_encoder(REAR,ENC_RIGHT);
    pcnt_unit_handle_t encoder_unit_l_r = init_encoder(REAR,ENC_LEFT);

    ESP_LOGI(ACT_TAG, "Inicializando controladores PID");
    pid_ctrl_block_handle_t pid_block_r_f = init_pid(PID_RIGHT);
    pid_ctrl_block_handle_t pid_block_l_f = init_pid(PID_LEFT);
    pid_ctrl_block_handle_t pid_block_r_r = init_pid(PID_RIGHT);
    pid_ctrl_block_handle_t pid_block_l_r = init_pid(PID_LEFT);

    // Variável para manter o tempo de execução periódico
    TickType_t xLastWakeTime;
    const TickType_t xFrequency = pdMS_TO_TICKS(CNTRL_PERIOD_MS);
    xLastWakeTime = xTaskGetTickCount();

    while(1) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);

        if (xDataMutex != NULL) {
            if (xSemaphoreTake(xDataMutex, pdMS_TO_TICKS(5)) == pdTRUE) {
                               
                // Como pid_calculate usa as globais G_TARGET e G_RADS, é necessário proteger sua execução
                pid_calculate(FRONT, pid_block_l_f, pid_block_r_f, encoder_unit_l_f, encoder_unit_r_f);
                pid_calculate(REAR, pid_block_l_r, pid_block_r_r, encoder_unit_l_r, encoder_unit_r_r);

                xSemaphoreGive(xDataMutex);
            }
        }

        update_motor(FRONT,MOTOR_LEFT, G_PWM_L_F);
        update_motor(FRONT,MOTOR_RIGHT, G_PWM_R_F);
        update_motor(REAR,MOTOR_LEFT, G_PWM_L_R);
        update_motor(REAR,MOTOR_RIGHT, G_PWM_R_R);
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