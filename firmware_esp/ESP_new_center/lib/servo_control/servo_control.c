#include "servo_control.h"
#include "utils.h"

#include <math.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include "driver/ledc.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#define SERVO_GRIPPER_GPIO C_SERVO_1
#define SERVO_WRIST_GPIO   C_SERVO_2

#define SERVO_GRIPPER_MIN_US 500U
#define SERVO_GRIPPER_MAX_US 2500U
#define SERVO_WRIST_MIN_US   500U
#define SERVO_WRIST_MAX_US   2500U

#define SERVO_MAX_ANGLE_DEG  180.0f
#define SERVO_FREQUENCY_HZ   50U
#define SERVO_DUTY_BITS      16U
#define SERVO_DUTY_SCALE     (1UL << SERVO_DUTY_BITS)
#define SERVO_PERIOD_US      (1000000UL / SERVO_FREQUENCY_HZ)

#define SERVO_TIMER          LEDC_TIMER_0
#define SERVO_SPEED_MODE     LEDC_LOW_SPEED_MODE
#define SERVO_CH_GRIPPER     LEDC_CHANNEL_0
#define SERVO_CH_WRIST       LEDC_CHANNEL_1

static const char *TAG = "SERVO";

// Atualizado somente apos sucesso na escrita
static float s_last_gripper = NAN;
static float s_last_wrist = NAN;
static SemaphoreHandle_t s_lock = NULL;
static bool s_initialized = false;

static esp_err_t configure_channel(ledc_channel_t channel, int gpio)
{
    ledc_channel_config_t cfg = {
        .gpio_num   = gpio,
        .speed_mode = SERVO_SPEED_MODE,
        .channel    = channel,
        .intr_type  = LEDC_INTR_DISABLE,
        .timer_sel  = SERVO_TIMER,
        .duty       = 0,
        .hpoint     = 0,
    };
    return ledc_channel_config(&cfg);
}

static uint32_t angle_to_duty(float angle_deg,
                              uint32_t pulse_min_us,
                              uint32_t pulse_max_us)
{
    float pulse_us = (float)pulse_min_us
        + (angle_deg / SERVO_MAX_ANGLE_DEG)
        * (float)(pulse_max_us - pulse_min_us);

    // Converter tempo alto (us) em contagem do LEDC, arredondando.
    uint32_t pulse_rounded_us = (uint32_t)(pulse_us + 0.5f);
    return (uint32_t)(((uint64_t)pulse_rounded_us * SERVO_DUTY_SCALE
                       + (SERVO_PERIOD_US / 2U)) / SERVO_PERIOD_US);
}

static esp_err_t write_angle(ledc_channel_t channel, float angle_deg,
                             uint32_t pulse_min_us, uint32_t pulse_max_us,
                             float *last_store)
{
    if (!s_initialized || s_lock == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    if (!isfinite(angle_deg)) {
        return ESP_ERR_INVALID_ARG;
    }

    if (angle_deg < 0.0f) angle_deg = 0.0f;
    if (angle_deg > SERVO_MAX_ANGLE_DEG) angle_deg = SERVO_MAX_ANGLE_DEG;

    uint32_t duty = angle_to_duty(angle_deg, pulse_min_us, pulse_max_us);

    // Serializa comandos concorrentes e mantem o cache consistente.
    xSemaphoreTake(s_lock, portMAX_DELAY);
    esp_err_t err = ledc_set_duty_and_update(SERVO_SPEED_MODE,
                                             channel, duty, 0);
    if (err == ESP_OK) {
        *last_store = angle_deg;
    }
    xSemaphoreGive(s_lock);

    return err;
}

esp_err_t init_servos(void)
{
    if (s_initialized) {
        return ESP_OK;
    }

    ESP_LOGI(TAG, "Inicializando dois servos via LEDC");

    ledc_timer_config_t timer_cfg = {
        .speed_mode      = SERVO_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_16_BIT,
        .timer_num       = SERVO_TIMER,
        .freq_hz         = SERVO_FREQUENCY_HZ,
        .clk_cfg         = LEDC_AUTO_CLK,
    };

    esp_err_t err = ledc_timer_config(&timer_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Falha no timer LEDC: %s", esp_err_to_name(err));
        return err;
    }

    err = configure_channel(SERVO_CH_GRIPPER, SERVO_GRIPPER_GPIO);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Falha no canal da garra: %s", esp_err_to_name(err));
        return err;
    }

    err = configure_channel(SERVO_CH_WRIST, SERVO_WRIST_GPIO);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Falha no canal do pulso: %s", esp_err_to_name(err));
        (void)ledc_stop(SERVO_SPEED_MODE, SERVO_CH_GRIPPER, 0);
        return err;
    }

    if (s_lock == NULL) {
        s_lock = xSemaphoreCreateMutex();
    }
    if (s_lock == NULL) {
        (void)ledc_stop(SERVO_SPEED_MODE, SERVO_CH_GRIPPER, 0);
        (void)ledc_stop(SERVO_SPEED_MODE, SERVO_CH_WRIST, 0);
        ESP_LOGE(TAG, "Sem memoria para mutex");
        return ESP_ERR_NO_MEM;
    }

    s_last_gripper = NAN;
    s_last_wrist = NAN;
    s_initialized = true;

    // Nao aplicar 0 ou 90 graus automaticamente: posicao segura depende
    // da montagem e dos limites mecanicos de cada servo.
    ESP_LOGI(TAG, "Servos prontos: garra GPIO %d, pulso GPIO %d",
             SERVO_GRIPPER_GPIO, SERVO_WRIST_GPIO);
    return ESP_OK;
}

esp_err_t set_servo_gripper(float angle_deg)
{
    return write_angle(SERVO_CH_GRIPPER, angle_deg,
                       SERVO_GRIPPER_MIN_US, SERVO_GRIPPER_MAX_US,
                       &s_last_gripper);
}

esp_err_t set_servo_wrist(float angle_deg)
{
    return write_angle(SERVO_CH_WRIST, angle_deg,
                       SERVO_WRIST_MIN_US, SERVO_WRIST_MAX_US,
                       &s_last_wrist);
}

float get_servo_gripper(void)
{
    if (!s_initialized || s_lock == NULL) return NAN;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    float angle = s_last_gripper;
    xSemaphoreGive(s_lock);
    return angle;
}

float get_servo_wrist(void)
{
    if (!s_initialized || s_lock == NULL) return NAN;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    float angle = s_last_wrist;
    xSemaphoreGive(s_lock);
    return angle;
}