#ifndef MOTORS_H
#define MOTORS_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "magnetic_encoder.h"
#include "pid_ctrl.h"

typedef enum {
    MOTOR_ELEVATOR = 0, // Deslocamento RELATIVO em centimetros
    MOTOR_BASE,         // Posicao ABSOLUTA em graus [0, 360]
    MOTOR_WRIST,        // Servo: angulo em graus [0, 180]
    MOTOR_GRIPPER       // Servo: angulo em graus [0, 180]
} motor_id_t;

typedef struct {
    // Calibracao do fuso
    float elevator_lead_mm_per_rev;
    uint16_t elevator_full_steps_per_rev; // normalmente 200 (1,8 graus)
    uint8_t elevator_microsteps;          // DRV8825 M0=1 M1=0 M2=0 -> 2
    bool elevator_dir_high_is_up;        // sentido real de subida do fuso

    // Transmissao da base: voltas do MOTOR para 1 volta da BASE.
    uint16_t base_full_steps_per_rev;
    uint8_t base_microsteps;
    float base_motor_turns_per_base_turn;
    bool base_dir_high_increases_angle; // conferir com o AS5600 instalado

    as5600_direction_t encoder_direction;
    float base_tolerance_deg;           // tolerancia angular

    // PID posicional. Entrada = erro em passos equivalentes da base
    pid_ctrl_parameter_t base_pid;
} motors_config_t;

typedef struct {
    bool elevator_upper_limit;          // GPIO C_FIM_CS = HIGH
    bool elevator_busy;
    float elevator_estimated_cm;        // relativo ao boot. Não é absoluto
    esp_err_t elevator_error;           // falha de transmissao de passos

    bool base_target_active;
    bool base_on_target;
    float base_target_deg;
    float base_measured_deg;
    esp_err_t base_sensor_error;
    esp_err_t base_stepper_error;
} motors_status_t;

// Inicializa steppers, encoder, servos e a task privada de supervisao.
esp_err_t motors_init(const motors_config_t *config);

// Não bloqueante. Uma chamada = um novo comando
esp_err_t motors_apply(motor_id_t motor, float value);

// Lê uma fotografia do estado dos movimentos e sensores.
esp_err_t motors_get_status(motors_status_t *status);

// Cancela apenas o deslocamento ainda não enviado ao DRV8825.
esp_err_t motors_cancel_elevator(void);

#endif // MOTORS_H
