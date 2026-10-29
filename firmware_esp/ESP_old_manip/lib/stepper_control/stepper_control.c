#include "stepper_control.h"
#include "utils.h"         // Pinos
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <math.h>
#include <stdlib.h>
#include <stdatomic.h>

#define STEPPER_MAX_SPEED 1000.f
#define STEPPER_ACCEL     500.f

static const char* TAG = "STEPPER";

// Variáveis de controle de movimento (Atômicas para thread-safety)
static _Atomic int s_remain_e = 0; // Elevador
static _Atomic int s_remain_b = 0; // Base

static void pulse_blocking(_Atomic int *remain_ptr, int gpio_step, int gpio_dir) {
    // Captura e zera o contador atomicamente
    int remain = atomic_exchange(remain_ptr, 0);
    if (remain == 0) return;

    // Configura direção
    int dir = (remain > 0) ? 1 : 0;
    gpio_set_level(gpio_dir, dir);

    int steps = abs(remain);
    const uint32_t pulse_us = 5; 
    
    // Simples cálculo de período fixo (sem rampa complexa)
    float sps = STEPPER_MAX_SPEED;
    if (sps < 1.0f) sps = 1.0f;
    uint32_t period_us = (uint32_t)(1000000.0f / sps);
    if (period_us <= pulse_us) period_us = pulse_us + 1;
    uint32_t low_us = period_us - pulse_us;

    // Gera pulsos
    for (int i = 0; i < steps; ++i) {
        gpio_set_level(gpio_step, 1);
        esp_rom_delay_us(pulse_us);
        gpio_set_level(gpio_step, 0);

        if (low_us >= 2000) {
            vTaskDelay(pdMS_TO_TICKS(low_us / 1000));
            uint32_t r = low_us % 1000;
            if (r) esp_rom_delay_us(r);
        } else {
            esp_rom_delay_us(low_us);
        }
        
        // Evita travar watchdog em movimentos longos
        if ((i & 0xFF) == 0) taskYIELD();
    }
}

esp_err_t init_steppers(void) {
    ESP_LOGI(TAG, "Inicializando Steppers");

    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << PIN_STEP_ELEVATOR) | (1ULL << PIN_DIR_ELEVATOR) |
                        (1ULL << PIN_STEP_BASE)     | (1ULL << PIN_DIR_BASE),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    ESP_ERROR_CHECK(gpio_config(&io_conf));

    // Estado inicial
    gpio_set_level(PIN_STEP_ELEVATOR, 0);
    gpio_set_level(PIN_STEP_BASE, 0);

    // Limpa variáveis
    atomic_store(&s_remain_e, 0);
    atomic_store(&s_remain_b, 0);

    return ESP_OK;
}

void move_stepper_elevator(int steps) {
    atomic_fetch_add(&s_remain_e, steps);
}

void move_stepper_base(int steps) {
    atomic_fetch_add(&s_remain_b, steps);
}

void stepper_loop_process(void) {
    if (atomic_load(&s_remain_e) != 0) {
        pulse_blocking(&s_remain_e, PIN_STEP_ELEVATOR, PIN_DIR_ELEVATOR);
    }
    if (atomic_load(&s_remain_b) != 0) {
        pulse_blocking(&s_remain_b, PIN_STEP_BASE, PIN_DIR_BASE);
    }
}

bool is_stepper_idle(void) {
    return (atomic_load(&s_remain_e) == 0 && atomic_load(&s_remain_b) == 0);
}