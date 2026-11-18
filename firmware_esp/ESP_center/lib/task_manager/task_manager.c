
#include "task_manager.h"

#include <math.h>
#include <stdint.h>
#include <stddef.h>
#include <stdatomic.h>
#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/gpio.h"

#include "mqtt_communication.h"
#include "uart_communication.h"
#include "motors.h"
#include "utils.h"

static atomic_bool s_motors_ready = ATOMIC_VAR_INIT(false);

// Protecao das variaveis compartilhadas entre os nucleos
static portMUX_TYPE s_cmd_mux = portMUX_INITIALIZER_UNLOCKED;

// Confirmacao de conclusao do ultimo comando
static bool s_mov_complete = false;
static uint32_t s_cmd_generation = 0;

/* Tags de Log */
static const char *COMM_TAG = "COMM_TASK";
static const char *ACT_TAG = "ACT_TASK";
static const char *TAG = "TASKS";

// Formato exigido pelo frame_test.py atual:
// TX Jetson -> Center: <Bffff> (17 B de payload).
// RX Center -> Jetson: <ffBBB> (11 B de payload).
_Static_assert(sizeof(uart_command_t) == 17, "UART Center: comando deve ter 17 bytes (sem sequence)");
_Static_assert(sizeof(uart_telemetry_t) == 11, "UART Center: telemetria deve ter 11 bytes (com mov_complete)");

static void mqtt_task(void *pvParameters) {
    (void)pvParameters;

    // O MQTT utiliza o controle dos motores; aguarda a inicializacao.
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
        bool pending;

        // Recepcao: so retirar o proximo comando quando o anterior
        // nao estiver aguardando a task de atuacao.
        taskENTER_CRITICAL(&s_cmd_mux);
        pending = G_MOTOR_CMD_READY;
        taskEXIT_CRITICAL(&s_cmd_mux);

        if (!pending && mqtt_read(&cmd)) {
            taskENTER_CRITICAL(&s_cmd_mux);
            G_MOTOR_CMD = cmd;           // Ultimo comando fica salvo para debug da main.
            G_MOTOR_CMD_READY = true;    // Aviso para a actuators_task.
            s_mov_complete = false;
            ++s_cmd_generation;
            taskEXIT_CRITICAL(&s_cmd_mux);
        }

        // Publica telemetria no MQTT somente com conexao.
        if (mqtt_is_connected()) {
            uart_telemetry_t telemetry = {0};
            motors_status_t status;

            if (motors_get_status(&status) == ESP_OK) {
                bool encoder_ok = status.base_sensor_error == ESP_OK &&
                                  isfinite(status.base_measured_deg);
                float deg = encoder_ok ? status.base_measured_deg : 0.0f;
                telemetry.base_angle_deg = deg;
                telemetry.base_angle_rad = deg * (PI / 180.0f);
                telemetry.upper_limit_active = status.elevator_upper_limit ? 1u : 0u;
                telemetry.encoder_valid = encoder_ok ? 1u : 0u;
            }

            taskENTER_CRITICAL(&s_cmd_mux);
            telemetry.mov_complete = s_mov_complete ? 1u : 0u;
            taskEXIT_CRITICAL(&s_cmd_mux);

            (void)mqtt_publish_telemetry(&telemetry);
        }

        vTaskDelay(pdMS_TO_TICKS(COMM_PERIOD_MS));
    }
}

static void uart_task(void *pvParameters) {
    (void)pvParameters;

    // A porta serial pode funcionar mesmo se motors_init() falhar.
    // Isso permite receber e observar frames durante o diagnostico.
    esp_err_t ret = init_uart();
    if (ret != ESP_OK) {
        ESP_LOGE(COMM_TAG, "Falha ao iniciar UART: %s", esp_err_to_name(ret));
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGI(COMM_TAG, "UART inicializada; aguardando comandos");
    bool tx_error_reported = false;

    while (1) {
        uart_command_t cmd;

        // A recepcao UART nao depende da task de atuacao.
        // Mesmo sem AS5600/motores, cada frame valido atualiza G_MOTOR_CMD
        // para que a main e o frame_test.py possam diagnosticar a comunicacao.
        if (uart_read(&cmd)) {
            const bool motors_ready = atomic_load(&s_motors_ready);

            taskENTER_CRITICAL(&s_cmd_mux);
            G_MOTOR_CMD = cmd;              // Ultimo frame valido, preservado para debug.
            G_MOTOR_CMD_READY = motors_ready; // Pendente SO se a atuacao esta disponivel.
            s_mov_complete = false;          // Recebimento nao significa movimento concluido.
            ++s_cmd_generation;
            taskEXIT_CRITICAL(&s_cmd_mux);

            // Em operacao normal, o novo comando substitui eventual pendencia
            // anterior. Se motores_init falhou, nenhum comando fica aguardando
            // execucao futura, mas o ultimo recebido continua na global.
            ESP_LOGI(COMM_TAG,
                     "RX UART mask=%u | elev=%.2f | base=%.2f | wrist=%.2f | grip=%.2f",
                     (unsigned)cmd.motor_mask, (double)cmd.elevator_cm,
                     (double)cmd.base_angle_deg, (double)cmd.wrist_angle_deg,
                     (double)cmd.gripper_angle_deg);
            if (!motors_ready) {
                ESP_LOGW(COMM_TAG,
                         "UART recebido, mas motores indisponiveis; comando nao aplicado");
            }
        }

        // Envia telemetria em todos os ciclos, inclusive se o status
        // estiver indisponivel. Nessa situacao encoder_valid permanece 0.
        uart_telemetry_t telemetry = {0};
        motors_status_t status;

        if (atomic_load(&s_motors_ready) &&
            motors_get_status(&status) == ESP_OK) {
            bool encoder_ok = status.base_sensor_error == ESP_OK &&
                              isfinite(status.base_measured_deg);
            float deg = encoder_ok ? status.base_measured_deg : 0.0f;
            telemetry.base_angle_deg = deg;
            telemetry.base_angle_rad = deg * (PI / 180.0f);
            telemetry.upper_limit_active = status.elevator_upper_limit ? 1u : 0u;
            telemetry.encoder_valid = encoder_ok ? 1u : 0u;
        }

        taskENTER_CRITICAL(&s_cmd_mux);
        telemetry.mov_complete = s_mov_complete ? 1u : 0u;
        taskEXIT_CRITICAL(&s_cmd_mux);

        ret = uart_send_telemetry(&telemetry);
        if (ret != ESP_OK && !tx_error_reported) {
            ESP_LOGW(COMM_TAG, "Falha ao enviar telemetria UART: %s",
                     esp_err_to_name(ret));
            tx_error_reported = true;
        } else if (ret == ESP_OK) {
            tx_error_reported = false;
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
        .elevator_lead_mm_per_rev = 6.0f,  // Avanço fuso
        .elevator_full_steps_per_rev = 200, // NEMA 17
        .elevator_microsteps = 2,          // DRV8825: M0 HIGH, M1/M2 LOW
        .elevator_dir_high_is_up = true,   // Confirmar sentido de subida

        // Base rotativa com correia
        .base_full_steps_per_rev = 200,
        .base_microsteps = 2,
        .base_motor_turns_per_base_turn = 20.0f, // De acordo com Pedrão
        .base_dir_high_increases_angle = true, // Confirmar sentido

        // Sensor magnetico e PID de posicao angular
        .encoder_direction = AS5600_DIR_COUNTERCLOCKWISE,
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
        ESP_LOGE(ACT_TAG, "Falha ao iniciar motores: %s",
                 esp_err_to_name(ret));
        vTaskDelete(NULL);
        return;
    }

    atomic_store(&s_motors_ready, true);
    ESP_LOGI(ACT_TAG, "Motores inicializados");

    TickType_t xLastWakeTime = xTaskGetTickCount();
    TickType_t xFrequency = pdMS_TO_TICKS(CNTRL_PERIOD_MS);
    if (xFrequency == 0) xFrequency = 1;

    esp_err_t last_encoder_error = ESP_OK;
    esp_err_t last_elevator_error = ESP_OK;
    esp_err_t last_base_error = ESP_OK;

    // Estado do ultimo comando recebido
    bool command_active = false;
    uint8_t active_mask = 0;
    uint32_t active_generation = 0;

    while (1) {

        /*=== Aplicacao dos comandos recebidos ===*/

        uart_command_t cmd;
        uint32_t generation = 0;
        bool received = false;

        // A task consome a pendencia, mas NAO apaga G_MOTOR_CMD.
        // A main continua podendo exibir o ultimo comando recebido.
        taskENTER_CRITICAL(&s_cmd_mux);
        if (G_MOTOR_CMD_READY) {
            cmd = G_MOTOR_CMD;
            generation = s_cmd_generation;
            G_MOTOR_CMD_READY = false;
            received = true;
        }
        taskEXIT_CRITICAL(&s_cmd_mux);

        if (received) {

            bool accepted = true;
            active_mask = cmd.motor_mask;
            active_generation = generation;

            if (cmd.motor_mask & UART_MOTOR_ELEVATOR) {

                // Se ja estiver no limite superior, nao solicitar nova subida.
                motors_status_t elevator_status;
                bool at_upper_limit =
                    cmd.elevator_cm > 0.0f &&
                    gpio_get_level(FIM_CS) == HIGH &&
                    motors_get_status(&elevator_status) == ESP_OK &&
                    !elevator_status.elevator_busy &&
                    elevator_status.elevator_error == ESP_OK;

                ret = at_upper_limit ?
                      ESP_OK :
                      motors_apply(MOTOR_ELEVATOR, cmd.elevator_cm);

                if (ret != ESP_OK) {
                    accepted = false;
                    ESP_LOGW(ACT_TAG,
                             "Elevador: comando rejeitado (%s)",
                             esp_err_to_name(ret));
                }
            }

            if (cmd.motor_mask & UART_MOTOR_BASE) {
                ret = motors_apply(
                    MOTOR_BASE,
                    cmd.base_angle_deg
                );

                if (ret != ESP_OK) {
                    accepted = false;
                    ESP_LOGW(ACT_TAG,
                             "Base: comando rejeitado (%s)",
                             esp_err_to_name(ret));
                }
            }

            if (cmd.motor_mask & UART_MOTOR_WRIST) {
                ret = motors_apply(
                    MOTOR_WRIST,
                    cmd.wrist_angle_deg
                );

                if (ret != ESP_OK) {
                    accepted = false;
                    ESP_LOGW(ACT_TAG,
                             "Pulso: comando rejeitado (%s)",
                             esp_err_to_name(ret));
                }
            }

            if (cmd.motor_mask & UART_MOTOR_GRIPPER) {
                ret = motors_apply(
                    MOTOR_GRIPPER,
                    cmd.gripper_angle_deg
                );

                if (ret != ESP_OK) {
                    accepted = false;
                    ESP_LOGW(ACT_TAG,
                             "Garra: comando rejeitado (%s)",
                             esp_err_to_name(ret));
                }
            }

            command_active = accepted;
        }

        /*=== Supervisao dos motores e sensores ===*/

        motors_status_t status;

        if (motors_get_status(&status) == ESP_OK) {

            G_FCS_UP = status.elevator_upper_limit;

            /*=== Verificacao de conclusao do movimento ===*/

            if (command_active) {

                bool elevator_done =
                    !(active_mask & UART_MOTOR_ELEVATOR) ||
                    (!status.elevator_busy &&
                     status.elevator_error == ESP_OK);

                bool base_done =
                    !(active_mask & UART_MOTOR_BASE) ||
                    (status.base_target_active &&
                     status.base_on_target &&
                     status.base_sensor_error == ESP_OK &&
                     status.base_stepper_error == ESP_OK);

                // Servos sao considerados concluidos apos motors_apply().
                if (elevator_done && base_done) {
                    // Nao declarar um comando antigo concluido caso um
                    // mais recente ja tenha sido recebido.
                    taskENTER_CRITICAL(&s_cmd_mux);
                    if (active_generation == s_cmd_generation &&
                        !G_MOTOR_CMD_READY) {
                        s_mov_complete = true;
                    }
                    taskEXIT_CRITICAL(&s_cmd_mux);
                    command_active = false;
                }
            }

            if (status.base_sensor_error != last_encoder_error) {
                if (status.base_sensor_error != ESP_OK)
                    ESP_LOGW(ACT_TAG,
                             "Erro AS5600: %s",
                             esp_err_to_name(status.base_sensor_error));

                last_encoder_error = status.base_sensor_error;
            }

            if (status.elevator_error != last_elevator_error) {
                if (status.elevator_error != ESP_OK)
                    ESP_LOGE(ACT_TAG,
                             "Erro elevador: %s",
                             esp_err_to_name(status.elevator_error));

                last_elevator_error = status.elevator_error;
            }

            if (status.base_stepper_error != last_base_error) {
                if (status.base_stepper_error != ESP_OK)
                    ESP_LOGE(ACT_TAG,
                             "Erro stepper base: %s",
                             esp_err_to_name(status.base_stepper_error));

                last_base_error = status.base_stepper_error;
            }
        }

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
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

    // Inicializa o compartilhamento de comandos
    taskENTER_CRITICAL(&s_cmd_mux);
    G_MOTOR_CMD = (uart_command_t){0};
    G_MOTOR_CMD_READY = false;
    s_mov_complete = false;
    s_cmd_generation = 0;
    taskEXIT_CRITICAL(&s_cmd_mux);

    atomic_store(&s_motors_ready, false);

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