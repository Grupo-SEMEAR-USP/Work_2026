
#include <stdio.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_log.h"
#include "esp_err.h"
#include "driver/gpio.h"

#include "utils.h"

static const char *TAG = "ENC_DEBUG";

void app_main(void) {

    // Teste isolado do encoder dianteiro direito
    gpio_config_t io_config = {
        .pin_bit_mask =
            (1ULL << ENC_TD_CHA) |
            (1ULL << ENC_TD_CHB),

        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    ESP_ERROR_CHECK(gpio_config(&io_config));

    int last_a = gpio_get_level(ENC_TD_CHA);
    int last_b = gpio_get_level(ENC_TD_CHB);

    uint32_t changes_a = 0;
    uint32_t changes_b = 0;

    TickType_t last_print = xTaskGetTickCount();

    while (1) {

        int a = gpio_get_level(ENC_TD_CHA);
        int b = gpio_get_level(ENC_TD_CHB);

        if (a != last_a) {
            changes_a++;
            last_a = a;
        }

        if (b != last_b) {
            changes_b++;
            last_b = b;
        }

        TickType_t now = xTaskGetTickCount();

        if ((now - last_print) >= pdMS_TO_TICKS(1000)) {

            ESP_LOGI(TAG,
                "A=%d | B=%d | Mudancas A=%lu | Mudancas B=%lu",
                a, b,
                (unsigned long)changes_a,
                (unsigned long)changes_b
            );

            changes_a = 0;
            changes_b = 0;
            last_print = now;
        }

        vTaskDelay(1);
    }
}