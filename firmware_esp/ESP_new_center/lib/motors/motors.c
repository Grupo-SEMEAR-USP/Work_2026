#include "motors.h"
#include "utils.h"
#include "stepper_control.h"
#include "servo_control.h"

#include <math.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>
#include <stdatomic.h>

#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

// Permite inspecionar o fim de curso e o encoder entre transmissoes.
#define MOTORS_ELEVATOR_BLOCK_STEPS 4
#define MOTORS_BASE_BLOCK_STEPS     4
#define MOTORS_POLL_MS              5
#define MOTORS_TASK_STACK           4096
#define MOTORS_TASK_PRIORITY        4
#define MOTORS_LIMIT_RELEASE_READS  2

static const char *TAG = "MOTORS";

static motors_config_t s_cfg;
static SemaphoreHandle_t s_mutex = NULL;
static pid_ctrl_block_handle_t s_pid = NULL;
static TaskHandle_t s_task = NULL;
static atomic_bool s_initialized = ATOMIC_VAR_INIT(false);
static double s_elevator_steps_per_cm = 0.0;
static float s_base_steps_per_deg = 0.0f;

// Todas estas variaveis sao acessadas sob s_mutex.
static int64_t s_elevator_pending = 0;
static int32_t s_elevator_inflight = 0;
static float s_elevator_estimated_cm = 0.0f;
static bool s_upper_limit = false;
static unsigned s_limit_release_count = 0;
static esp_err_t s_elevator_error = ESP_OK;

static bool s_base_target_active = false;
static bool s_base_settled = false;
static bool s_base_pid_reset_needed = false;
static float s_base_target_deg = 0.0f;
static float s_base_measured_deg = NAN;
static bool s_base_inflight = false;
static esp_err_t s_base_sensor_error = ESP_OK;
static esp_err_t s_base_stepper_error = ESP_OK;

static bool valid_config(const motors_config_t *c)
{
    if (c == NULL) return false;
    if (!isfinite(c->elevator_lead_mm_per_rev) || c->elevator_lead_mm_per_rev <= 0.0f ||
        c->elevator_full_steps_per_rev == 0 || c->elevator_microsteps == 0 ||
        c->base_full_steps_per_rev == 0 || c->base_microsteps == 0 ||
        !isfinite(c->base_motor_turns_per_base_turn) || c->base_motor_turns_per_base_turn <= 0.0f ||
        !isfinite(c->base_tolerance_deg) || c->base_tolerance_deg <= 0.0f ||
        c->base_tolerance_deg >= 180.0f ||
        (c->encoder_direction != AS5600_DIR_CLOCKWISE &&
         c->encoder_direction != AS5600_DIR_COUNTERCLOCKWISE)) {
        return false;
    }

    const pid_ctrl_parameter_t *p = &c->base_pid;
    return p->cal_type == PID_CAL_TYPE_POSITIONAL &&
           isfinite(p->kp) && isfinite(p->ki) && isfinite(p->kd) &&
           isfinite(p->max_output) && isfinite(p->min_output) &&
           isfinite(p->max_integral) && isfinite(p->min_integral) &&
           p->max_output > 0.0f && p->min_output < 0.0f &&
           p->min_integral <= p->max_integral;
}

static float wrap_360(float deg)
{
    float out = fmodf(deg, 360.0f);
    return (out < 0.0f) ? out + 360.0f : out;
}

static float shortest_error_deg(float target, float actual)
{
    float err = fmodf(target - actual + 540.0f, 360.0f) - 180.0f;
    return err; // intervalo [-180,180), menor caminho circular
}

static void update_elevator_locked(bool limit_high)
{
    s_upper_limit = limit_high;
    if (limit_high) {
        s_limit_release_count = 0;
    } else if (s_limit_release_count < MOTORS_LIMIT_RELEASE_READS) {
        s_limit_release_count++;
    }

    // So contabilizar passos depois de conclusao confirmada pelo driver.
    if (s_elevator_inflight != 0 && is_stepper_motor_idle(STEPPER_ELEVATOR)) {
        esp_err_t err = stepper_get_last_error(STEPPER_ELEVATOR);
        if (err == ESP_OK) {
            s_elevator_estimated_cm += (float)((double)s_elevator_inflight /
                                                 s_elevator_steps_per_cm);
            s_elevator_pending -= s_elevator_inflight;
        } else {
            // Quantidade de pulsos realmente executados torna-se desconhecida.
            s_elevator_error = err;
            s_elevator_pending = 0;
            ESP_LOGE(TAG, "Elevador: erro no driver de passos: %s", esp_err_to_name(err));
        }
        s_elevator_inflight = 0;
    }

    // Fim de curso superior: cancela subida ainda pendente.
    if (limit_high && s_elevator_pending > 0) {
        // Manter contabilizados os passos que ja estao em execucao
        int64_t still_inflight = (s_elevator_inflight > 0) ?
                                  s_elevator_inflight : 0;
        if (s_elevator_pending != still_inflight) {
            s_elevator_pending = still_inflight;
            ESP_LOGW(TAG, "Fim de curso superior ativo; subida pendente cancelada");
        }
    }

    if (s_elevator_error != ESP_OK || s_elevator_inflight != 0 ||
        s_elevator_pending == 0 || !is_stepper_motor_idle(STEPPER_ELEVATOR)) {
        return;
    }

    // Exigir duas leituras em LOW para liberar nova subida.
    if (s_elevator_pending > 0 &&
        (limit_high || s_limit_release_count < MOTORS_LIMIT_RELEASE_READS)) {
        return;
    }

    int64_t remaining = s_elevator_pending;
    int32_t batch = (remaining > MOTORS_ELEVATOR_BLOCK_STEPS) ?
                     MOTORS_ELEVATOR_BLOCK_STEPS :
                    (remaining < -MOTORS_ELEVATOR_BLOCK_STEPS) ?
                    -MOTORS_ELEVATOR_BLOCK_STEPS : (int32_t)remaining;

    // Sinal logico positivo representa subida, independentemente da montagem.
    int32_t driver_steps = s_cfg.elevator_dir_high_is_up ? batch : -batch;
    esp_err_t err = stepper_move(STEPPER_ELEVATOR, driver_steps);
    if (err == ESP_OK) {
        s_elevator_inflight = batch;
    } else if (err != ESP_ERR_TIMEOUT) {
        s_elevator_error = err;
        s_elevator_pending = 0;
        ESP_LOGE(TAG, "Nao foi possivel comandar elevador: %s", esp_err_to_name(err));
    }
}

static void update_base_inflight_locked(void)
{
    if (s_base_inflight && is_stepper_motor_idle(STEPPER_BASE)) {
        s_base_inflight = false;
        esp_err_t err = stepper_get_last_error(STEPPER_BASE);
        if (err != ESP_OK) {
            s_base_stepper_error = err;
            s_base_target_active = false;
            ESP_LOGE(TAG, "Base: erro no RMT: %s", esp_err_to_name(err));
        }
    }
}

static void update_base_pid_locked(bool fresh_sensor)
{
    if (!fresh_sensor || !s_base_target_active || s_base_inflight ||
        s_base_stepper_error != ESP_OK || !is_stepper_motor_idle(STEPPER_BASE)) {
        return;
    }

    float err_deg = shortest_error_deg(s_base_target_deg, s_base_measured_deg);
    if (fabsf(err_deg) <= s_cfg.base_tolerance_deg) {
        // Anti-windup: zerar acumulador uma vez quando atingir o alvo.
        if (!s_base_settled) {
            (void)pid_reset_ctrl_block(s_pid);
        }
        s_base_settled = true;
        return;
    }
    s_base_settled = false;

    if (s_base_pid_reset_needed) {
        (void)pid_reset_ctrl_block(s_pid);
        s_base_pid_reset_needed = false;
    }

    // Conversao do erro angular para passos equivalentes no eixo do motor
    float error_steps = err_deg * s_base_steps_per_deg;
    float output_steps = 0.0f;
    esp_err_t err = pid_compute(s_pid, error_steps, &output_steps);
    if (err != ESP_OK || !isfinite(output_steps)) {
        s_base_stepper_error = (err == ESP_OK) ? ESP_FAIL : err;
        s_base_target_active = false;
        return;
    }

    // Limitar mesmo quando o PID estiver configurado com max_output alto.
    if (output_steps > MOTORS_BASE_BLOCK_STEPS) output_steps = MOTORS_BASE_BLOCK_STEPS;
    if (output_steps < -MOTORS_BASE_BLOCK_STEPS) output_steps = -MOTORS_BASE_BLOCK_STEPS;
    int32_t batch = (int32_t)lroundf(output_steps);

    // Evita que quantizacao gere saida zero fora da tolerancia.
    if (batch == 0) batch = (err_deg > 0.0f) ? 1 : -1;

    // Correção deve sempre seguir o sinal do erro, mesmo com PID mal ajustado.
    if ((batch > 0 && err_deg < 0.0f) || (batch < 0 && err_deg > 0.0f)) {
        batch = (err_deg > 0.0f) ? 1 : -1;
    }

    int32_t driver_steps = s_cfg.base_dir_high_increases_angle ? batch : -batch;
    err = stepper_move(STEPPER_BASE, driver_steps);
    if (err == ESP_OK) {
        s_base_inflight = true;
    } else if (err != ESP_ERR_TIMEOUT) {
        s_base_stepper_error = err;
        s_base_target_active = false;
        ESP_LOGE(TAG, "Nao foi possivel comandar base: %s", esp_err_to_name(err));
    }
}

static void motors_worker(void *arg)
{
    (void)arg;
    TickType_t poll_ticks = pdMS_TO_TICKS(MOTORS_POLL_MS);
    if (poll_ticks == 0) poll_ticks = 1;
    TickType_t base_ticks = pdMS_TO_TICKS(CNTRL_PERIOD_MS);
    if (base_ticks == 0) base_ticks = 1;
    TickType_t last_base = xTaskGetTickCount() - base_ticks;

    for (;;) {
        const bool upper_limit_high = gpio_get_level(C_FIM_CS) == 1;
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        update_elevator_locked(upper_limit_high);
        update_base_inflight_locked();
        xSemaphoreGive(s_mutex);

        TickType_t now = xTaskGetTickCount();
        if ((TickType_t)(now - last_base) >= base_ticks) {
            last_base = now;
            // Somente esta task executa a leitura I2C do AS5600.
            esp_err_t err = as5600_update();
            float angle = G_ENCMAG_ANGLE_DEG;

            xSemaphoreTake(s_mutex, portMAX_DELAY);
            s_base_sensor_error = err;
            if (err == ESP_OK && isfinite(angle)) {
                s_base_measured_deg = wrap_360(angle);
                update_base_pid_locked(true);
            } else if (err == ESP_OK) {
                s_base_sensor_error = ESP_FAIL;
            }
            // Se I2C falhar, não emitir novos passos para a base.
            xSemaphoreGive(s_mutex);
        }
        vTaskDelay(poll_ticks);
    }
}

esp_err_t motors_init(const motors_config_t *config)
{
    if (atomic_load(&s_initialized)) return ESP_OK;
    if (!valid_config(config)) return ESP_ERR_INVALID_ARG;

    // Calculos mecanicos, com drivers isolados da unidade fisica.
    double steps_per_cm = (double)config->elevator_full_steps_per_rev *
                          (double)config->elevator_microsteps * 10.0 /
                          (double)config->elevator_lead_mm_per_rev;
    double base_steps_per_deg = (double)config->base_full_steps_per_rev *
                                (double)config->base_microsteps *
                                (double)config->base_motor_turns_per_base_turn / 360.0;
    if (!isfinite(steps_per_cm) || steps_per_cm < 1.0 ||
        !isfinite(base_steps_per_deg) || base_steps_per_deg <= 0.0 ||
        base_steps_per_deg > 1000000.0) {
        return ESP_ERR_INVALID_ARG;
    }

    s_mutex = xSemaphoreCreateMutex();
    if (s_mutex == NULL) return ESP_ERR_NO_MEM;

    // Chave simples: uma perna em 3V3 e OUT no GPIO.
    // Para fios longos, usar resistor PULL-DOWN EXTERNO e protecao eletrica.
    gpio_config_t limit_cfg = {
        .pin_bit_mask = 1ULL << C_FIM_CS,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t err = gpio_config(&limit_cfg);
    if (err != ESP_OK) goto failure;

    err = init_steppers();
    if (err != ESP_OK) goto failure;
    err = as5600_init(config->encoder_direction);
    if (err != ESP_OK) goto failure;
    err = as5600_update();
    if (err != ESP_OK) goto failure;
    err = init_servos();
    if (err != ESP_OK) goto failure;

    pid_ctrl_config_t pid_config = { .init_param = config->base_pid };
    err = pid_new_control_block(&pid_config, &s_pid);
    if (err != ESP_OK) goto failure;

    s_cfg = *config;
    s_elevator_steps_per_cm = steps_per_cm;
    s_base_steps_per_deg = (float)base_steps_per_deg;
    s_elevator_pending = 0;
    s_elevator_inflight = 0;
    s_elevator_estimated_cm = 0.0f;
    s_upper_limit = gpio_get_level(C_FIM_CS) == 1;
    s_limit_release_count = 0;
    s_elevator_error = ESP_OK;
    s_base_target_active = false;
    s_base_settled = false;
    s_base_pid_reset_needed = false;
    s_base_measured_deg = wrap_360(G_ENCMAG_ANGLE_DEG);
    s_base_sensor_error = ESP_OK;
    s_base_stepper_error = ESP_OK;
    s_base_inflight = false;

    if (xTaskCreate(motors_worker, "motors_ctrl", MOTORS_TASK_STACK,
                    NULL, MOTORS_TASK_PRIORITY, &s_task) != pdPASS) {
        err = ESP_ERR_NO_MEM;
        goto failure;
    }

    atomic_store(&s_initialized, true);
    ESP_LOGI(TAG, "Inicializado: %.2f pulsos/cm elevador, %.3f pulsos/grau base",
             (float)s_elevator_steps_per_cm, s_base_steps_per_deg);
    return ESP_OK;

failure:
    ESP_LOGE(TAG, "Falha de inicializacao: %s", esp_err_to_name(err));
    if (s_pid != NULL) {
        (void)pid_del_control_block(s_pid);
        s_pid = NULL;
    }
    if (s_mutex != NULL) {
        vSemaphoreDelete(s_mutex);
        s_mutex = NULL;
    }
    return err;
}

esp_err_t motors_apply(motor_id_t motor, float value)
{
    if (!atomic_load(&s_initialized) || s_mutex == NULL) return ESP_ERR_INVALID_STATE;
    if (!isfinite(value)) return ESP_ERR_INVALID_ARG;

    switch (motor) {
    case MOTOR_ELEVATOR: {
        if (value == 0.0f) return ESP_OK;
        double exact = (double)value * s_elevator_steps_per_cm;
        if (!isfinite(exact) || fabs(exact) > (double)INT32_MAX) {
            return ESP_ERR_INVALID_ARG;
        }
        int64_t command_steps = (int64_t)llround(exact);
        if (command_steps == 0) return ESP_ERR_INVALID_ARG;

        // Checagem imediata; a task repete a verificacao entre blocos.
        if (command_steps > 0 && gpio_get_level(C_FIM_CS) == 1) {
            return ESP_ERR_INVALID_STATE;
        }
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        if (s_elevator_error != ESP_OK) {
            xSemaphoreGive(s_mutex);
            return ESP_ERR_INVALID_STATE;
        }
        if ((command_steps > 0 && s_elevator_pending > INT32_MAX - command_steps) ||
            (command_steps < 0 && s_elevator_pending < INT32_MIN - command_steps)) {
            xSemaphoreGive(s_mutex);
            return ESP_ERR_INVALID_ARG;
        }
        s_elevator_pending += command_steps;
        xSemaphoreGive(s_mutex);
        return ESP_OK;
    }
    case MOTOR_BASE:
        if (value < 0.0f || value > 360.0f) return ESP_ERR_INVALID_ARG;
        xSemaphoreTake(s_mutex, portMAX_DELAY);
        if (s_base_stepper_error != ESP_OK) {
            xSemaphoreGive(s_mutex);
            return ESP_ERR_INVALID_STATE;
        }
        float next_target = wrap_360(value);
        if (!s_base_target_active ||
            fabsf(shortest_error_deg(next_target, s_base_target_deg)) > 0.0001f) {
            s_base_target_deg = next_target;
            s_base_target_active = true;
            s_base_pid_reset_needed = true;
            s_base_settled = false;
        }
        xSemaphoreGive(s_mutex);
        return ESP_OK;

    case MOTOR_WRIST:
        return set_servo_wrist(value);
    case MOTOR_GRIPPER:
        return set_servo_gripper(value);
    default:
        return ESP_ERR_INVALID_ARG;
    }
}

esp_err_t motors_cancel_elevator(void)
{
    if (!atomic_load(&s_initialized)) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    // Preservar o bloco em voo na contagem; apenas nao enviar os demais.
    s_elevator_pending = s_elevator_inflight;
    xSemaphoreGive(s_mutex);
    return ESP_OK;
}

esp_err_t motors_get_status(motors_status_t *status)
{
    if (status == NULL) return ESP_ERR_INVALID_ARG;
    if (!atomic_load(&s_initialized)) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    *status = (motors_status_t) {
        .elevator_upper_limit = s_upper_limit,
        .elevator_busy = (s_elevator_pending != 0 || s_elevator_inflight != 0),
        .elevator_estimated_cm = s_elevator_estimated_cm,
        .elevator_error = s_elevator_error,
        .base_target_active = s_base_target_active,
        .base_on_target = s_base_target_active && s_base_settled && !s_base_inflight &&
                          s_base_sensor_error == ESP_OK,
        .base_target_deg = s_base_target_deg,
        .base_measured_deg = s_base_measured_deg,
        .base_sensor_error = s_base_sensor_error,
        .base_stepper_error = s_base_stepper_error,
    };
    xSemaphoreGive(s_mutex);
    return ESP_OK;
}