#pragma once

#include <driver/i2c_master.h>
#include "esp_log.h"

class I2cBus {
public:
    struct Config {
        i2c_port_t port = I2C_NUM_0;
        gpio_num_t sda_io_num = GPIO_NUM_NC;
        gpio_num_t scl_io_num = GPIO_NUM_NC;
        uint32_t clk_speed = 400 * 1000; // 400 kHz por padrão
    };

    explicit I2cBus(const Config &config);
    ~I2cBus();

    esp_err_t init();
    esp_err_t deinit();
    esp_err_t add_device(uint16_t dev_addr, i2c_master_dev_handle_t *dev_handle);
    bool is_initialized() const;

private:
    static constexpr const char *TAG = "I2C_BUS";
    Config config_;
    i2c_master_bus_handle_t bus_handle_ = nullptr;
    bool initialized_ = false;
};