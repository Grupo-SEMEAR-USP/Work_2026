#include "task_manager.h"
#include "utils.h"

/* Módulos de Lib */
#include "servo_control.h"
#include "stepper_control.h"
#include "ultrasonic_distance.h"
#include "mqtt_communication.h"
#include "uart_communication.h"
#include "terminal_cli.h"

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
    
    uart_command_t cmd;
    uart_telemetry_t telem;

    while (1) {
        // Processa entrada
        if (uart_read(&cmd)) {
            // Steppers recebem quanto devem andar em relação à posição atual
            G_STEPPER_ARM  += cmd.arm_val;
            G_STEPPER_BASE += cmd.base_val;
            G_SERVO_WRIST   = fminf(180.f, fmaxf(0.f, cmd.wrist_val));
            G_SERVO_GRIPPER = fminf(180.f, fmaxf(0.f, cmd.grip_val));
        }

        // Envia Telemetria
        telem.front_left  = G_US_CM[0];
        telem.front_right = G_US_CM[1];
        telem.rear_left   = G_US_CM[2];
        uart_send_telemetry(&telem);

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
    // Inicializa Drivers de Hardware
    ESP_ERROR_CHECK(init_servos());
    ESP_ERROR_CHECK(init_steppers());

    // Variáveis para snap
    static float last_arm = 0;
    static float last_base = 0;
    static float last_wrist = -1;
    static float last_grip = -1;

    while (1) {
        float delta_arm = G_STEPPER_ARM - last_arm;
        if (fabs(delta_arm) > 0.1) {
            move_stepper_elevator((int)delta_arm);
            last_arm = G_STEPPER_ARM;
        }

        float delta_base = G_STEPPER_BASE - last_base;
        if (fabs(delta_base) > 0.1) {
            move_stepper_base((int)delta_base);
            last_base = G_STEPPER_BASE;
        }

        // Aplica Servos (Absoluto com verificação de mudança)
        if (G_SERVO_WRIST != last_wrist) {
            set_servo_wrist(G_SERVO_WRIST);
            last_wrist = G_SERVO_WRIST;
        }

        if (G_SERVO_GRIPPER != last_grip) {
            set_servo_gripper(G_SERVO_GRIPPER);
            last_grip = G_SERVO_GRIPPER;
        }

        // Processa loop dos Steppers (Gera pulsos se houver pendência)
        stepper_loop_process();
        vTaskDelay(pdMS_TO_TICKS(CNTRL_PERIOD_MS));
    }
}

// Task dedicada aos sensores ultrassônicos
static void sensors_task(void *pv) {
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
    
    // Inicia sensores (não falha critico, apenas loga)
    if(init_ultrasonic_distance() != ESP_OK) {
        ESP_LOGW(TAG, "Sensores de distancia com falha na inicializacao");
    }

    // Task 1 (core 0): comunicação
    if (COMM_MODE == MQTT){
        xTaskCreatePinnedToCore(mqtt_task, "mqtt_task", 4096, NULL, 5, NULL, 0);
    } else if (COMM_MODE == UART){
        xTaskCreatePinnedToCore(uart_task, "uart_task", 4096, NULL, 5, NULL, 0);
    } else if (COMM_MODE == CLI){
        start_cli_task();
    }
    
    // Task 2 (core 1): atuação
    xTaskCreatePinnedToCore(actuators_task, "actuators_task", 4096, NULL, 5, NULL, 1);
    // Task 3 (core 1): sensores
    xTaskCreatePinnedToCore(sensors_task, "sensors_task", 4096, NULL, 3, NULL, 1);

    return ESP_OK;
}