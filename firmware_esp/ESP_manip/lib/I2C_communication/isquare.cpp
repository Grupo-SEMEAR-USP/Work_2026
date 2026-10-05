#include "isquare.hpp"

// Construtor
I2cBus::I2cBus(const Config &config) : config_(config) {
    esp_err_t err = init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Erro crítico ao auto-inicializar o I2C: %s", esp_err_to_name(err));
    }
}

// Destrutor
I2cBus::~I2cBus() {
    deinit();
}

// Inicializa o barramento físico
esp_err_t I2cBus::init() {
    if (initialized_) return ESP_OK;

    i2c_master_bus_config_t bus_config = {
        .i2c_port = config_.port,
        .sda_io_num = config_.sda_io_num,
        .scl_io_num = config_.scl_io_num,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags = { .enable_internal_pullup = true }
    };

    esp_err_t err = i2c_new_master_bus(&bus_config, &bus_handle_);
    if (err == ESP_OK) {
        initialized_ = true;
        ESP_LOGI(TAG, "Barramento I2C iniciado na porta %d", config_.port);
    }
    return err;
}

// Desinicializa o barramento
esp_err_t I2cBus::deinit() {
    if (!initialized_) return ESP_OK;

    esp_err_t err = i2c_del_master_bus(bus_handle_);
    if (err == ESP_OK) {
        initialized_ = false;
        ESP_LOGI(TAG, "Barramento I2C encerrado");
    }
    return err;
}

// Adiciona um dispositivo ao barramento (ex: o AS5600)
esp_err_t I2cBus::add_device(uint16_t dev_addr, i2c_master_dev_handle_t *dev_handle) {
    if (!initialized_) {
        ESP_LOGE(TAG, "Tentou adicionar dispositivo com barramento desligado");
        return ESP_ERR_INVALID_STATE;
    }

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = dev_addr,
        .scl_speed_hz = config_.clk_speed,
    };

    return i2c_master_bus_add_device(bus_handle_, &dev_cfg, dev_handle);
}

// Verifica se está inicializado
bool I2cBus::is_initialized() const {
    return initialized_;
}