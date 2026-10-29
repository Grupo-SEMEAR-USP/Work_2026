
#include <stdio.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_err.h"

#include "utils.h"
#include "task_manager.h"
#include "motors.h"

static const char *TAG = "APP_MAIN";

void app_main(void) {
    COMM_MODE = UART; // UART, MQTT ou NONE

    bool enable_tasks = true;
    bool disable_logs = false;

    // Debug de sensores
    bool debug_encoder = false;
    bool debug_fim_curso = false;

    // Debug de motores
    bool debug_elevator = false;
    bool debug_base = false;
    bool debug_wrist = false;
    bool debug_gripper = false;

    // Valores para teste dos motores
    float elevator_cm = 1.0f;
    float base_deg = 90.0f;
    float wrist_deg = 45.0f;
    float gripper_deg = 90.0f;

    if (disable_logs) esp_log_level_set("*", ESP_LOG_NONE);

    if (enable_tasks) {
        ESP_LOGI(TAG, "Iniciando tasks");
        esp_err_t ret = init_tasks();

        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Falha na inicializacao das Tasks.");
            return;
        }
    }

    bool debug_commands_sent = false;

    while (1) {
        motors_status_t status;

        // Somente executa apos inicializacao dos motores
        if (enable_tasks && motors_get_status(&status) == ESP_OK) {

            // Debug Encoder AS5600
            if (debug_encoder) {
                if (status.base_sensor_error == ESP_OK) {
                    ESP_LOGI(TAG, "Angulo: %.2f graus",
                             status.base_measured_deg);
                } else {
                    ESP_LOGW(TAG, "Falha na leitura do AS5600");
                }
            }

            // Debug Fim de Curso
            if (debug_fim_curso) {
                ESP_LOGI(TAG, "Fim de curso: %s",
                         status.elevator_upper_limit ? "ATIVO" : "INATIVO");
            }

            // Debug dos motores (executa uma unica vez)
            if (!debug_commands_sent) {
                debug_commands_sent = true;

                if (debug_elevator)
                    ESP_ERROR_CHECK(motors_apply(MOTOR_ELEVATOR, elevator_cm));

                if (debug_base)
                    ESP_ERROR_CHECK(motors_apply(MOTOR_BASE, base_deg));

                if (debug_wrist)
                    ESP_ERROR_CHECK(motors_apply(MOTOR_WRIST, wrist_deg));

                if (debug_gripper)
                    ESP_ERROR_CHECK(motors_apply(MOTOR_GRIPPER, gripper_deg));
            }
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
