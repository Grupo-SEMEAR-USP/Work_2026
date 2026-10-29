#include "h_bridge.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "math.h"

/* Configurações do LEDC */
#define LEDC_MODE          LEDC_HIGH_SPEED_MODE
#define LEDC_FREQUENCY     (5000) // 5 kHz
#define LEDC_TIMER_LEFT_F    LEDC_TIMER_0
#define LEDC_TIMER_RIGHT_F   LEDC_TIMER_0
#define LEDC_TIMER_LEFT_R    LEDC_TIMER_0
#define LEDC_TIMER_RIGHT_R   LEDC_TIMER_0
#define LEDC_CHANNEL_LEFT_F  LEDC_CHANNEL_0
#define LEDC_CHANNEL_RIGHT_F LEDC_CHANNEL_1
#define LEDC_CHANNEL_LEFT_R  LEDC_CHANNEL_2
#define LEDC_CHANNEL_RIGHT_R LEDC_CHANNEL_3

/* Macros */
#define MOTOR_INPUT_1(POS,SIDE) ((POS) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? R_H_BRIDGE_LA_IN1 : R_H_BRIDGE_LB_IN1) : \
        ((SIDE) == (MOTOR_LEFT) ? R_H_BRIDGE_RA_IN1 : R_H_BRIDGE_RB_IN1)   \
)
#define MOTOR_INPUT_2(POS,SIDE) ((POS) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? R_H_BRIDGE_LA_IN2 : R_H_BRIDGE_LB_IN2) : \
        ((SIDE) == (MOTOR_LEFT) ? R_H_BRIDGE_RA_IN2 : R_H_BRIDGE_RB_IN2)   \
)
#define MOTOR_PWM(POS,SIDE) ((POS) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? R_H_BRIDGE_LA_PWM : R_H_BRIDGE_LB_PWM) : \
        ((SIDE) == (MOTOR_LEFT) ? R_H_BRIDGE_RA_PWM : R_H_BRIDGE_RB_PWM)   \
)
#define MOTOR_CHANNEL(POS,SIDE) ((POS) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? LEDC_CHANNEL_LEFT_F : LEDC_CHANNEL_RIGHT_F) : \
        ((SIDE) == (MOTOR_LEFT) ? LEDC_CHANNEL_LEFT_R : LEDC_CHANNEL_RIGHT_R)   \
)
#define LEDC_TIMER(POS,SIDE) ((POS) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? LEDC_TIMER_LEFT_F : LEDC_TIMER_RIGHT_F) : \
        ((SIDE) == (MOTOR_LEFT) ? LEDC_TIMER_LEFT_R : LEDC_TIMER_RIGHT_R)   \
)

static const char *TAG = "H_BRIDGE";

esp_err_t init_h_bridge(pos_t pos, motor_side_t side){
    // Inicializa GPIO
    gpio_set_direction(MOTOR_INPUT_1(pos, side), GPIO_MODE_OUTPUT);
    gpio_set_direction(MOTOR_INPUT_2(pos, side), GPIO_MODE_OUTPUT);
    gpio_set_direction(MOTOR_PWM(pos, side), GPIO_MODE_OUTPUT);

    ledc_timer_config_t ledc_timer = {
        .speed_mode         = LEDC_MODE,
        .timer_num          = LEDC_TIMER(pos,side),
        .duty_resolution    = LEDC_DUTY_RES,
        .freq_hz            = LEDC_FREQUENCY,
        .clk_cfg            = LEDC_AUTO_CLK
    };
    ESP_ERROR_CHECK(ledc_timer_config(&ledc_timer));

    ledc_channel_config_t ledc_channel = {
        .speed_mode     = LEDC_MODE,
        .channel        = MOTOR_CHANNEL(pos,side),
        .timer_sel      = LEDC_TIMER(pos,side),
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = MOTOR_PWM(pos,side),
        .duty           = 0,
        .hpoint         = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ledc_channel));

    return ESP_OK;
}

// Controla motor para frente, considerando in1 = 1 e in2 = 0
static esp_err_t _set_forward(pos_t pos, motor_side_t side){
    gpio_set_level(MOTOR_INPUT_1(pos,side), HIGH);
    gpio_set_level(MOTOR_INPUT_2(pos,side), LOW);

    return ESP_OK;
}

// Controla motor para trás, considerando in1 = 0 e in2 = 1
static esp_err_t _set_backward(pos_t pos, motor_side_t side){
    gpio_set_level(MOTOR_INPUT_1(pos,side), LOW);
    gpio_set_level(MOTOR_INPUT_2(pos,side), HIGH);

    return ESP_OK;
}

// Define a velocidade e a direção do motor (assumindo a direção pelo sinal da velocidade)
// Define a velocidade e a direção do motor (assumindo a direção pelo sinal da velocidade)
esp_err_t update_motor(pos_t pos, motor_side_t side, float u) {
    if (!isfinite(u)) {
        u = 0.0f;
    }

    if (u > LEDC_MAX_DUTY) {
        u = LEDC_MAX_DUTY;
    } else if (u < -LEDC_MAX_DUTY) {
        u = -LEDC_MAX_DUTY;
    }

    uint32_t pwm = (uint32_t)(fabsf(u) + 0.5f);

    esp_err_t ret;

    // Remove o PWM antes de alterar a direção
    ret = ledc_set_duty(LEDC_MODE, MOTOR_CHANNEL(pos, side), 0);
    if (ret != ESP_OK) return ret;

    ret = ledc_update_duty(LEDC_MODE, MOTOR_CHANNEL(pos, side));
    if (ret != ESP_OK) return ret;

    if (pwm == 0) {
        gpio_set_level(MOTOR_INPUT_1(pos, side), LOW);
        gpio_set_level(MOTOR_INPUT_2(pos, side), LOW);
    } else if (u > 0.0f) {
        gpio_set_level(MOTOR_INPUT_1(pos, side), HIGH);
        gpio_set_level(MOTOR_INPUT_2(pos, side), LOW);
    } else {
        gpio_set_level(MOTOR_INPUT_1(pos, side), LOW);
        gpio_set_level(MOTOR_INPUT_2(pos, side), HIGH);
    }

    ret = ledc_set_duty(LEDC_MODE, MOTOR_CHANNEL(pos, side), pwm);
    if (ret != ESP_OK) return ret;

    return ledc_update_duty(LEDC_MODE, MOTOR_CHANNEL(pos, side));
}