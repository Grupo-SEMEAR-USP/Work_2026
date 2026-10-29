#include "stepper_control.h"
#include "utils.h"

#include <math.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "driver/rmt_tx.h"
#include "driver/rmt_encoder.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

// Ajustes iniciais conservadores
#define STEPPER_START_SPEED_SPS    100.0f   // pulsos/s na partida e na parada
#define STEPPER_MAX_SPEED_SPS     1000.0f   // pulsos/s maximos
#define STEPPER_ACCEL_SPS2         500.0f   // pulsos/s²

#define STEPPER_RMT_RES_HZ       1000000U   // tick de 1 us
#define STEPPER_PULSE_HIGH_US         5U   // DRV8825: > 1,9 us
#define STEPPER_CHUNK_STEPS           8U   // pulsos por transacao
#define STEPPER_QUEUE_DEPTH          8U   // comandos por motor
#define STEPPER_TASK_STACK        4096U
#define STEPPER_TASK_PRIORITY        5U
#define STEPPER_TX_TIMEOUT_MS     2000

#define STEPPER_COUNT 2

static const char *TAG = "STEPPER";

typedef struct {
    gpio_num_t step_pin;
    gpio_num_t dir_pin;
    const char *name;
    rmt_channel_handle_t channel;
    rmt_encoder_handle_t encoder;
    QueueHandle_t queue;
    TaskHandle_t task;
    bool channel_enabled;
    atomic_int pending_commands;
    atomic_int last_error;
} stepper_ctx_t;

static stepper_ctx_t s_motor[STEPPER_COUNT] = {
    [STEPPER_ELEVATOR] = {
        .step_pin = C_DRV_STEP_UP,
        .dir_pin = C_DRV_DIR_UP,
        .name = "ELEVATOR",
        .pending_commands = ATOMIC_VAR_INIT(0),
        .last_error = ATOMIC_VAR_INIT(ESP_OK),
    },
    [STEPPER_BASE] = {
        .step_pin = C_DRV_STEP_DOWN,
        .dir_pin = C_DRV_DIR_DOWN,
        .name = "BASE",
        .pending_commands = ATOMIC_VAR_INIT(0),
        .last_error = ATOMIC_VAR_INIT(ESP_OK),
    },
};

static atomic_bool s_initialized = ATOMIC_VAR_INIT(false);

static bool motor_is_valid(stepper_motor_t motor)
{
    return motor == STEPPER_ELEVATOR || motor == STEPPER_BASE;
}

// Perfil trapezoidal limitado por aceleracao e distancia de frenagem.
static uint32_t step_period_us(uint32_t step_index, uint32_t total_steps)
{
    const float v0_sq = STEPPER_START_SPEED_SPS * STEPPER_START_SPEED_SPS;
    const float v_acc = sqrtf(v0_sq + 2.0f * STEPPER_ACCEL_SPS2 * (float)step_index);
    const float v_dec = sqrtf(v0_sq + 2.0f * STEPPER_ACCEL_SPS2 *
                              (float)(total_steps - step_index - 1U));
    float speed = fminf(STEPPER_MAX_SPEED_SPS, fminf(v_acc, v_dec));

    // Com os parametros acima: periodo de 1000 a 10000 us (cabe em 15 bits).
    uint32_t period = (uint32_t)((float)STEPPER_RMT_RES_HZ / speed + 0.5f);
    if (period <= STEPPER_PULSE_HIGH_US + 2U) {
        period = STEPPER_PULSE_HIGH_US + 3U;
    }
    return period;
}

static esp_err_t execute_steps(stepper_ctx_t *motor, int32_t signed_steps)
{
    // Evita overflow de abs(INT32_MIN).
    const uint32_t total_steps = signed_steps < 0
        ? (uint32_t)(-(int64_t)signed_steps) : (uint32_t)signed_steps;

    if (total_steps == 0U) return ESP_OK;

    esp_err_t err = gpio_set_level(motor->dir_pin, signed_steps > 0 ? 1 : 0);
    if (err != ESP_OK) return err;

    // Tempo de setup de DIR antes da borda de subida STEP (> 650 ns).
    esp_rom_delay_us(2);

    rmt_symbol_word_t symbols[STEPPER_CHUNK_STEPS];
    const rmt_transmit_config_t tx_config = {
        .loop_count = 0,
        .flags = {
            .eot_level = 0,
        },
    };

    for (uint32_t done = 0; done < total_steps;) {
        uint32_t count = total_steps - done;
        if (count > STEPPER_CHUNK_STEPS) count = STEPPER_CHUNK_STEPS;

        for (uint32_t i = 0; i < count; ++i) {
            uint32_t period = step_period_us(done + i, total_steps);
            symbols[i] = (rmt_symbol_word_t) {
                .level0 = 1,
                .duration0 = STEPPER_PULSE_HIGH_US,
                .level1 = 0,
                .duration1 = period - STEPPER_PULSE_HIGH_US,
            };
        }

        err = rmt_transmit(motor->channel, motor->encoder,
                           symbols, count * sizeof(symbols[0]), &tx_config);
        if (err != ESP_OK) break;

        // Bloqueia apenas a task interna do motor
        err = rmt_tx_wait_all_done(motor->channel, STEPPER_TX_TIMEOUT_MS);
        if (err != ESP_OK) break;

        done += count;
    }

    if (err != ESP_OK) {
        // Garante o fim da transacao antes de liberar o buffer local e
        // antes de permitir uma mudanca de DIR no proximo comando.
        esp_err_t disable_err = rmt_disable(motor->channel);
        if (disable_err == ESP_OK) {
            motor->channel_enabled = false;
            esp_err_t enable_err = rmt_enable(motor->channel);
            if (enable_err == ESP_OK) {
                motor->channel_enabled = true;
            } else {
                ESP_LOGE(TAG, "%s: falha ao reabilitar RMT: %s",
                         motor->name, esp_err_to_name(enable_err));
            }
        } else {
            ESP_LOGE(TAG, "%s: falha ao desabilitar RMT: %s",
                     motor->name, esp_err_to_name(disable_err));
        }
    }

    return err;
}

static void stepper_worker(void *arg)
{
    stepper_ctx_t *motor = (stepper_ctx_t *)arg;
    int32_t steps;

    while (true) {
        if (xQueueReceive(motor->queue, &steps, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        esp_err_t err = execute_steps(motor, steps);
        atomic_store(&motor->last_error, (int)err);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "%s: movimento falhou: %s",
                     motor->name, esp_err_to_name(err));
        }
        atomic_fetch_sub(&motor->pending_commands, 1);
    }
}

static void release_resources(void)
{
    // Chamada apenas durante falha de inicializacao, antes de liberar o modulo.
    for (int i = 0; i < STEPPER_COUNT; i++) {
        stepper_ctx_t *motor = &s_motor[i];
        if (motor->task != NULL) {
            vTaskDelete(motor->task);
            motor->task = NULL;
        }
    }
    for (int i = 0; i < STEPPER_COUNT; i++) {
        stepper_ctx_t *motor = &s_motor[i];
        if (motor->channel_enabled) {
            rmt_disable(motor->channel);
            motor->channel_enabled = false;
        }
        if (motor->encoder != NULL) {
            rmt_del_encoder(motor->encoder);
            motor->encoder = NULL;
        }
        if (motor->channel != NULL) {
            rmt_del_channel(motor->channel);
            motor->channel = NULL;
        }
        if (motor->queue != NULL) {
            vQueueDelete(motor->queue);
            motor->queue = NULL;
        }
    }
}

esp_err_t init_steppers(void)
{
    if (atomic_load(&s_initialized)) return ESP_OK;

    gpio_config_t dir_config = {
        .pin_bit_mask = (1ULL << C_DRV_DIR_UP) | (1ULL << C_DRV_DIR_DOWN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    esp_err_t err = gpio_config(&dir_config);
    if (err != ESP_OK) return err;

    err = gpio_set_level(C_DRV_DIR_UP, 0);
    if (err != ESP_OK) return err;
    err = gpio_set_level(C_DRV_DIR_DOWN, 0);
    if (err != ESP_OK) return err;

    for (int i = 0; i < STEPPER_COUNT; i++) {
        stepper_ctx_t *motor = &s_motor[i];
        atomic_store(&motor->pending_commands, 0);
        atomic_store(&motor->last_error, ESP_OK);

        motor->queue = xQueueCreate(STEPPER_QUEUE_DEPTH, sizeof(int32_t));
        if (motor->queue == NULL) {
            err = ESP_ERR_NO_MEM;
            goto failed;
        }

        rmt_tx_channel_config_t channel_config = {
            .clk_src = RMT_CLK_SRC_DEFAULT,
            .gpio_num = motor->step_pin,
            .mem_block_symbols = 64,
            .resolution_hz = STEPPER_RMT_RES_HZ,
            .trans_queue_depth = 2,
        };

        err = rmt_new_tx_channel(&channel_config, &motor->channel);
        if (err != ESP_OK) goto failed;

        rmt_copy_encoder_config_t encoder_config = {0};
        err = rmt_new_copy_encoder(&encoder_config, &motor->encoder);
        if (err != ESP_OK) goto failed;

        err = rmt_enable(motor->channel);
        if (err != ESP_OK) goto failed;
        motor->channel_enabled = true;
    }

    for (int i = 0; i < STEPPER_COUNT; i++) {
        stepper_ctx_t *motor = &s_motor[i];
        if (xTaskCreate(stepper_worker,
                        motor->name,
                        STEPPER_TASK_STACK,
                        motor,
                        STEPPER_TASK_PRIORITY,
                        &motor->task) != pdPASS) {
            err = ESP_ERR_NO_MEM;
            goto failed;
        }
    }

    atomic_store(&s_initialized, true);
    ESP_LOGI(TAG, "Dois steppers inicializados (RMT + tasks independentes)");
    return ESP_OK;

failed:
    ESP_LOGE(TAG, "Falha na inicializacao: %s", esp_err_to_name(err));
    release_resources();
    return err;
}

esp_err_t stepper_move(stepper_motor_t motor, int32_t steps)
{
    if (!motor_is_valid(motor)) return ESP_ERR_INVALID_ARG;
    if (!atomic_load(&s_initialized)) return ESP_ERR_INVALID_STATE;
    if (steps == 0) return ESP_OK;

    stepper_ctx_t *ctx = &s_motor[motor];
    // Contagem anterior ao envio evita que o status 'idle' seja verdadeiro
    // entre a entrada na fila e o inicio da execucao.
    atomic_fetch_add(&ctx->pending_commands, 1);
    if (xQueueSend(ctx->queue, &steps, 0) != pdTRUE) {
        atomic_fetch_sub(&ctx->pending_commands, 1);
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

bool is_stepper_motor_idle(stepper_motor_t motor)
{
    if (!motor_is_valid(motor) || !atomic_load(&s_initialized)) return false;
    return atomic_load(&s_motor[motor].pending_commands) == 0;
}

bool is_stepper_idle(void)
{
    return is_stepper_motor_idle(STEPPER_ELEVATOR) &&
           is_stepper_motor_idle(STEPPER_BASE);
}

esp_err_t stepper_get_last_error(stepper_motor_t motor)
{
    if (!motor_is_valid(motor)) return ESP_ERR_INVALID_ARG;
    if (!atomic_load(&s_initialized)) return ESP_ERR_INVALID_STATE;
    return (esp_err_t)atomic_load(&s_motor[motor].last_error);
}