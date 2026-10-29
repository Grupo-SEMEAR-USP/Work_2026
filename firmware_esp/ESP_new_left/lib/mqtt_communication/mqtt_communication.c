#include "mqtt_communication.h"
#include "utils.h"

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "mqtt_client.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#include <string.h>
#include <math.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdint.h> 

/* Wi-Fi Credentials */
#define INTERNAL_WIFI_SSID       "atenaopen2023"
#define INTERNAL_WIFI_PASS       "rrrmmmaaa"

/* MQTT Broker & Topics */
#define INTERNAL_BROKER_URI  "mqtt://192.168.1.100"
#define TOPIC_ULTRASONIC     "state/ultrasonic"

#define US_NUM_COUNT        6

static const char *TAG = "MQTT";

static esp_mqtt_client_handle_t s_client = NULL;
static atomic_bool s_mqtt_connected = ATOMIC_VAR_INIT(false);
static bool s_mqtt_started = false;

/* Eventos de Wi-Fi */
static void wifi_event_handler(
    void *arg,
    esp_event_base_t base,
    int32_t event_id,
    void *event_data
) {
    if (base == WIFI_EVENT) {

        if (event_id == WIFI_EVENT_STA_START) {
            esp_wifi_connect();

        } else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
            atomic_store(&s_mqtt_connected, false);

            ESP_LOGW(TAG, "Wi-Fi desconectado. Reconectando...");
            esp_wifi_connect();
        }

    } else if (base == IP_EVENT &&
               event_id == IP_EVENT_STA_GOT_IP) {

        ESP_LOGI(TAG, "Wi-Fi conectado. IP obtido.");

        // Inicia o cliente MQTT após obter IP
        if (s_client && !s_mqtt_started) {
            esp_err_t err = esp_mqtt_client_start(s_client);

            if (err == ESP_OK) {
                s_mqtt_started = true;
            } else {
                ESP_LOGE(TAG, "Falha ao iniciar MQTT: %s",
                         esp_err_to_name(err));
            }
        }
    }
}

/* Inicialização Wi-Fi */
static void wifi_init_sta(void) {

    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_register(
        WIFI_EVENT,
        WIFI_EVENT_STA_START,
        wifi_event_handler,
        NULL
    ));

    ESP_ERROR_CHECK(esp_event_handler_register(
        WIFI_EVENT,
        WIFI_EVENT_STA_DISCONNECTED,
        wifi_event_handler,
        NULL
    ));

    ESP_ERROR_CHECK(esp_event_handler_register(
        IP_EVENT,
        IP_EVENT_STA_GOT_IP,
        wifi_event_handler,
        NULL
    ));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = INTERNAL_WIFI_SSID,
            .password = INTERNAL_WIFI_PASS,
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));

    ESP_ERROR_CHECK(esp_wifi_set_config(
        WIFI_IF_STA,
        &wifi_config
    ));

    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Wi-Fi inicializado.");
}

/* Eventos MQTT */
static void mqtt_event_handler(
    void *handler_args,
    esp_event_base_t base,
    int32_t event_id,
    void *event_data
) {
    switch ((esp_mqtt_event_id_t)event_id) {

        case MQTT_EVENT_CONNECTED:
            atomic_store(&s_mqtt_connected, true);
            ESP_LOGI(TAG, "MQTT conectado ao broker.");
            break;

        case MQTT_EVENT_DISCONNECTED:
            atomic_store(&s_mqtt_connected, false);
            ESP_LOGW(TAG, "MQTT desconectado.");
            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "Erro no cliente MQTT.");
            break;

        default:
            break;
    }
}

/* Inicialização MQTT */
void init_mqtt(void) {

    // Inicializa stack de rede e loop de eventos
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Configura cliente MQTT
    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = INTERNAL_BROKER_URI,
    };

    s_client = esp_mqtt_client_init(&mqtt_cfg);

    if (s_client == NULL) {
        ESP_LOGE(TAG, "Falha ao criar cliente MQTT.");
        return;
    }

    ESP_ERROR_CHECK(esp_mqtt_client_register_event(
        s_client,
        MQTT_EVENT_ANY,
        mqtt_event_handler,
        NULL
    ));

    // Inicializa Wi-Fi após configurar o MQTT
    wifi_init_sta();
}

/* Adiciona distância ao JSON */
static void json_add_distance(
    cJSON *root,
    const char *name,
    float value
) {
    if (isfinite(value)) {
        cJSON_AddNumberToObject(root, name, (double)value);
    } else {
        cJSON_AddNullToObject(root, name);
    }
}

/* Publicação da Telemetria */
void publish_mqtt_telemetry(void) {

    // Verifica disponibilidade do MQTT
    if (s_client == NULL ||
        !atomic_load(&s_mqtt_connected)) {
        return;
    }

    // Snapshot local dos sensores
    float readings[US_NUM_COUNT];
    uint64_t timestamp;

    memcpy(readings, G_US_CM, sizeof(readings));
    timestamp = G_US_TS_MS;

    // Aguarda a primeira varredura completa
    if (timestamp == 0) {
        return;
    }

    // Cria objeto JSON
    cJSON *root = cJSON_CreateObject();

    if (root == NULL) {
        ESP_LOGE(TAG, "Falha ao criar JSON.");
        return;
    }

    // Timestamp da aquisição
    cJSON_AddNumberToObject(
        root, "ts_ms", (double)timestamp
    );

    // Distâncias dos 6 ultrassônicos (cm)
    json_add_distance(root, "us_esq_1", readings[0]);
    json_add_distance(root, "us_esq_2", readings[1]);
    json_add_distance(root, "us_dir_1", readings[2]);
    json_add_distance(root, "us_dir_2", readings[3]);
    json_add_distance(root, "us_frt_1", readings[4]);
    json_add_distance(root, "us_trs_1", readings[5]);

    // Serializa JSON
    char *payload = cJSON_PrintUnformatted(root);

    if (payload != NULL) {

        // Enfileira telemetria QoS 0, sem retain
        int msg_id = esp_mqtt_client_enqueue(
            s_client,
            TOPIC_ULTRASONIC,
            payload,
            0,      // Tamanho calculado automaticamente
            0,      // QoS 0
            0,      // Retain false
            true    // Armazena na fila de envio
        );

        if (msg_id < 0) {
            ESP_LOGW(TAG, "Falha ao enfileirar telemetria.");
        }

        cJSON_free(payload);
    }

    cJSON_Delete(root);
}

/* Finalização MQTT */
void mqtt_stop(void) {

    atomic_store(&s_mqtt_connected, false);

    if (s_client != NULL) {

        if (s_mqtt_started) {
            esp_mqtt_client_stop(s_client);
        }

        esp_mqtt_client_destroy(s_client);

        s_client = NULL;
        s_mqtt_started = false;

        ESP_LOGI(TAG, "Cliente MQTT finalizado.");
    }
}