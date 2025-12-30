#ifndef PID_H
#define PID_H

/* Importe de bibliotecas */
#include "pid_ctrl.h"
#include "esp_err.h"
#include "driver/pulse_cnt.h"

/* Identificador de lado */
typedef enum {
    PID_RIGHT,
    PID_LEFT
} pid_side_t;

/* Protótipos das Funções */
pid_ctrl_block_handle_t init_pid(pid_side_t side);
esp_err_t pid_calculate(pid_ctrl_block_handle_t pid_l, pid_ctrl_block_handle_t pid_r, pcnt_unit_handle_t encoder_l, pcnt_unit_handle_t encoder_r);

#endif // PID_H