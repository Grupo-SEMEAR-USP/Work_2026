#include "ultrasonic_distance.h"
#include "ultrasonic.h" // Componente Driver (Baixo Nível)
#include "utils.h"      // Hardware Map (Pinos) e Globais
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <math.h>

#define US_NUM_COUNT  6
#define DIST_MAX_RANGE_M   2.0f 
#define DIST_PING_DELAY_MS 10

static const char *TAG = "US_DIST";

// Instâncias internas dos drivers
static ultrasonic_sensor_t s_sensors[US_NUM_COUNT];

esp_err_t init_ultrasonic_distance() {
    ESP_LOGI(TAG, "Inicializando %d Sensores.", US_NUM_COUNT);

    // Sensor 0: Esq_1
    s_sensors[0].trigger_pin = L_TRIG_ESQ_1;
    s_sensors[0].echo_pin    = L_ECHO_ESQ_1;

    // Sensor 1: Esq_2
    s_sensors[1].trigger_pin = L_TRIG_ESQ_2;
    s_sensors[1].echo_pin    = L_ECHO_ESQ_2;

    // Sensor 2: Dir_1
    s_sensors[2].trigger_pin = L_TRIG_DIR_1;
    s_sensors[2].echo_pin    = L_ECHO_DIR_1;

    // Sensor 3: Dir_2
    s_sensors[3].trigger_pin = L_TRIG_DIR_2;
    s_sensors[3].echo_pin    = L_ECHO_DIR_2;

    // Sensor 4: Frt_1
    s_sensors[4].trigger_pin = L_TRIG_FRT_1;
    s_sensors[4].echo_pin    = L_ECHO_FRT_1;

    // Sensor 5: Trs_1
    s_sensors[5].trigger_pin = L_TRIG_TRS_1;
    s_sensors[5].echo_pin    = L_ECHO_TRS_1;

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
            G_US_CM[i] = dist_m * 100.0f; // Metros para Centímetros
        } else {
            G_US_CM[i] = NAN;
        }
        
        // Pequeno delay para evitar eco cruzado entre sensores
        vTaskDelay(pdMS_TO_TICKS(DIST_PING_DELAY_MS));
    }
    
    // Atualiza Timestamp
    G_US_TS_MS = (uint64_t)(esp_timer_get_time() / 1000ULL);
}