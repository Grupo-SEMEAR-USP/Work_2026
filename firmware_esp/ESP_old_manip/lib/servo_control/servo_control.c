#include "servo_control.h"
#include "utils.h"
#include "driver/ledc.h"
#include "esp_log.h"

#define SERVO_MAX_ANGLE 180.0f
#define SERVO_HZ        50
#define SERVO_MIN_US    500
#define SERVO_MAX_US    2500

static const char *TAG = "SERVO";

// Variáveis estáticas para cache local
static float s_last_gripper = 0.0f;
static float s_last_wrist   = 0.0f;

static inline uint32_t us_to_duty(uint32_t period_us, uint32_t pulse_us, uint32_t max_duty) {
    if (pulse_us < SERVO_MIN_US) pulse_us = SERVO_MIN_US;
    if (pulse_us > SERVO_MAX_US) pulse_us = SERVO_MAX_US;
    return (uint32_t)((((uint64_t)pulse_us) * max_duty) / period_us);
}

static esp_err_t channel_cfg(int channel, int gpio) {
    ledc_channel_config_t ch = {
        .gpio_num   = gpio,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel    = channel,
        .intr_type  = LEDC_INTR_DISABLE,
        .timer_sel  = LEDC_TIMER_0,
        .duty       = 0,
        .hpoint     = 0
    };
    return ledc_channel_config(&ch);
}

static esp_err_t write_angle(int channel, float angle_deg, float *last_store) {
    if (angle_deg < 0.f) angle_deg = 0.f;
    if (angle_deg > SERVO_MAX_ANGLE) angle_deg = SERVO_MAX_ANGLE;

    float pulse = SERVO_MIN_US + (angle_deg / SERVO_MAX_ANGLE) * (SERVO_MAX_US - SERVO_MIN_US);
    uint32_t max_duty = (1<<20) - 1;
    uint32_t period_us = 1000000 / SERVO_HZ;
    uint32_t duty = us_to_duty(period_us, (uint32_t)pulse, max_duty);

    ESP_ERROR_CHECK(ledc_set_duty(LEDC_LOW_SPEED_MODE, channel, duty));
    ESP_ERROR_CHECK(ledc_update_duty(LEDC_LOW_SPEED_MODE, channel));

    *last_store = angle_deg;
    return ESP_OK;
}

esp_err_t init_servos(void) {
    ESP_LOGI(TAG, "Inicializando PWM Servos");
    
    ledc_timer_config_t t = {
        .speed_mode       = LEDC_LOW_SPEED_MODE,
        .duty_resolution  = LEDC_TIMER_20_BIT,
        .timer_num        = LEDC_TIMER_0,
        .freq_hz          = SERVO_HZ,
        .clk_cfg          = LEDC_AUTO_CLK
    };
    ESP_ERROR_CHECK(ledc_timer_config(&t));

    ESP_ERROR_CHECK(channel_cfg(LEDC_CHANNEL_0, PIN_SERVO_GRIPPER));
    ESP_ERROR_CHECK(channel_cfg(LEDC_CHANNEL_1, PIN_SERVO_WRIST));

    // Posição inicial segura
    set_servo_gripper(0.0f);
    set_servo_wrist(0.0f);

    return ESP_OK;
}

esp_err_t set_servo_gripper(float angle_deg) {
    return write_angle(LEDC_CHANNEL_0, angle_deg, &s_last_gripper);
}

esp_err_t set_servo_wrist(float angle_deg) {
    return write_angle(LEDC_CHANNEL_1, angle_deg, &s_last_wrist);
}

float get_servo_gripper(void) { return s_last_gripper; }
float get_servo_wrist(void)   { return s_last_wrist; }