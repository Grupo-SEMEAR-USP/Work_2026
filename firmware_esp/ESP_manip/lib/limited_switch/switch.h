#ifndef SWITCH_H
#define SWITCH_H

#include "driver/gpio.h"
#include "esp_log.h"
#include "utils.h"


esp_err_t init_switch();
void update_switch_state();

#endif // SWITCH_H