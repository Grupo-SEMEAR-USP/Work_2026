#include <chrono>
#include <sdkconfig.h>
#include <atomic>
#include <thread>
#include <cstdio>

#include "isquare.hpp" // O seu novo cabeçalho do barramento I2C
#include "magnetic_encoder.hpp"
#include "task.hpp"

using namespace std::chrono_literals;

extern "C" void app_main(void) {
    // Declaração da variável de controle do loop
    std::atomic<bool> quit_test = false;
    printf("Starting as5600 example, rotate to -720 degrees to quit!\n");

    // 1. Inicializa o seu barramento customizado (isquare)
    I2cBus i2c_bus({
        .port = I2C_NUM_0,
        .sda_io_num = (gpio_num_t)AS5600_I2C_SDA_PIN,
        .scl_io_num = (gpio_num_t)AS5600_I2C_SCL_PIN,
    });

    // 2. Adiciona o dispositivo AS5600 e guarda o handle nativo do ESP-IDF
    i2c_master_dev_handle_t as5600_handle;
    esp_err_t err = i2c_bus.add_device(espp::As5600::DEFAULT_ADDRESS, &as5600_handle);
    if (err != ESP_OK) {
        printf("Falha ao adicionar o AS5600 ao barramento!\n");
        return;
    }

    // Período de atualização do encoder (10 ms)
    constexpr float encoder_update_period = 0.01f;

    // 3. Instancia o As5600 adaptando a comunicação para usar o seu I2cBus
    espp::As5600 as5600({
        .write_then_read = [as5600_handle](const uint8_t *wdata, size_t wlen, uint8_t *rdata, size_t rlen) -> bool {
            return i2c_master_transmit_receive(as5600_handle, wdata, wlen, rdata, rlen, pdMS_TO_TICKS(10)) == ESP_OK;
        },
        .update_period = std::chrono::duration<float>(encoder_update_period),
    });

    // 4. Função executada periodicamente pela task em segundo plano
    auto task_fn = [&quit_test, &as5600](std::mutex &m, std::condition_variable &cv) {
      static auto start = std::chrono::high_resolution_clock::now();
      auto now = std::chrono::high_resolution_clock::now();
      auto seconds = std::chrono::duration<float>(now - start).count();
      
      auto count = as5600.get_count();
      auto radians = as5600.get_radians();
      auto degrees = as5600.get_degrees();
      auto rpm = as5600.get_rpm();

      // Imprime os dados formatados usando o printf clássico
      printf("%.3f, %d, %.3f, %.3f, %.3f\n", seconds, count, radians, degrees, rpm);

      quit_test = degrees <= -720.0f;
      
      {
        std::unique_lock<std::mutex> lk(m);
        cv.wait_for(lk, 50ms);
      }
      return false;
    };

    // 5. Cria e inicia a Task
    auto task = espp::Task({
        .callback = task_fn,
        .task_config = {
            .name = "As5600 Task",
            .stack_size_bytes = 5 * 1024,
        }
    });

    printf("time(s), count, radians, degrees, rpm\n");
    task.start();

    // Loop principal à espera que a condição de saída seja atingida
    while (!quit_test) {
      std::this_thread::sleep_for(100ms);
    }

    // Loop de segurança final para travar o programa
    while (true) {
      std::this_thread::sleep_for(1s);
    }
}