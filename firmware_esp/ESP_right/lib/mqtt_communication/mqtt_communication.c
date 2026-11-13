
#include "mqtt_communication.h"
#include "utils.h"

#include <stdio.h>
#include <string.h>
#include <math.h>

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_idf_version.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"

#include "mqtt_client.h"
#include "cJSON.h"

/* === Configurações Wi-Fi === */
#define INTERNAL_WIFI_SSID   "atenaopen2023"
#define INTERNAL_WIFI_PASS   "rrrmmmaaa"

/* === MQTT === */
#define INTERNAL_BROKER_URI  "mqtt://192.168.1.100"

#define TOPIC_CMD_VELOCITY   "command/velocity"
#define TOPIC_ENCODERS       "state/encoders"

/* === Segurança e comunicação === */
#define MQTT_CMD_TIMEOUT_MS  300
#define MQTT_MAX_PAYLOAD     256

#define WIFI_CONNECTED_BIT   BIT0
#define MQTT_CONNECTED_BIT   BIT0

static const char *TAG = "MQTT";

/* === Estado interno === */
static esp_mqtt_client_handle_t s_mqtt_client = NULL;

static SemaphoreHandle_t s_data_mutex = NULL;

static EventGroupHandle_t s_wifi_events = NULL;
static EventGroupHandle_t s_mqtt_events = NULL;

static TickType_t s_last_command_tick = 0;
static bool s_command_received = false;

/* ============================================
   Funções auxiliares
   ============================================ */

/* Zera os setpoints e invalida o último comando.
   O controle PID aplica PWM zero no próximo ciclo. */
static void mqtt_reset_commands(void) {

    if (s_data_mutex == NULL) {
        return;
    }

    if (xSemaphoreTake(s_data_mutex,
                       pdMS_TO_TICKS(10)) == pdTRUE) {

        G_TARGET_L_F = 0.0f;
        G_TARGET_R_F = 0.0f;
        G_TARGET_L_R = 0.0f;
        G_TARGET_R_R = 0.0f;

        s_command_received = false;

        xSemaphoreGive(s_data_mutex);
    }
}

/* Verifica se o MQTT está conectado */
static bool mqtt_is_connected(void) {

    if (s_mqtt_events == NULL) {
        return false;
    }

    EventBits_t bits = xEventGroupGetBits(s_mqtt_events);

    return (bits & MQTT_CONNECTED_BIT) != 0;
}

/* ============================================
   Gerenciamento Wi-Fi
   ============================================ */

static void wifi_event_handler(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data
) {
    (void)arg;
    (void)event_data;

    if (event_base == WIFI_EVENT) {

        if (event_id == WIFI_EVENT_STA_START) {
            esp_wifi_connect();
        }

        else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {

            xEventGroupClearBits(
                s_wifi_events,
                WIFI_CONNECTED_BIT
            );

            mqtt_reset_commands();

            ESP_LOGW(TAG,
                     "Wi-Fi desconectado. Reconectando...");

            esp_err_t ret = esp_wifi_connect();

            if (ret != ESP_OK) {
                ESP_LOGW(TAG,
                         "Falha ao solicitar reconexao Wi-Fi");
            }
        }
    }

    else if (event_base == IP_EVENT &&
             event_id == IP_EVENT_STA_GOT_IP) {

        xEventGroupSetBits(
            s_wifi_events,
            WIFI_CONNECTED_BIT
        );

        ESP_LOGI(TAG, "Wi-Fi conectado e IP obtido");
    }
}

esp_err_t init_wifi(void) {

    if (s_wifi_events != NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    s_wifi_events = xEventGroupCreate();

    if (s_wifi_events == NULL) {
        return ESP_ERR_NO_MEM;
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    if (esp_netif_create_default_wifi_sta() == NULL) {
        return ESP_FAIL;
    }

    wifi_init_config_t wifi_init_config =
        WIFI_INIT_CONFIG_DEFAULT();

    ESP_ERROR_CHECK(
        esp_wifi_init(&wifi_init_config)
    );

    ESP_ERROR_CHECK(
        esp_event_handler_register(
            WIFI_EVENT,
            ESP_EVENT_ANY_ID,
            &wifi_event_handler,
            NULL
        )
    );

    ESP_ERROR_CHECK(
        esp_event_handler_register(
            IP_EVENT,
            IP_EVENT_STA_GOT_IP,
            &wifi_event_handler,
            NULL
        )
    );

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = INTERNAL_WIFI_SSID,
            .password = INTERNAL_WIFI_PASS,
        }
    };

    ESP_ERROR_CHECK(
        esp_wifi_set_mode(WIFI_MODE_STA)
    );

    ESP_ERROR_CHECK(
        esp_wifi_set_config(
            WIFI_IF_STA,
            &wifi_config
        )
    );

    /* Reduz latência de comunicação */
    ESP_ERROR_CHECK(
        esp_wifi_set_ps(WIFI_PS_NONE)
    );

    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Aguardando conexao Wi-Fi...");

    /* Espera o primeiro IP.
       O handler continua tentando reconectar. */
    xEventGroupWaitBits(
        s_wifi_events,
        WIFI_CONNECTED_BIT,
        pdFALSE,
        pdFALSE,
        portMAX_DELAY
    );

    return ESP_OK;
}

/* ============================================
   Recepção de comandos MQTT
   ============================================ */

static void mqtt_process_command(
    esp_mqtt_event_handle_t event
) {

    /* Confirma o tópico recebido */
    const size_t topic_size =
        sizeof(TOPIC_CMD_VELOCITY) - 1;

    if (event->topic == NULL ||
        event->topic_len != (int)topic_size ||
        memcmp(
            event->topic,
            TOPIC_CMD_VELOCITY,
            topic_size
        ) != 0) {
        return;
    }

    /* Não executa comandos antigos retidos
       pelo broker após uma reconexão. */
    if (event->retain) {
        return;
    }

    /* Rejeita mensagens fragmentadas ou grandes */
    if (event->data == NULL ||
        event->current_data_offset != 0 ||
        event->data_len != event->total_data_len ||
        event->data_len <= 0 ||
        event->data_len >= MQTT_MAX_PAYLOAD) {

        ESP_LOGW(TAG, "Payload MQTT invalido");
        return;
    }

    char buffer[MQTT_MAX_PAYLOAD];

    memcpy(
        buffer,
        event->data,
        event->data_len
    );

    buffer[event->data_len] = '\0';

    cJSON *root = cJSON_Parse(buffer);

    if (root == NULL || !cJSON_IsObject(root)) {
        cJSON_Delete(root);
        ESP_LOGW(TAG, "JSON MQTT invalido");
        return;
    }

    const cJSON *lf = cJSON_GetObjectItemCaseSensitive(
        root, "left_front"
    );

    const cJSON *rf = cJSON_GetObjectItemCaseSensitive(
        root, "right_front"
    );

    const cJSON *lr = cJSON_GetObjectItemCaseSensitive(
        root, "left_rear"
    );

    const cJSON *rr = cJSON_GetObjectItemCaseSensitive(
        root, "right_rear"
    );

    /* Todos os quatro campos são obrigatórios */
    bool valid =
        cJSON_IsNumber(lf) &&
        cJSON_IsNumber(rf) &&
        cJSON_IsNumber(lr) &&
        cJSON_IsNumber(rr);

    if (valid) {

        float target_lf = (float)lf->valuedouble;
        float target_rf = (float)rf->valuedouble;
        float target_lr = (float)lr->valuedouble;
        float target_rr = (float)rr->valuedouble;

        valid =
            isfinite(target_lf) &&
            isfinite(target_rf) &&
            isfinite(target_lr) &&
            isfinite(target_rr);

        if (valid && s_data_mutex != NULL) {

            if (xSemaphoreTake(
                    s_data_mutex,
                    pdMS_TO_TICKS(10)
                ) == pdTRUE) {

                G_TARGET_L_F = target_lf;
                G_TARGET_R_F = target_rf;
                G_TARGET_L_R = target_lr;
                G_TARGET_R_R = target_rr;

                s_last_command_tick = xTaskGetTickCount();
                s_command_received = true;

                xSemaphoreGive(s_data_mutex);
            }
        }
    }

    if (!valid) {
        ESP_LOGW(TAG,
                 "Comando MQTT com valores invalidos");
    }

    cJSON_Delete(root);
}

/* ============================================
   Eventos MQTT
   ============================================ */

static void mqtt_event_handler(
    void *handler_args,
    esp_event_base_t base,
    int32_t event_id,
    void *event_data
) {
    (void)handler_args;
    (void)base;

    esp_mqtt_event_handle_t event =
        (esp_mqtt_event_handle_t)event_data;

    switch ((esp_mqtt_event_id_t)event_id) {

        case MQTT_EVENT_CONNECTED:

            /* Uma nova sessão requer novos comandos */
            mqtt_reset_commands();

            xEventGroupSetBits(
                s_mqtt_events,
                MQTT_CONNECTED_BIT
            );

            ESP_LOGI(TAG, "Conectado ao broker MQTT");

            if (esp_mqtt_client_subscribe(
                    event->client,
                    TOPIC_CMD_VELOCITY,
                    0
                ) < 0) {

                ESP_LOGE(TAG,
                         "Falha ao assinar topico de comandos");
            }

            break;

        case MQTT_EVENT_DISCONNECTED:

            xEventGroupClearBits(
                s_mqtt_events,
                MQTT_CONNECTED_BIT
            );

            mqtt_reset_commands();

            ESP_LOGW(TAG,
                     "Broker desconectado");

            break;

        case MQTT_EVENT_DATA:

            mqtt_process_command(event);
            break;

        case MQTT_EVENT_ERROR:

            ESP_LOGW(TAG,
                     "Erro na comunicacao MQTT");
            break;

        default:
            break;
    }
}

/* ============================================
   Inicialização MQTT
   ============================================ */

esp_err_t mqtt_start(SemaphoreHandle_t data_mutex) {

    if (data_mutex == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (s_mqtt_client != NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    s_data_mutex = data_mutex;

    s_mqtt_events = xEventGroupCreate();

    if (s_mqtt_events == NULL) {
        return ESP_ERR_NO_MEM;
    }

    esp_mqtt_client_config_t mqtt_config = {
#if ESP_IDF_VERSION_MAJOR >= 5
        .broker.address.uri = INTERNAL_BROKER_URI,
#else
        .uri = INTERNAL_BROKER_URI,
#endif
    };

    s_mqtt_client = esp_mqtt_client_init(&mqtt_config);

    if (s_mqtt_client == NULL) {
        vEventGroupDelete(s_mqtt_events);
        s_mqtt_events = NULL;
        return ESP_FAIL;
    }

    esp_err_t ret = esp_mqtt_client_register_event(
        s_mqtt_client,
        MQTT_EVENT_ANY,
        mqtt_event_handler,
        NULL
    );

    if (ret != ESP_OK) {
        esp_mqtt_client_destroy(s_mqtt_client);
        s_mqtt_client = NULL;

        vEventGroupDelete(s_mqtt_events);
        s_mqtt_events = NULL;

        return ret;
    }

    return esp_mqtt_client_start(s_mqtt_client);
}

/* ============================================
   Publicação dos encoders
   ============================================ */

void mqtt_publish_encoders(void) {

    if (s_mqtt_client == NULL ||
        !mqtt_is_connected()) {
        return;
    }

    if (s_data_mutex == NULL) {
        return;
    }

    float lf, rf, lr, rr;
    int ticks_lf, ticks_rf, ticks_lr, ticks_rr;

    /* Apenas copia os valores sob proteção */
    if (xSemaphoreTake(
            s_data_mutex,
            pdMS_TO_TICKS(5)
        ) != pdTRUE) {
        return;
    }

    lf = G_RADS_L_F;
    rf = G_RADS_R_F;
    lr = G_RADS_L_R;
    rr = G_RADS_R_R;

    ticks_lf = G_ENC_L_F;
    ticks_rf = G_ENC_R_F;
    ticks_lr = G_ENC_L_R;
    ticks_rr = G_ENC_R_R;

    xSemaphoreGive(s_data_mutex);

    char payload[256];

    int len = snprintf(
        payload,
        sizeof(payload),
        "{"
          "\"left_front\":%.4f,"
          "\"right_front\":%.4f,"
          "\"left_rear\":%.4f,"
          "\"right_rear\":%.4f,"
          "\"ticks\":{"
            "\"left_front\":%d,"
            "\"right_front\":%d,"
            "\"left_rear\":%d,"
            "\"right_rear\":%d"
          "}"
        "}",
        lf, rf, lr, rr,
        ticks_lf, ticks_rf, ticks_lr, ticks_rr
    );

    if (len < 0 || len >= (int)sizeof(payload)) {
        ESP_LOGW(TAG, "Payload de feedback muito grande");
        return;
    }

    /* Publicação não bloqueante, QoS 0.
       Não acumula telemetria antiga offline. */
    int msg_id = esp_mqtt_client_enqueue(
        s_mqtt_client,
        TOPIC_ENCODERS,
        payload,
        len,
        0,
        0,
        false
    );

    if (msg_id < 0) {
        ESP_LOGW(TAG,
                 "Falha ao enfileirar feedback MQTT");
    }
}

/* ============================================
   Watchdog de comunicação
   ============================================ */

void mqtt_check_timeout(void) {

    if (s_data_mutex == NULL) {
        return;
    }

    bool connected = mqtt_is_connected();
    TickType_t now = xTaskGetTickCount();

    if (xSemaphoreTake(
            s_data_mutex,
            pdMS_TO_TICKS(5)
        ) != pdTRUE) {
        return;
    }

    bool expired =
        !s_command_received ||
        ((now - s_last_command_tick) >=
         pdMS_TO_TICKS(MQTT_CMD_TIMEOUT_MS));

    if (!connected || expired) {

        G_TARGET_L_F = 0.0f;
        G_TARGET_R_F = 0.0f;
        G_TARGET_L_R = 0.0f;
        G_TARGET_R_R = 0.0f;

        s_command_received = false;
    }

    xSemaphoreGive(s_data_mutex);
}

/* ============================================
   Encerramento MQTT
   ============================================ */

void mqtt_stop(void) {

    mqtt_reset_commands();

    if (s_mqtt_client != NULL) {

        esp_mqtt_client_stop(s_mqtt_client);
        esp_mqtt_client_destroy(s_mqtt_client);

        s_mqtt_client = NULL;
    }

    if (s_mqtt_events != NULL) {

        vEventGroupDelete(s_mqtt_events);
        s_mqtt_events = NULL;
    }

    s_data_mutex = NULL;
}
