#include "mqtt_communication.h"

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>

#include "cJSON.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "mqtt_client.h"
#include "nvs_flash.h"

/* Wi-Fi Credentials */
#define WIFI_SSID       "atenaopen2023"
#define WIFI_PASS       "rrrmmmaaa"

#define BROKER_URI             "mqtt://192.168.1.100"
#define MQTT_TOPIC_CMD         "command/motors"
#define MQTT_TOPIC_TELEMETRY   "state/manipulator"
#define MQTT_CMD_QUEUE_LENGTH  8
#define MQTT_MAX_CMD_JSON      256

static const char *TAG = "MQTT_COMM";

static esp_mqtt_client_handle_t s_client = NULL;
static QueueHandle_t s_cmd_queue = NULL;
static bool s_wifi_started = false;
static _Atomic bool s_mqtt_connected = false;
static bool s_have_sequence = false;
static uint16_t s_last_sequence = 0;

// MQTT_EVENT_DATA pode chegar fragmentado em varios eventos
static char s_command_json[MQTT_MAX_CMD_JSON + 1];
static size_t s_json_expected = 0;
static size_t s_json_received = 0;
static bool s_json_accepting = false;

static void wifi_event_handler(void *arg, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    (void)arg;
    (void)event_data;
    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        (void)esp_wifi_connect();
    } else if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi desconectado; tentando reconectar");
        (void)esp_wifi_connect();
    } else if (base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ESP_LOGI(TAG, "Wi-Fi conectado e IP obtido");
    }
}

esp_err_t init_wifi(void)
{
    if (s_wifi_started) return ESP_OK;

    // NVS e usado pelo driver Wi-Fi. Nao apagar NVS automaticamente.
    esp_err_t err = nvs_flash_init();
    if (err != ESP_OK) return err;

    err = esp_netif_init();
    if (err != ESP_OK) return err;

    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) return err;

    esp_netif_t *station = esp_netif_create_default_wifi_sta();
    if (station == NULL) return ESP_ERR_NO_MEM;

    wifi_init_config_t wifi_init = WIFI_INIT_CONFIG_DEFAULT();
    err = esp_wifi_init(&wifi_init);
    if (err != ESP_OK) goto fail_netif;

    err = esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                     wifi_event_handler, NULL);
    if (err != ESP_OK) goto fail_wifi;
    err = esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                     wifi_event_handler, NULL);
    if (err != ESP_OK) goto fail_wifi_handler;

    wifi_config_t wifi_cfg = {0};
    // Copia com verificacao do tamanho, inclusive terminador NUL.
    if (strlen(WIFI_SSID) >= sizeof(wifi_cfg.sta.ssid) ||
        strlen(WIFI_PASS) >= sizeof(wifi_cfg.sta.password)) {
        err = ESP_ERR_INVALID_ARG;
        goto fail_ip_handler;
    }
    memcpy(wifi_cfg.sta.ssid, WIFI_SSID, strlen(WIFI_SSID) + 1);
    memcpy(wifi_cfg.sta.password, WIFI_PASS, strlen(WIFI_PASS) + 1);

    err = esp_wifi_set_mode(WIFI_MODE_STA);
    if (err != ESP_OK) goto fail_ip_handler;
    err = esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg);
    if (err != ESP_OK) goto fail_ip_handler;
    err = esp_wifi_start();
    if (err != ESP_OK) goto fail_ip_handler;

    s_wifi_started = true;
    ESP_LOGI(TAG, "Wi-Fi STA iniciado (SSID: %s)", WIFI_SSID);
    return ESP_OK;

fail_ip_handler:
    (void)esp_event_handler_unregister(IP_EVENT, IP_EVENT_STA_GOT_IP,
                                       wifi_event_handler);
fail_wifi_handler:
    (void)esp_event_handler_unregister(WIFI_EVENT, ESP_EVENT_ANY_ID,
                                       wifi_event_handler);
fail_wifi:
    (void)esp_wifi_deinit();
fail_netif:
    esp_netif_destroy_default_wifi(station);
    return err;
}

static bool get_required_int(const cJSON *root, const char *key,
                             int minimum, int maximum, int *result)
{
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, key);
    if (!cJSON_IsNumber(item)) return false;
    const double value = item->valuedouble;
    if (!isfinite(value) || value < minimum || value > maximum ||
        value != floor(value)) return false;
    *result = (int)value;
    return true;
}

static bool get_masked_float(const cJSON *root, const char *key,
                             bool required, float minimum, float maximum,
                             float *result)
{
    *result = 0.0f;
    if (!required) return true;
    const cJSON *item = cJSON_GetObjectItemCaseSensitive(root, key);
    if (!cJSON_IsNumber(item)) return false;
    double value = item->valuedouble;
    if (!isfinite(value) || value < minimum || value > maximum) return false;
    *result = (float)value;
    return isfinite(*result);
}

static void parse_motor_command(const char *data, size_t length)
{
    cJSON *root = cJSON_ParseWithLength(data, length);
    if (root == NULL || !cJSON_IsObject(root)) {
        ESP_LOGW(TAG, "Comando MQTT: JSON invalido");
        cJSON_Delete(root);
        return;
    }

    int sequence = 0;
    int mask = 0;
    const bool header_ok =
        get_required_int(root, "sequence", 0, UINT16_MAX, &sequence) &&
        get_required_int(root, "motor_mask", 1, UART_MOTOR_ALL, &mask);

    // Campos do struct UART sao packed: nunca passar seus enderecos como float*.
    float elevator = 0.0f, base = 0.0f, wrist = 0.0f, gripper = 0.0f;
    bool valid = header_ok && ((mask & ~UART_MOTOR_ALL) == 0);
    if (valid) {
        valid =
            get_masked_float(root, "elevator_cm",
                             (mask & UART_MOTOR_ELEVATOR) != 0,
                             -INFINITY, INFINITY, &elevator) &&
            get_masked_float(root, "base_angle_deg",
                             (mask & UART_MOTOR_BASE) != 0,
                             0.0f, 360.0f, &base) &&
            get_masked_float(root, "wrist_angle_deg",
                             (mask & UART_MOTOR_WRIST) != 0,
                             0.0f, 180.0f, &wrist) &&
            get_masked_float(root, "gripper_angle_deg",
                             (mask & UART_MOTOR_GRIPPER) != 0,
                             0.0f, 180.0f, &gripper);
    }
    uart_command_t cmd = {
        .sequence = (uint16_t)sequence,
        .motor_mask = (uint8_t)mask,
        .elevator_cm = elevator,
        .base_angle_deg = base,
        .wrist_angle_deg = wrist,
        .gripper_angle_deg = gripper,
    };
    cJSON_Delete(root);

    if (!valid) {
        ESP_LOGW(TAG, "Comando MQTT: campos ou valores invalidos");
        return;
    }
    if (s_have_sequence && cmd.sequence == s_last_sequence) {
        return; // retransmissao do ultimo comando recebido
    }
    if (s_cmd_queue == NULL || xQueueSend(s_cmd_queue, &cmd, 0) != pdTRUE) {
        ESP_LOGW(TAG, "Fila MQTT cheia; comando descartado (seq=%u)",
                 (unsigned)cmd.sequence);
        return;
    }
    s_last_sequence = cmd.sequence;
    s_have_sequence = true;
}

static void process_data_event(const esp_mqtt_event_handle_t event)
{
    if (event == NULL || event->data == NULL || event->data_len < 0 ||
        event->total_data_len < 0 || event->current_data_offset < 0) return;

    const size_t offset = (size_t)event->current_data_offset;
    const size_t len = (size_t)event->data_len;
    const size_t total = (size_t)event->total_data_len;

    if (offset == 0) {
        s_json_accepting = false;
        s_json_received = 0;
        s_json_expected = 0;
        const size_t topic_len = strlen(MQTT_TOPIC_CMD);
        if (event->topic == NULL || event->topic_len != (int)topic_len ||
            memcmp(event->topic, MQTT_TOPIC_CMD, topic_len) != 0) return;
        if (event->retain) {
            // Uma mensagem retida pode causar movimento antigo apos reboot.
            ESP_LOGW(TAG, "Comando retido ignorado por seguranca");
            return;
        }
        if (total == 0 || total > MQTT_MAX_CMD_JSON) {
            ESP_LOGW(TAG, "Comando MQTT excede limite de %d bytes", MQTT_MAX_CMD_JSON);
            return;
        }
        s_json_expected = total;
        s_json_accepting = true;
    }

    if (!s_json_accepting || offset != s_json_received ||
        len > s_json_expected - s_json_received) {
        s_json_accepting = false;
        return;
    }
    memcpy(s_command_json + s_json_received, event->data, len);
    s_json_received += len;
    if (s_json_received == s_json_expected) {
        s_command_json[s_json_expected] = '\0';
        s_json_accepting = false;
        parse_motor_command(s_command_json, s_json_expected);
    }
}

static void mqtt_event_handler(void *args, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    (void)args;
    (void)base;
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        atomic_store(&s_mqtt_connected, true);
        ESP_LOGI(TAG, "MQTT conectado; assinando %s", MQTT_TOPIC_CMD);
        if (esp_mqtt_client_subscribe(event->client, MQTT_TOPIC_CMD, 1) < 0) {
            ESP_LOGE(TAG, "Falha ao solicitar assinatura MQTT");
        }
        break;
    case MQTT_EVENT_DISCONNECTED:
        atomic_store(&s_mqtt_connected, false);
        s_json_accepting = false;
        ESP_LOGW(TAG, "MQTT desconectado");
        break;
    case MQTT_EVENT_DATA:
        process_data_event(event);
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "Erro de transporte MQTT");
        break;
    default:
        break;
    }
}

esp_err_t mqtt_start(void)
{
    if (s_client != NULL) return ESP_OK;
    if (!s_wifi_started) return ESP_ERR_INVALID_STATE;

    if (s_cmd_queue == NULL) {
        s_cmd_queue = xQueueCreate(MQTT_CMD_QUEUE_LENGTH, sizeof(uart_command_t));
        if (s_cmd_queue == NULL) return ESP_ERR_NO_MEM;
    } else {
        (void)xQueueReset(s_cmd_queue);
    }

    const esp_mqtt_client_config_t config = {
        .broker.address.uri = BROKER_URI,
    };
    s_client = esp_mqtt_client_init(&config);
    if (s_client == NULL) return ESP_ERR_NO_MEM;

    esp_err_t err = esp_mqtt_client_register_event(
        s_client, MQTT_EVENT_ANY, mqtt_event_handler, NULL);
    if (err != ESP_OK) goto failure;

    err = esp_mqtt_client_start(s_client);
    if (err != ESP_OK) goto failure;

    ESP_LOGI(TAG, "Cliente MQTT iniciado: %s", BROKER_URI);
    return ESP_OK;

failure:
    (void)esp_mqtt_client_destroy(s_client);
    s_client = NULL;
    return err;
}

bool mqtt_read(uart_command_t *out_cmd)
{
    if (out_cmd == NULL || s_cmd_queue == NULL) return false;
    return xQueueReceive(s_cmd_queue, out_cmd, 0) == pdTRUE;
}

bool mqtt_is_connected(void)
{
    return atomic_load(&s_mqtt_connected);
}

esp_err_t mqtt_publish_telemetry(const uart_telemetry_t *data)
{
    if (data == NULL) return ESP_ERR_INVALID_ARG;
    if (s_client == NULL || !mqtt_is_connected()) return ESP_ERR_INVALID_STATE;
    if (data->encoder_valid &&
        (!isfinite(data->base_angle_deg) || !isfinite(data->base_angle_rad))) {
        return ESP_ERR_INVALID_ARG;
    }

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) return ESP_ERR_NO_MEM;

    const float degrees = data->encoder_valid ? data->base_angle_deg : 0.0f;
    const float radians = data->encoder_valid ? data->base_angle_rad : 0.0f;
    cJSON_AddNumberToObject(root, "base_angle_deg", degrees);
    cJSON_AddNumberToObject(root, "base_angle_rad", radians);
    cJSON_AddNumberToObject(root, "upper_limit_active", data->upper_limit_active ? 1 : 0);
    cJSON_AddNumberToObject(root, "encoder_valid", data->encoder_valid ? 1 : 0);

    char *payload = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (payload == NULL) return ESP_ERR_NO_MEM;

    // Nonblocking: transferencia real ocorre na task interna do ESP-MQTT.
    // QOS 0, retain=0, store=true (enfileira mesmo com QoS 0).
    // Nao enfileirar se desconectado: telemetria antiga nao deve acumular.
    int msg_id = esp_mqtt_client_enqueue(s_client, MQTT_TOPIC_TELEMETRY,
                                          payload, (int)strlen(payload),
                                          0, 0, true);
    free(payload);
    return (msg_id >= 0) ? ESP_OK : ESP_FAIL;
}

void mqtt_stop(void)
{
    atomic_store(&s_mqtt_connected, false);
    if (s_client != NULL) {
        (void)esp_mqtt_client_stop(s_client);
        (void)esp_mqtt_client_destroy(s_client);
        s_client = NULL;
    }
    if (s_cmd_queue != NULL) {
        vQueueDelete(s_cmd_queue);
        s_cmd_queue = NULL;
    }
    s_json_accepting = false;
    s_have_sequence = false;
    ESP_LOGI(TAG, "MQTT finalizado; Wi-Fi permanece ativo");
}