#include "h_bridge.h"
#include "utils.h"           
#include "driver/gpio.h"
#include "esp_log.h"

/* Configurações do LEDC */
#define LEDC_MODE          LEDC_HIGH_SPEED_MODE
#define LEDC_FREQUENCY     (5000) // 5 kHz
#define LEDC_TIMER_LEFT    LEDC_TIMER_0
#define LEDC_TIMER_RIGHT   LEDC_TIMER_0
#define LEDC_CHANNEL_LEFT  LEDC_CHANNEL_0
#define LEDC_CHANNEL_RIGHT LEDC_CHANNEL_1

/* Macros */
#define MOTOR_INPUT_1(SIDE) ((ESP_POSITION) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? F_INPUT_LEFT_1 : F_INPUT_RIGHT_1) : \
        ((SIDE) == (MOTOR_LEFT) ? R_INPUT_LEFT_1 : R_INPUT_RIGHT_1)   \
)
#define MOTOR_INPUT_2(SIDE) ((ESP_POSITION) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? F_INPUT_LEFT_2 : F_INPUT_RIGHT_2) : \
        ((SIDE) == (MOTOR_LEFT) ? R_INPUT_LEFT_2 : R_INPUT_RIGHT_2)   \
)
#define MOTOR_PWM(SIDE) ((ESP_POSITION) == (FRONT) ? \
        ((SIDE) == (MOTOR_LEFT) ? F_PWM_LEFT : F_PWM_RIGHT) : \
        ((SIDE) == (MOTOR_LEFT) ? R_PWM_LEFT : R_PWM_RIGHT)   \
)
#define MOTOR_CHANNEL(MOTOR_SIDE) ((MOTOR_SIDE) == (MOTOR_LEFT) ? LEDC_CHANNEL_LEFT : LEDC_CHANNEL_RIGHT)
#define LEDC_TIMER(MOTOR_SIDE) ((MOTOR_SIDE) == (MOTOR_LEFT) ? LEDC_TIMER_LEFT : LEDC_TIMER_RIGHT)
#define STBY ((ESP_POSITION) == (FRONT) ? F_STBY : R_STBY)

static const char *TAG = "H_BRIDGE";

esp_err_t init_h_bridge(motor_side_t side){
    // Inicializa GPIO
    gpio_set_direction(MOTOR_INPUT_1(side), GPIO_MODE_OUTPUT);
    gpio_set_direction(MOTOR_INPUT_2(side), GPIO_MODE_OUTPUT);
    gpio_set_direction(MOTOR_PWM(side), GPIO_MODE_OUTPUT);
    gpio_set_direction(STBY, GPIO_MODE_OUTPUT);
    gpio_set_level(STBY, HIGH);

    ledc_timer_config_t ledc_timer = {
        .speed_mode         = LEDC_MODE,
        .timer_num          = LEDC_TIMER(side),
        .duty_resolution    = LEDC_DUTY_RES,
        .freq_hz            = LEDC_FREQUENCY,
        .clk_cfg            = LEDC_AUTO_CLK
    };
    ESP_ERROR_CHECK(ledc_timer_config(&ledc_timer));

    ledc_channel_config_t ledc_channel = {
        .speed_mode     = LEDC_MODE,
        .channel        = MOTOR_CHANNEL(side),
        .timer_sel      = LEDC_TIMER(side),
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = MOTOR_PWM(side),
        .duty           = 0,
        .hpoint         = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ledc_channel));

    return ESP_OK;
}

// Controla motor para frente, considerando in1 = 1 e in2 = 0
static esp_err_t _set_forward(motor_side_t side){
    gpio_set_level(MOTOR_INPUT_1(side), HIGH);
    gpio_set_level(MOTOR_INPUT_2(side), LOW);

    return ESP_OK;
}

// Controla motor para trás, considerando in1 = 0 e in2 = 1
static esp_err_t _set_backward(motor_side_t side){
    gpio_set_level(MOTOR_INPUT_1(side), LOW);
    gpio_set_level(MOTOR_INPUT_2(side), HIGH);

    return ESP_OK;
}

// Define a velocidade e a direção do motor (assumindo a direção pelo sinal da velocidade)
esp_err_t update_motor(motor_side_t side, float u){
    u > 0 ? _set_forward(side) : _set_backward(side);
    int pwm;
    pwm = (int)(u + 0.5f); // Arredonda o valor de u
    pwm = pwm > 0 ? pwm : -pwm;  // Abs of action control u

    ledc_set_duty(LEDC_MODE, MOTOR_CHANNEL(side), pwm);
    ledc_update_duty(LEDC_MODE, MOTOR_CHANNEL(side));

    return ESP_OK;
}