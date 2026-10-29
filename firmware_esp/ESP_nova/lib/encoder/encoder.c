#include "encoder.h"
#include "esp_log.h"
#include "esp_err.h"
#include "utils.h"

/* Limites do PCNT */
#define PCNT_HIGH_LIMIT 10000
#define PCNT_LOW_LIMIT  -10000

/* Macros */
#define ENCODER_A(SIDE) ((ESP_POSITION) == (FRONT) ? \
        ((SIDE) == (ENC_LEFT) ? F_ENCODER_LA : F_ENCODER_RA) : \
        ((SIDE) == (ENC_LEFT) ? R_ENCODER_LA : R_ENCODER_RA)   \
)
#define ENCODER_B(SIDE) ((ESP_POSITION) == (FRONT) ? \
        ((SIDE) == (ENC_LEFT) ? F_ENCODER_LB : F_ENCODER_RB) : \
        ((SIDE) == (ENC_LEFT) ? R_ENCODER_LB : R_ENCODER_RB)   \
)

static const char *TAG = "ENCODER";

pcnt_unit_handle_t init_encoder(encoder_side_t side){
    pcnt_unit_handle_t side_handler = NULL;
    
    // Define o planejamento do gerente da contagem do PCNT
    pcnt_unit_config_t unit_config = {
        .high_limit = PCNT_HIGH_LIMIT,
        .low_limit = PCNT_LOW_LIMIT,
    };
    ESP_ERROR_CHECK(pcnt_new_unit(&unit_config, &side_handler)); // Atribui planejamento ao handle

    // Filtro de ruído
    pcnt_glitch_filter_config_t filter_config = {
        .max_glitch_ns = 1000, // Filtra qualquer pulso menor que 1000 nanosegundos (1us)
    };
    ESP_ERROR_CHECK(pcnt_unit_set_glitch_filter(side_handler, &filter_config));

    // Definindo ambos os canais para implementar uma decodificação de quadratura x4
    // Configuração do canal A
    pcnt_chan_config_t chan_a_config = {
        .edge_gpio_num = ENCODER_A(side), // Pino de borda
        .level_gpio_num = ENCODER_B(side), // Pino de nível (para direção)
    };
    pcnt_channel_handle_t encoder_chan_a = NULL;
    ESP_ERROR_CHECK(pcnt_new_channel(side_handler, &chan_a_config, &encoder_chan_a)); // Cria o Canal A

    // Configuração do canal B
    pcnt_chan_config_t chan_b_config = {
        .edge_gpio_num = ENCODER_B(side), // Pino de borda
        .level_gpio_num = ENCODER_A(side), // Pino de nível (para direção)
    };
    pcnt_channel_handle_t encoder_chan_b = NULL;
    ESP_ERROR_CHECK(pcnt_new_channel(side_handler, &chan_b_config, &encoder_chan_b)); // Cria o Canal B

    // Define a lógica de contagem
    ESP_ERROR_CHECK(pcnt_channel_set_edge_action(encoder_chan_a, PCNT_CHANNEL_EDGE_ACTION_DECREASE, PCNT_CHANNEL_EDGE_ACTION_INCREASE));
    ESP_ERROR_CHECK(pcnt_channel_set_level_action(encoder_chan_a, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE));
    
    ESP_ERROR_CHECK(pcnt_channel_set_edge_action(encoder_chan_b, PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_DECREASE));
    ESP_ERROR_CHECK(pcnt_channel_set_level_action(encoder_chan_b, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE));

    // Inicia o hardware do PCNT
    ESP_ERROR_CHECK(pcnt_unit_enable(side_handler));
    ESP_ERROR_CHECK(pcnt_unit_clear_count(side_handler));
    ESP_ERROR_CHECK(pcnt_unit_start(side_handler));

    return side_handler;
}

// Função para obter a variação de contagem atual (velocidade)
int get_encoder_vel(pcnt_unit_handle_t handler){
    int count = 0; // Definindo variável temporária para armazenar a contagem

    ESP_ERROR_CHECK(pcnt_unit_get_count(handler, &count));
    pcnt_unit_clear_count(handler);
    
    return count;
}

// Função para obter a contagem atual (posição)
int get_encoder_position(pcnt_unit_handle_t handler){
    int count = 0; // Definindo variável temporária para armazenar a contagem

    ESP_ERROR_CHECK(pcnt_unit_get_count(handler, &count));
    
    return count;
}