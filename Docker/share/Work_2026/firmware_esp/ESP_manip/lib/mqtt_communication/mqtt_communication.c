#include "mqtt_communication.h"
#include "utils.h"         // Acesso às variáveis G_*
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "cJSON.h"
#include <string.h>
#include <math.h>

// Wi-Fi Credentials
#define INTERNAL_WIFI_SSID       "atenaopen2023"
#define INTERNAL_WIFI_PASS       "rrrmmmaaa"

// MQTT Broker & Topics
#define INTERNAL_BROKER_URI      "mqtt://192.168.1.100"
#define TOPIC_CMD_MANIPULATOR    "command/manipulator"
#define TOPIC_STATE_DISTANCE     "state/ultrasonic_distance"

static const char *TAG = "MQTT";
static esp_mqtt_client_handle_t s_client = NULL;

static void wifi_init_sta(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = INTERNAL_WIFI_SSID,
            .password = INTERNAL_WIFI_PASS,
        },
    };
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(ESP_IF_WIFI_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    
    ESP_LOGI(TAG, "Conectando ao Wi-Fi SSID: %s ...", INTERNAL_WIFI_SSID);
    ESP_ERROR_CHECK(esp_wifi_connect());
}

static void parse_json_command(const char *payload, int len) {
    cJSON *root = cJSON_ParseWithLength(payload, len);
    if (!root) {
        ESP_LOGW(TAG, "JSON invalido recebido");
        return;
    }

    // Extração segura dos campos
    cJSON *arm   = cJSON_GetObjectItem(root, "arm");
    cJSON *base  = cJSON_GetObjectItem(root, "base");
    cJSON *wrist = cJSON_GetObjectItem(root, "wrist");
    cJSON *grip  = cJSON_GetObjectItem(root, "grip");

    // Atualiza Globais
    if (cJSON_IsNumber(arm)) {
        G_STEPPER_ARM = (float)arm->valuedouble;
    }
    if (cJSON_IsNumber(base)) {
        G_STEPPER_BASE = (float)base->valuedouble;
    }
    if (cJSON_IsNumber(wrist)) {
        G_SERVO_WRIST = (float)wrist->valuedouble;
    }
    if (cJSON_IsNumber(grip)) {
        G_SERVO_GRIPPER = (float)grip->valuedouble;
    }

    cJSON_Delete(root);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t) event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT Conectado! Inscrevendo em: %s", TOPIC_CMD_MANIPULATOR);
            esp_mqtt_client_subscribe(s_client, TOPIC_CMD_MANIPULATOR, 0);
            break;

        case MQTT_EVENT_DATA:
            if (strncmp(event->topic, TOPIC_CMD_MANIPULATOR, event->topic_len) == 0) {
                parse_json_command(event->data, event->data_len);
            }
            break;
        
        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "Erro no cliente MQTT");
            break;

        default:
            break;
    }
}

void init_mqtt(void) {
    // Inicializa Stack Wi-Fi
    wifi_init_sta();

    // Configura Cliente MQTT
    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = INTERNAL_BROKER_URI,
    };

    s_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(s_client, MQTT_EVENT_ANY, mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_client);
}

void publish_mqtt_telemetry(void) {
    if (!s_client) return;

    cJSON *root = cJSON_CreateObject();
    
    // Timestamp
    cJSON_AddNumberToObject(root, "ts_ms", (double)G_US_TS_MS);
    
    // Dados dos sensores (tratando NAN como 0.0 para compatibilidade JSON)
    cJSON_AddNumberToObject(root, "front_left",  isnan(G_US_CM[0]) ? 0.0 : G_US_CM[0]);
    cJSON_AddNumberToObject(root, "front_right", isnan(G_US_CM[1]) ? 0.0 : G_US_CM[1]);
    cJSON_AddNumberToObject(root, "rear_left",   isnan(G_US_CM[2]) ? 0.0 : G_US_CM[2]);

    char *payload = cJSON_PrintUnformatted(root);
    if (payload) {
        esp_mqtt_client_publish(s_client, TOPIC_STATE_DISTANCE, payload, 0, 0, 0);
        free(payload);
    }
    cJSON_Delete(root);
}

void mqtt_stop(){
    if (s_client) {
        esp_mqtt_client_stop(s_client);
        esp_mqtt_client_destroy(s_client);
        s_client = NULL;
    }
}