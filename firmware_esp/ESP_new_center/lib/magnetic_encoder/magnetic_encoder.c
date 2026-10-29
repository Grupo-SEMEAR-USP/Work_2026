
#include "magnetic_encoder.h"
#include "utils.h"

#include <stdint.h>
#include <stdbool.h>

#include "driver/i2c_master.h"
#include "esp_log.h"

#define AS5600_I2C_ADDRESS     0x36
#define AS5600_ANGLE_REGISTER  0x0E
#define AS5600_I2C_FREQ_HZ     100000
#define AS5600_TIMEOUT_MS      50

static const char *TAG = "AS5600";

static i2c_master_bus_handle_t s_i2c_bus = NULL;
static i2c_master_dev_handle_t s_as5600 = NULL;

esp_err_t as5600_init(as5600_direction_t direction)
{
    gpio_config_t dir_cfg = {
        .pin_bit_mask = (1ULL << C_ENCMAG_DIR),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    esp_err_t err = gpio_config(&dir_cfg);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Erro configurando DIR");
        return err;
    }

    // Define o sentido de leitura do AS5600
    err = gpio_set_level(C_ENCMAG_DIR, (uint32_t)direction);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Erro definindo DIR");
        return err;
    }

    if (s_as5600 != NULL) {
        return ESP_OK;
    }

    i2c_master_bus_config_t bus_cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = C_ENCMAG_SDA,
        .scl_io_num = C_ENCMAG_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };

    err = i2c_new_master_bus(&bus_cfg, &s_i2c_bus);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Falha ao configurar I2C: %s",
                 esp_err_to_name(err));
        return err;
    }

    err = i2c_master_probe(
        s_i2c_bus,
        AS5600_I2C_ADDRESS,
        AS5600_TIMEOUT_MS
    );

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "AS5600 nao encontrado: %s",
                 esp_err_to_name(err));

        i2c_del_master_bus(s_i2c_bus);
        s_i2c_bus = NULL;
        return err;
    }

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = AS5600_I2C_ADDRESS,
        .scl_speed_hz = AS5600_I2C_FREQ_HZ,
    };

    err = i2c_master_bus_add_device(
        s_i2c_bus,
        &dev_cfg,
        &s_as5600
    );

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Falha ao adicionar AS5600: %s",
                 esp_err_to_name(err));

        i2c_del_master_bus(s_i2c_bus);
        s_i2c_bus = NULL;
        return err;
    }

    ESP_LOGI(TAG, "AS5600 inicializado");
    return ESP_OK;
}

esp_err_t as5600_update(void)
{
    if (s_as5600 == NULL) {
        return ESP_ERR_INVALID_STATE;
    }

    const uint8_t reg = AS5600_ANGLE_REGISTER;
    uint8_t bytes[2] = {0};

    esp_err_t err = i2c_master_transmit_receive(
        s_as5600,
        &reg,
        sizeof(reg),
        bytes,
        sizeof(bytes),
        AS5600_TIMEOUT_MS
    );

    if (err != ESP_OK) {
        return err;
    }

    uint16_t raw_angle =
        ((uint16_t)(bytes[0] & 0x0F) << 8) | bytes[1];

    G_ENCMAG_ANGLE_DEG =
        (float)raw_angle * (360.0f / 4096.0f);

    G_ENCMAG_ANGLE_RAD =
        (float)raw_angle * (6.28318530718f / 4096.0f);

    return ESP_OK;
}
