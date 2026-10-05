#include "switch.h"

esp_err_t init_switch() {
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << SWITCH_PIN),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    return gpio_config(&io_conf);
}

void update_switch_state() {
    if(gpio_get_level(SWITCH_PIN) == 0) {
        G_SWITCH_PRESSED = true;  // Switch pressionado
    } else {
        G_SWITCH_PRESSED = false; // Switch não pressionado
    }
}