#include "terminal_cli.h"
#include "utils.h"
#include "driver/uart.h"
#include "esp_log.h"
#include <string.h>
#include <stdio.h>
#include <stdarg.h>

/* Configurações para estabelecer o CLI via UART */
#define CLI_UART_NUM       UART_NUM_0
#define CLI_BUF_SIZE       256
#define CLI_PROMPT         "\r\nManibot> "

static const char *TAG = "CLI";

/* Helper de Printf para UART */
static void cli_print(const char* fmt, ...) {
    char buf[128];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n > 0) {
        uart_write_bytes(CLI_UART_NUM, buf, n);
    }
}

static void process_command_line(char *line) {
    // Remove espaços iniciais
    char *p = line;
    while (*p == ' ') p++;
    
    if (strlen(p) == 0) return;

    float val1, val2, val3, val4;

    // Comando: HELP
    if (strncmp(p, "help", 4) == 0) {
        cli_print("\r\n--- Ajuda ---"
                  "\r\n status         : Mostra valores globais"
                  "\r\n set <A> <B> <W> <G> : Define Arm, Base, Wrist, Grip"
                  "\r\n arm <val>      : Define Arm (incremento passos)"
                  "\r\n grip <val>     : Define Grip (graus)"
                  "\r\n");
        return;
    }

    // Comando: STATUS
    if (strncmp(p, "status", 6) == 0) {
        cli_print("\r\n[STATUS]"
                  "\r\n Arm: %.2f | Base: %.2f"
                  "\r\n Wrist: %.2f | Grip: %.2f"
                  "\r\n US: [%.1f, %.1f, %.1f]",
                  (double)G_STEPPER_ARM, (double)G_STEPPER_BASE,
                  (double)G_SERVO_WRIST, (double)G_SERVO_GRIPPER,
                  (double)G_US_CM[0], (double)G_US_CM[1], (double)G_US_CM[2]);
        return;
    }

    // Comando: SET ALL
    if (sscanf(p, "set %f %f %f %f", &val1, &val2, &val3, &val4) == 4) {
        G_STEPPER_ARM  += val1; // Steppers sao relativos/incrementais na logica simples
        G_STEPPER_BASE += val2;
        G_SERVO_WRIST   = val3;
        G_SERVO_GRIPPER = val4;
        cli_print("\r\nOK: Set All");
        return;
    }

    // Comandos Individuais (Exemplos)
    if (sscanf(p, "arm %f", &val1) == 1) {
        G_STEPPER_ARM += val1;
        cli_print("\r\nOK: Arm += %.2f", val1);
        return;
    }
    
    if (sscanf(p, "grip %f", &val1) == 1) {
        G_SERVO_GRIPPER = val1;
        cli_print("\r\nOK: Grip = %.2f", val1);
        return;
    }

    cli_print("\r\nComando desconhecido: %s", p);
}

static void cli_task_loop(void *pv) {
    char line[CLI_BUF_SIZE];
    int pos = 0;

    cli_print(CLI_PROMPT);

    while (1) {
        uint8_t c;
        int len = uart_read_bytes(CLI_UART_NUM, &c, 1, pdMS_TO_TICKS(50));
        
        if (len > 0) {
            // Echo
            uart_write_bytes(CLI_UART_NUM, &c, 1);

            if (c == '\r' || c == '\n') {
                line[pos] = 0;
                process_command_line(line);
                pos = 0;
                cli_print(CLI_PROMPT);
            } else if (c == 0x08 || c == 0x7F) { // Backspace
                if (pos > 0) pos--;
            } else {
                if (pos < CLI_BUF_SIZE - 1) line[pos++] = (char)c;
            }
        }
    }
}

void start_cli_task(void) {
    xTaskCreate(cli_task_loop, "cli_task", 4096, NULL, 5, NULL);
}