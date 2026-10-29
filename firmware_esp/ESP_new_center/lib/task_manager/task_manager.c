#include "task_manager.h"

#include <math.h>
#include <stdatomic.h>
#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "nvs_flash.h"

#include "mqtt_communication.h"
#include "uart_communication.h"
#include "motors.h"
#include "utils.h"

static atomic_bool s_motors_ready = ATOMIC_VAR_INIT(false);

/* Tags de Log */
static const char *COMM_TAG = "COMM_TASK";
static const char *ACT_TAG = "ACT_TASK";
static const char *TAG = "TASKS";

static void mqtt_task(void *pvParameters) {
    (void)pvParameters;

    // Espera o modulo motors estar pronto para receber comandos.
    while (!atomic_load(&s_motors_ready)) {
        vTaskDelay(pdMS_TO_TICKS(20));
    }

    esp_err_t ret = init_wifi();
    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha ao iniciar Wi-Fi: %s", esp_err_to_name(ret));
        vTaskDelete(NULL);
        return;
    }

    ret = mqtt_start();
    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha ao iniciar MQTT: %s", esp_err_to_name(ret));
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        uart_command_t cmd;

        // Um pacote = um novo comando. Nao reaplicar nos ciclos seguintes.
        for (int i = 0; i < 8 && mqtt_read(&cmd); i++) {
            if (cmd.motor_mask & UART_MOTOR_ELEVATOR) {
                ret = motors_apply(MOTOR_ELEVATOR, cmd.elevator_cm);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Elevador: comando rejeitado (%s)", esp_err_to_name(ret));
            }
            if (cmd.motor_mask & UART_MOTOR_BASE) {
                ret = motors_apply(MOTOR_BASE, cmd.base_angle_deg);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Base: comando rejeitado (%s)", esp_err_to_name(ret));
            }
            if (cmd.motor_mask & UART_MOTOR_WRIST) {
                ret = motors_apply(MOTOR_WRIST, cmd.wrist_angle_deg);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Pulso: comando rejeitado (%s)", esp_err_to_name(ret));
            }
            if (cmd.motor_mask & UART_MOTOR_GRIPPER) {
                ret = motors_apply(MOTOR_GRIPPER, cmd.gripper_angle_deg);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Garra: comando rejeitado (%s)", esp_err_to_name(ret));
            }
        }

        motors_status_t status;
        if (mqtt_is_connected() && motors_get_status(&status) == ESP_OK) {
            bool encoder_ok = status.base_sensor_error == ESP_OK &&
                              isfinite(status.base_measured_deg);
            float deg = encoder_ok ? status.base_measured_deg : 0.0f;
            uart_telemetry_t telemetry = {
                .base_angle_deg = deg,
                .base_angle_rad = deg * (PI / 180.0f),
                .upper_limit_active = status.elevator_upper_limit ? 1u : 0u,
                .encoder_valid = encoder_ok ? 1u : 0u,
            };
            (void)mqtt_publish_telemetry(&telemetry);
        }

        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }

    // Nao deve chegar aqui
    mqtt_stop();
}

static void uart_task(void *pvParameters) {
    (void)pvParameters;
    esp_err_t ret;

    while (!atomic_load(&s_motors_ready)) {
        vTaskDelay(pdMS_TO_TICKS(20));
    }

    ret = init_uart();
    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha ao iniciar UART: %s", esp_err_to_name(ret));
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        uart_command_t cmd;

        for (int i = 0; i < 8 && uart_read(&cmd); i++) {
            if (cmd.motor_mask & UART_MOTOR_ELEVATOR) {
                ret = motors_apply(MOTOR_ELEVATOR, cmd.elevator_cm);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Elevador: comando rejeitado (%s)", esp_err_to_name(ret));
            }
            if (cmd.motor_mask & UART_MOTOR_BASE) {
                ret = motors_apply(MOTOR_BASE, cmd.base_angle_deg);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Base: comando rejeitado (%s)", esp_err_to_name(ret));
            }
            if (cmd.motor_mask & UART_MOTOR_WRIST) {
                ret = motors_apply(MOTOR_WRIST, cmd.wrist_angle_deg);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Pulso: comando rejeitado (%s)", esp_err_to_name(ret));
            }
            if (cmd.motor_mask & UART_MOTOR_GRIPPER) {
                ret = motors_apply(MOTOR_GRIPPER, cmd.gripper_angle_deg);
                if (ret != ESP_OK)
                    ESP_LOGW(COMM_TAG, "Garra: comando rejeitado (%s)", esp_err_to_name(ret));
            }
        }

        motors_status_t status;
        if (motors_get_status(&status) == ESP_OK) {
            bool encoder_ok = status.base_sensor_error == ESP_OK &&
                              isfinite(status.base_measured_deg);
            float deg = encoder_ok ? status.base_measured_deg : 0.0f;
            uart_telemetry_t telemetry = {
                .base_angle_deg = deg,
                .base_angle_rad = deg * (PI / 180.0f),
                .upper_limit_active = status.elevator_upper_limit ? 1u : 0u,
                .encoder_valid = encoder_ok ? 1u : 0u,
            };
            (void)uart_send_telemetry(&telemetry);
        }

        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }
}

static void actuators_task(void *pvParameters) {
    (void)pvParameters;
    ESP_LOGI(ACT_TAG, "Inicializando motores e sensores do manipulador");

    // Configuração mecânica.
    const motors_config_t config = {
        // Elevador com fuso de esferas
        .elevator_lead_mm_per_rev = 5.0f,  // Confirmar avanco
        .elevator_full_steps_per_rev = 200, // Confirmar passo do motor
        .elevator_microsteps = 2,          // DRV8825: M0 HIGH, M1/M2 LOW
        .elevator_dir_high_is_up = true,   // Confirmar sentido de subida

        // Base rotativa com correia
        .base_full_steps_per_rev = 200,
        .base_microsteps = 2,
        .base_motor_turns_per_base_turn = 1.0f, // Confirmar polias
        .base_dir_high_increases_angle = true, // Confirmar sentido

        // Sensor magnetico e PID de posicao angular
        .encoder_direction = AS5600_DIR_CLOCKWISE,
        .base_tolerance_deg = 0.5f,
        .base_pid = {
            .kp = 0.6f,
            .ki = 0.0f,
            .kd = 0.0f,
            .max_output = 4.0f,
            .min_output = -4.0f,
            .max_integral = 0.0f,
            .min_integral = 0.0f,
            .cal_type = PID_CAL_TYPE_POSITIONAL,
        },
    };

    esp_err_t ret = motors_init(&config);
    if (ret != ESP_OK) {
        ESP_LOGE(ACT_TAG, "Falha ao iniciar motores: %s", esp_err_to_name(ret));
        vTaskDelete(NULL);
        return;
    }

    atomic_store(&s_motors_ready, true);
    ESP_LOGI(ACT_TAG, "Motores inicializados");

    // Mantem a task de atuacao original como supervisora de diagnosticos.
    // O proprio motors ja atualiza PID, AS5600 e fim de curso internamente.
    TickType_t xLastWakeTime = xTaskGetTickCount();
    TickType_t xFrequency = pdMS_TO_TICKS(CNTRL_PERIOD_MS);
    if (xFrequency == 0) xFrequency = 1;

    esp_err_t last_encoder_error = ESP_OK;
    esp_err_t last_elevator_error = ESP_OK;
    esp_err_t last_base_error = ESP_OK;

    while (1) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);

        motors_status_t status;
        if (motors_get_status(&status) != ESP_OK) continue;

        // Logs somente em mudancas de erro (nao a cada periodo).
        if (status.base_sensor_error != last_encoder_error) {
            if (status.base_sensor_error != ESP_OK)
                ESP_LOGW(ACT_TAG, "Erro AS5600: %s", esp_err_to_name(status.base_sensor_error));
            last_encoder_error = status.base_sensor_error;
        }
        if (status.elevator_error != last_elevator_error) {
            if (status.elevator_error != ESP_OK)
                ESP_LOGE(ACT_TAG, "Erro elevador: %s", esp_err_to_name(status.elevator_error));
            last_elevator_error = status.elevator_error;
        }
        if (status.base_stepper_error != last_base_error) {
            if (status.base_stepper_error != ESP_OK)
                ESP_LOGE(ACT_TAG, "Erro stepper base: %s", esp_err_to_name(status.base_stepper_error));
            last_base_error = status.base_stepper_error;
        }
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

    // Task 1 (core 0): comunicacao
    if (COMM_MODE == MQTT){
        if (xTaskCreatePinnedToCore(mqtt_task, "mqtt_task", 4096, NULL, 5, NULL, 0) != pdPASS)
            return ESP_ERR_NO_MEM;
    } else if (COMM_MODE == UART){
        if (xTaskCreatePinnedToCore(uart_task, "uart_task", 4096, NULL, 5, NULL, 0) != pdPASS)
            return ESP_ERR_NO_MEM;
    }

    // Task 2 (core 1): atuacao
    if (xTaskCreatePinnedToCore(actuators_task, "actuators_task", 4096, NULL, 5, NULL, 1) != pdPASS)
        return ESP_ERR_NO_MEM;

    return ESP_OK;
}