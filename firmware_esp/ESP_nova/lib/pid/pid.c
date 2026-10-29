#include "pid.h"
#include "encoder.h"
#include "h_bridge.h"
#include "utils.h"
#include "esp_log.h"

/* Limites de Controle */
// Para a ação de controle (PWM)
#define Max_Output LEDC_MAX_DUTY
#define Min_Output -LEDC_MAX_DUTY
// Para evitar wind-up do integrador
#define Max_integral 1000
#define Min_integral -1000

/* Parâmetros do controlador */
// Motor Esquerdo
#define KP_L 150.0f 
#define KI_L 0.0f   
#define KD_L 0.0f
#define TICKS_TO_RADS_LEFT (PI*2*(1000/CNTRL_PERIOD_MS))/8120

// Motor Direito
#define KP_R 150.0f    
#define KI_R 0.0f     
#define KD_R 0.0f 
#define TICKS_TO_RADS_RIGHT (PI*2*(1000/CNTRL_PERIOD_MS))/8120

/* Macros */
#define PID_SIDE_KP(SIDE) ((SIDE) == PID_LEFT ? KP_L : KP_R)
#define PID_SIDE_KI(SIDE) ((SIDE) == PID_LEFT ? KI_L : KI_R)
#define PID_SIDE_KD(SIDE) ((SIDE) == PID_LEFT ? KD_L : KD_R)
#define PID_TICKS_TO_RADS(SIDE) ((SIDE) == PID_LEFT ? TICKS_TO_RADS_LEFT : TICKS_TO_RADS_RIGHT)

static const char *TAG = "PID";

static void PWM_limit(float *PWM) {
  *PWM = (*PWM > Max_Output) ? Max_Output : *PWM;
  *PWM = (*PWM < Min_Output) ? Min_Output : *PWM;
}

pid_ctrl_block_handle_t init_pid(pid_side_t side) {

  pid_ctrl_config_t config_pid; 
  pid_ctrl_block_handle_t pid_block; 

  pid_ctrl_parameter_t values_pid = {
    .kd = PID_SIDE_KD(side),
    .kp = PID_SIDE_KP(side),
    .ki = PID_SIDE_KI(side),
    .min_integral = Min_integral,
    .max_integral = Max_integral,
    .min_output = Min_Output,
    .max_output = Max_Output,
    .cal_type = PID_CAL_TYPE_INCREMENTAL,
  };

  config_pid.init_param = values_pid;

  ESP_ERROR_CHECK(pid_new_control_block(&config_pid, &pid_block));
  ESP_ERROR_CHECK(pid_update_parameters(pid_block, &values_pid));

  return pid_block;
}

esp_err_t pid_calculate(pid_ctrl_block_handle_t pid_l, pid_ctrl_block_handle_t pid_r, pcnt_unit_handle_t encoder_l, pcnt_unit_handle_t encoder_r) {
  float value_pid_L = 0;
  float value_pid_R = 0;

  G_ENC_L = get_encoder_vel(encoder_l);
  G_ENC_R = get_encoder_vel(encoder_r);

  G_RADS_L = G_ENC_L * PID_TICKS_TO_RADS(PID_LEFT);
  G_RADS_R = G_ENC_R * PID_TICKS_TO_RADS(PID_RIGHT);

  if(G_TARGET_L == 0 && G_TARGET_R == 0 && BREAK_FLAG) {
    G_PWM_L = 0;
    G_PWM_R = 0;
  } else {
    float error_L = (G_TARGET_L - G_RADS_L);
    float error_R = (G_TARGET_R - G_RADS_R);

    pid_compute(pid_l, error_L, &value_pid_L);
    pid_compute(pid_r, error_R, &value_pid_R);
    
    G_PWM_L += value_pid_L;
    G_PWM_R += value_pid_R;

    PWM_limit(&G_PWM_L);
    PWM_limit(&G_PWM_R);
  }

  // ESP_LOGI(TAG, "Target:%.2f | Atual:%.2f | Erro:%.2f | PWM:%.0f", 
  //   G_TARGET_L, G_RADS_L, (G_TARGET_L - G_RADS_L), G_PWM_L);
  // ESP_LOGI(TAG, "Target:%.2f | Atual:%.2f | Erro:%.2f | PWM:%.0f",
  //   G_TARGET_R, G_RADS_R, (G_TARGET_R - G_RADS_R), G_PWM_R);

  return ESP_OK;
}