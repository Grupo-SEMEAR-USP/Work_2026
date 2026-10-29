#include "utils.h"
#include <math.h>

/* Definições Iniciais */
communication_mode_t COMM_MODE = UART;

// Sensores
volatile float    G_US_CM[6] = {NAN, NAN, NAN, NAN, NAN, NAN};
volatile uint64_t G_US_TS_MS = 0ULL;