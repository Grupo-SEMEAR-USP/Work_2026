#include "utils.h"

/* Definições Iniciais */

communication_mode_t COMM_MODE = UART;

// Steppers (Passos ou mm)
volatile float G_STEPPER_BASE = 0.0f;
volatile float G_STEPPER_ARM  = 0.0f;

// Servos (Graus)
volatile float G_SERVO_WRIST   = 0.0f;  
volatile float G_SERVO_GRIPPER = 0.0f;  

// Sensores
volatile float    G_US_CM[3] = {NAN, NAN, NAN};
volatile uint64_t G_US_TS_MS = 0ULL;