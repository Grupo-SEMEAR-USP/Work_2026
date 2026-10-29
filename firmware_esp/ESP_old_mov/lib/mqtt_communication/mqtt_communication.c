#include "mqtt_communication.h"
#include <stdio.h>
#include <string.h>
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "mqtt_client.h"
#include <cJSON.h>
#include "utils.h"

/* Configurações Wi-Fi */
#define WIFI_SSID       "atenaopen2023"
#define WIFI_PASS       "rrrmmmaaa"

/* Configurações MQTT */
#define BROKER_URI      "mqtt://192.168.1.100"
#define MQTT_TOPIC_CMD  "command/motors"
#define MQTT_TOPIC_ENC  "state/encoders"

static const char *TAG = "MQTT_COMM";

static esp_mqtt_client_handle_t s_client = NULL;

static void parse_motor_command(const char *data, int len, SemaphoreHandle_t mutex_handle){
    cJSON *root = cJSON_ParseWithLength(data, len);
    if (root == NULL) {
        ESP_LOGW(TAG, "Falha ao realizar parse do JSON recebido");
        return;
    }

    // Determina o sufixo com base na posição (front/rear)
    const char *suffix_pos = (ESP_POSITION == FRONT) ? "_front" : "_rear";
    char left_key[32];
    char right_key[32];

    snprintf(left_key, sizeof(left_key), "left%s", suffix_pos);
    snprintf(right_key, sizeof(right_key), "right%s", suffix_pos);

    cJSON *left_item = cJSON_GetObjectItem(root, left_key);
    cJSON *right_item = cJSON_GetObjectItem(root, right_key);

    if (cJSON_IsNumber(left_item) && cJSON_IsNumber(right_item)) {
        // Verifica se o mutex foi configurado e tenta pegar ele
        if (mutex_handle != NULL) {
            if (xSemaphoreTake(mutex_handle, pdMS_TO_TICKS(10)) == pdTRUE) {
                
                // Região Crítica: Escrita nas Globais
                G_TARGET_L = (float)left_item->valuedouble;
                G_TARGET_R = (float)right_item->valuedouble;

                xSemaphoreGive(mutex_handle); // Libera o mutex
            } else {
                ESP_LOGW(TAG, "Nao foi possivel obter Mutex para atualizar Targets");
            }
        } else {
            // Se não tiver mutex (debug), escreve direto
            G_TARGET_L = (float)left_item->valuedouble;
            G_TARGET_R = (float)right_item->valuedouble;
        }
    } else {
        ESP_LOGW(TAG, "JSON nao contem chaves esperadas");
    }

    cJSON_Delete(root);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data){
    SemaphoreHandle_t mutex_handle = (SemaphoreHandle_t)handler_args;
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t) event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "MQTT Conectado. Inscrevendo em: %s", MQTT_TOPIC_CMD);
            esp_mqtt_client_subscribe(s_client, MQTT_TOPIC_CMD, 0);
            break;

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "MQTT Desconectado");
            break;

        case MQTT_EVENT_DATA:
            // Verifica se o tópico corresponde ao de comandos
            if (event->topic_len == strlen(MQTT_TOPIC_CMD) && 
                strncmp(event->topic, MQTT_TOPIC_CMD, event->topic_len) == 0) {
                
                parse_motor_command(event->data, event->data_len, mutex_handle);
            }
            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT Event Error");
            break;

        default:
            break;
    }
}

void init_wifi(){
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = {};
    // Copia segura das credenciais
    strncpy((char *)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, WIFI_PASS, sizeof(wifi_config.sta.password) - 1);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(ESP_IF_WIFI_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    
    ESP_LOGI(TAG, "Conectando ao Wi-Fi SSID: %s...", WIFI_SSID);
    ESP_ERROR_CHECK(esp_wifi_connect());
}

void mqtt_start(SemaphoreHandle_t mutex_handle){
    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.uri = BROKER_URI;

    s_client = esp_mqtt_client_init(&mqtt_cfg);
    if (s_client == NULL) {
        ESP_LOGE(TAG, "Falha ao inicializar cliente MQTT");
        return;
    }

    // Registra o handler passando o mutex como argumento de contexto
    esp_mqtt_client_register_event(s_client, MQTT_EVENT_ANY, mqtt_event_handler, (void*)mutex_handle);
    esp_mqtt_client_start(s_client);

    ESP_LOGI(TAG, "Cliente MQTT iniciado. Broker: %s", BROKER_URI);
}

void mqtt_publish_encoders(){
    if (s_client == NULL) {
        return;
    }

    float left_val = G_RADS_L;
    float right_val = G_RADS_R;

    const char *suffix_pos = (ESP_POSITION == FRONT) ? "_front" : "_rear";
    char left_key[32];
    char right_key[32];
    
    snprintf(left_key, sizeof(left_key), "left%s", suffix_pos);
    snprintf(right_key, sizeof(right_key), "right%s", suffix_pos);
    
    cJSON *root = cJSON_CreateObject();
    if (root == NULL) return;

    cJSON_AddNumberToObject(root, left_key, left_val);
    cJSON_AddNumberToObject(root, right_key, right_val);

    char *payload = cJSON_PrintUnformatted(root);
    if (payload != NULL) {
        esp_mqtt_client_publish(s_client, MQTT_TOPIC_ENC, payload, 0, 0, 0);
        free(payload);
    }

    cJSON_Delete(root);
}

void mqtt_stop(){
    if (s_client) {
        esp_mqtt_client_stop(s_client);
        esp_mqtt_client_destroy(s_client);
        s_client = NULL;
        ESP_LOGI(TAG, "MQTT Parado e Destruido");
    }
}