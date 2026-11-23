
#include <stdio.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_err.h"

#include "utils.h"
#include "task_manager.h"
#include "motors.h"
#include "magnetic_encoder.h"
#include "stepper_control.h"
#include "servo_control.h"
#include "uart_communication.h"

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

    // Debug da comunicação
    bool debug_uart = true;

    // Valores para teste dos servomotores
    float wrist_deg = 45.0f;
    float gripper_deg = 90.0f;

    // Valores para teste isolado dos steppers (passos)
    int32_t elevator_steps = 20;
    int32_t base_steps = 20;

    if (disable_logs) esp_log_level_set("*", ESP_LOG_NONE);

    // Controle dos componentes inicializados individualmente
    bool encoder_ready = false;
    bool fim_curso_ready = false;
    bool steppers_ready = false;
    bool servos_ready = false;

    esp_err_t ret;

    // Contador de voltas do encoder
    int cont = 0;
    float ang_anterior = 0.0f;
    float ang_acumulado = 0.0f;
    bool ang_inicializado = false;

    if (enable_tasks) {
        ESP_LOGI(TAG, "Iniciando tasks");

        ret = init_tasks();

        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Falha na inicializacao das Tasks.");
            return;
        }
    }

    if (!enable_tasks) {

        /*=== Inicializacao individual dos componentes ===*/

        // Encoder magnetico AS5600
        if (debug_encoder) {
            ret = as5600_init(AS5600_DIR_COUNTERCLOCKWISE);

            if (ret == ESP_OK) {
                encoder_ready = true;
                ESP_LOGI(TAG, "AS5600 inicializado");
            } else {
                ESP_LOGE(TAG, "Falha AS5600: %s",
                         esp_err_to_name(ret));
            }
        }

        // Fim de curso superior
        if (debug_fim_curso || debug_elevator) {
            gpio_config_t limit_cfg = {
                .pin_bit_mask = 1ULL << FIM_CS,
                .mode = GPIO_MODE_INPUT,
                .pull_up_en = GPIO_PULLUP_DISABLE,
                .pull_down_en = GPIO_PULLDOWN_ENABLE,
                .intr_type = GPIO_INTR_DISABLE,
            };

            ret = gpio_config(&limit_cfg);

            if (ret == ESP_OK) {
                fim_curso_ready = true;
                ESP_LOGI(TAG, "Fim de curso inicializado");
            } else {
                ESP_LOGE(TAG, "Falha fim de curso: %s",
                         esp_err_to_name(ret));
            }
        }

        // Motores de passo
        if (debug_elevator || debug_base) {
            ret = init_steppers();

            if (ret == ESP_OK) {
                steppers_ready = true;
                ESP_LOGI(TAG, "Steppers inicializados");
            } else {
                ESP_LOGE(TAG, "Falha steppers: %s",
                         esp_err_to_name(ret));
            }
        }

        // Servomotores
        if (debug_wrist || debug_gripper) {
            ret = init_servos();

            if (ret == ESP_OK) {
                servos_ready = true;
                ESP_LOGI(TAG, "Servos inicializados");
            } else {
                ESP_LOGE(TAG, "Falha servos: %s",
                         esp_err_to_name(ret));
            }
        }
    }

    ESP_LOGI(TAG, "UART comando: %u bytes",
             (unsigned)sizeof(uart_command_t));

    ESP_LOGI(TAG, "UART telemetria: %u bytes",
             (unsigned)sizeof(uart_telemetry_t));

    bool debug_commands_sent = false;

    while (1) {

        /*=== Debug com as tasks habilitadas ===*/

        if (enable_tasks) {
            motors_status_t status;
            bool status_valid = motors_get_status(&status) == ESP_OK;

            /*=== Contagem de voltas do encoder ===*/

            if (status_valid &&
                status.base_sensor_error == ESP_OK &&
                isfinite(status.base_measured_deg)) {

                float ang_atual = status.base_measured_deg;

                if (!ang_inicializado) {
                    ang_anterior = ang_atual;
                    ang_inicializado = true;
                } else {
                    float delta = ang_atual - ang_anterior;

                    // Corrige a passagem entre 0 e 360 graus
                    if (delta > 180.0f) {
                        delta -= 360.0f;
                    } else if (delta < -180.0f) {
                        delta += 360.0f;
                    }

                    ang_acumulado += delta;
                    cont = (int)(ang_acumulado / 360.0f);

                    ang_anterior = ang_atual;
                }
            }

            if (status_valid) {

                // Debug Encoder AS5600
                if (debug_encoder) {
                    if (status.base_sensor_error == ESP_OK) {
                        ESP_LOGI(TAG, "AS5600: %.2f graus | %.4f rad",
                                 G_ENCMAG_ANGLE_DEG,
                                 G_ENCMAG_ANGLE_RAD);
                        ESP_LOGI(TAG, "Voltas completas: %d", cont);
                    } else {
                        ESP_LOGW(TAG, "Falha na leitura do AS5600");
                    }
                }

                // Debug Fim de Curso
                if (debug_fim_curso) {
                    ESP_LOGI(TAG, "Fim de curso: %s",
                             status.elevator_upper_limit ?
                             "ATIVO" : "INATIVO");
                }

                // Debug dos motores
                if (debug_elevator) {
                    ESP_LOGI(TAG, "Elevador: %.2f cm | Busy: %d | Erro: %s",
                             status.elevator_estimated_cm,
                             status.elevator_busy,
                             esp_err_to_name(status.elevator_error));
                }

                if (debug_base) {
                    ESP_LOGI(TAG, "Base: Alvo %.2f | Medido %.2f | No alvo: %d",
                             status.base_target_deg,
                             status.base_measured_deg,
                             status.base_on_target);
                }

                if (debug_wrist) {
                    ESP_LOGI(TAG, "Pulso: %.2f graus",
                             get_servo_wrist());
                }

                if (debug_gripper) {
                    ESP_LOGI(TAG, "Garra: %.2f graus",
                             get_servo_gripper());
                }
            }

            // Debug da comunicacao UART
            if (debug_uart && COMM_MODE == UART && !disable_logs) {

                uart_command_t cmd;
                bool cmd_ready;
                bool mov_complete;

                task_manager_debug_snapshot(
                    &cmd, &cmd_ready, &mov_complete
                );

                ESP_LOGI(TAG, "CMD READY: %d", cmd_ready);

                ESP_LOGI(TAG, "=== Variaveis recebidas UART ===");

                ESP_LOGI(TAG, "Motor Mask: %u", cmd.motor_mask);
                ESP_LOGI(TAG, "Elevador: %.2f cm", cmd.elevator_cm);
                ESP_LOGI(TAG, "Base: %.2f graus", cmd.base_angle_deg);
                ESP_LOGI(TAG, "Pulso: %.2f graus", cmd.wrist_angle_deg);
                ESP_LOGI(TAG, "Garra: %.2f graus", cmd.gripper_angle_deg);

                ESP_LOGI(TAG, "=== Variaveis enviadas UART ===");

                if (status_valid) {
                    bool encoder_ok =
                        status.base_sensor_error == ESP_OK &&
                        isfinite(status.base_measured_deg);

                    float deg = encoder_ok ?
                                status.base_measured_deg : 0.0f;

                    ESP_LOGI(TAG, "Base medida: %.2f graus", deg);
                    ESP_LOGI(TAG, "Base medida: %.4f rad",
                             deg * (PI / 180.0f));

                    ESP_LOGI(TAG, "Quantidade de voltas completas: %d", cont);
                    ESP_LOGI(TAG, "Angulo acumulado: %.2f graus",
                             ang_acumulado);

                    ESP_LOGI(TAG, "Fim de curso superior: %d",
                             status.elevator_upper_limit ? 1 : 0);

                    ESP_LOGI(TAG, "Encoder valido: %d",
                             encoder_ok ? 1 : 0);
                } else {
                    ESP_LOGW(TAG, "Status dos motores indisponivel");
                }

                ESP_LOGI(TAG, "Movimento concluido: %d",
                         mov_complete ? 1 : 0);

                if (status_valid) {
                    ESP_LOGI(TAG, "=== Estado dos motores ===");

                    ESP_LOGI(TAG, "Elevador ocupado: %d",
                             status.elevator_busy);

                    ESP_LOGI(TAG, "Elevador estimado: %.2f cm",
                             status.elevator_estimated_cm);

                    ESP_LOGI(TAG, "Base alvo: %.2f graus",
                             status.base_target_deg);

                    ESP_LOGI(TAG, "Base no alvo: %d",
                             status.base_on_target);
                }
            }
        }

        /*=== Debug individual dos componentes ===*/

        if (!enable_tasks) {

            // Debug Encoder AS5600
            if (debug_encoder && encoder_ready) {
                ret = as5600_update();

                if (ret == ESP_OK) {
                    ESP_LOGI(TAG, "AS5600: %.2f graus | %.4f rad",
                             G_ENCMAG_ANGLE_DEG,
                             G_ENCMAG_ANGLE_RAD);
                } else {
                    ESP_LOGW(TAG, "Falha AS5600: %s",
                             esp_err_to_name(ret));
                }
            }

            // Debug Fim de Curso
            if (debug_fim_curso && fim_curso_ready) {
                G_FCS_UP = gpio_get_level(FIM_CS) == HIGH;

                ESP_LOGI(TAG, "Fim de curso: %s",
                         G_FCS_UP ? "ATIVO" : "INATIVO");
            }

            // Debug dos motores (executa uma unica vez)
            if (!debug_commands_sent) {
                debug_commands_sent = true;

                // Elevador: teste direto em passos
                if (debug_elevator &&
                    steppers_ready &&
                    fim_curso_ready) {

                    if (elevator_steps > 0 &&
                        gpio_get_level(FIM_CS) == HIGH) {
                        ESP_LOGW(TAG,
                                 "Subida bloqueada: fim de curso ativo");
                    } else {
                        ret = stepper_move(
                            STEPPER_ELEVATOR, elevator_steps);

                        ESP_LOGI(TAG, "Elevador: %s",
                                 esp_err_to_name(ret));
                    }
                }

                // Base: teste direto em passos
                if (debug_base && steppers_ready) {
                    ret = stepper_move(STEPPER_BASE, base_steps);

                    ESP_LOGI(TAG, "Base: %s",
                             esp_err_to_name(ret));
                }

                // Pulso
                if (debug_wrist && servos_ready) {
                    ret = set_servo_wrist(wrist_deg);

                    ESP_LOGI(TAG, "Pulso: %s",
                             esp_err_to_name(ret));
                }

                // Garra
                if (debug_gripper && servos_ready) {
                    ret = set_servo_gripper(gripper_deg);

                    ESP_LOGI(TAG, "Garra: %s",
                             esp_err_to_name(ret));
                }
            }

            // Estado dos steppers
            if (steppers_ready) {
                if (debug_elevator) {
                    ESP_LOGI(TAG, "Elevador idle: %d | Erro: %s",
                             is_stepper_motor_idle(STEPPER_ELEVATOR),
                             esp_err_to_name(
                                 stepper_get_last_error(STEPPER_ELEVATOR)));
                }

                if (debug_base) {
                    ESP_LOGI(TAG, "Base idle: %d | Erro: %s",
                             is_stepper_motor_idle(STEPPER_BASE),
                             esp_err_to_name(
                                 stepper_get_last_error(STEPPER_BASE)));
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
