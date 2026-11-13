#ifndef MAGNETIC_ENCODER_H
#define MAGNETIC_ENCODER_H

#include "esp_err.h"
#include "driver/gpio.h"

typedef enum {
    AS5600_DIR_CLOCKWISE = 0,
    AS5600_DIR_COUNTERCLOCKWISE = 1
} as5600_direction_t;

esp_err_t as5600_init(as5600_direction_t direction);

esp_err_t as5600_update(void);

#endif // MAGNETIC_ENCODER_H
