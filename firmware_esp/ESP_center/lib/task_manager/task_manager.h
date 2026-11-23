#ifndef TASK_MANAGER_H
#define TASK_MANAGER_H

#include "esp_err.h"
#include "uart_communication.h"
#include <stdbool.h>

esp_err_t init_tasks();

// Consulta das variaveis compartilhadas para debug
void task_manager_debug_snapshot(
    uart_command_t *cmd,
    bool *ready,
    bool *mov_complete
);

#endif // TASK_MANAGER_H