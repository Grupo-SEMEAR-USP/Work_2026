#include "ultrasonic_distance.h"
#include "ultrasonic.h" // Componente Driver (Baixo Nível)
#include "utils.h"      // Hardware Map (Pinos) e Globais
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define US_NUM_COUNT  3
#define DIST_MAX_RANGE_M   2.0f 
#define DIST_PING_DELAY_MS 10

static const char *TAG = "US_DIST";

// Instâncias internas dos drivers
static ultrasonic_sensor_t s_sensors[US_NUM_COUNT];

esp_err_t init_ultrasonic_distance() {
    ESP_LOGI(TAG, "Inicializando %d Sensores.", US_NUM_COUNT);

    // Sensor 0: Front Left
    s_sensors[0].trigger_pin = PIN_US1_TRIG;
    s_sensors[0].echo_pin    = PIN_US1_ECHO;

    // Sensor 1: Front Right
    s_sensors[1].trigger_pin = PIN_US2_TRIG;
    s_sensors[1].echo_pin    = PIN_US2_ECHO;

    // Sensor 2: Rear Left
    s_sensors[2].trigger_pin = PIN_US3_TRIG;
    s_sensors[2].echo_pin    = PIN_US3_ECHO;

    // Inicializa drivers individuais
    for (int i = 0; i < US_NUM_COUNT; ++i) {
        esp_err_t err = ultrasonic_init(&s_sensors[i]);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Falha ao iniciar sensor indice %d", i);
            return err;
        }
    }

    // Limpa estado global
    for (int i = 0; i < US_NUM_COUNT; ++i) G_US_CM[i] = NAN;

    return ESP_OK;
}

void update_ultrasonic_readings() {
    for (int i = 0; i < US_NUM_COUNT; ++i) {
        float dist_m = 0.0f;
        
        esp_err_t res = ultrasonic_measure(&s_sensors[i], DIST_MAX_RANGE_M, &dist_m);

        if (res == ESP_OK) {
            G_US_CM[i] = dist_m * 100.0f; // Metros par Centímetros
        } else {
            G_US_CM[i] = NAN;
        }
        
        // Pequeno delay para evitar eco cruzado entre sensores
        vTaskDelay(pdMS_TO_TICKS(DIST_PING_DELAY_MS));
    }
    
    // Atualiza Timestamp
    G_US_TS_MS = (uint64_t)(esp_timer_get_time() / 1000ULL);
}