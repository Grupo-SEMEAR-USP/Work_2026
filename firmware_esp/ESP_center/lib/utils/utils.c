
#include "utils.h"

/*=== Definicoes Iniciais ===*/

// Modo de comunicacao
communication_mode_t COMM_MODE = UART;

// Sensor magnetico AS5600
volatile float G_ENCMAG_ANGLE_DEG = 0.0f;
volatile float G_ENCMAG_ANGLE_RAD = 0.0f;
bool G_FCS_UP = false;

uart_command_t G_MOTOR_CMD;
bool G_MOTOR_CMD_READY = false;