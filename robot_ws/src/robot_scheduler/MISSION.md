# Missão de duas mesas

A missão coleta três AprilTags, guarda um bloco em cada depósito interno e entrega os
blocos por cor. O scheduler usa o ID apenas na mesa de coleta. Na entrega, cada cor
seleciona o contêiner, e o número do depósito seleciona o bloco.

## Preparação e execução

Em ROS Noetic, faça um build limpo do workspace com catkin. Use artefatos de build
locais atualizados. O protocolo UART da ESP_center inclui o UID de 64 bits no fim
dos payloads, que agora têm 25 bytes no comando e 19 na telemetria. Atualize a ESP_center
e a ponte ROS em conjunto. A ESP_right atualizada zera as referências se a UART
ficar 300 ms sem comando válido. A ESP_left usa o mesmo formato binário anterior.

Após calibrar os parâmetros, marque `calibrated: true` em `config/mission.yaml` e rode:

```bash
source devel/setup.bash
roslaunch robot_utils mission.launch
```

`general.launch` sobe os mesmos componentes sem disparar a missão. Com mensagens
simuladas e executores de teste, `scheduler.launch allow_uncalibrated:=true` permite
testar somente o sequenciamento. Não use esse override no robô em campo.

## Calibração

- `mission.yaml` associa provisoriamente 4, 5 e 6 a vermelho, azul e verde, com
  WS1 para blocos e WS2 para contêineres. O mapa já inclui esses waypoints. Confira
  a posição inicial Start, alturas de mesa, IDs, cores e borda de referência.
- Depósitos 1, 2 e 3 usam, respectivamente, deposit_left, deposit_middle e deposit_right.
- Em `robot_manipulation/config/manipulation.yaml`, meça as descidas a partir do
  fim de curso superior, o curso seguro, os ângulos, o tempo de assentamento dos
  servos e a altura de entrega. Servo sem encoder confirma aceitação do PWM e
  aguarda assentamento. A presença física do bloco não é medida.
- Em `robot_movement/config/mission_movement.yaml`, confirme a largura da mesa, a
  diferença entre retornos dos ultrassons e o ponto da garra. O contêiner usa o
  centro em frações da imagem. Calibre os sinais de correção e os setpoints.
- Em `robot_utils/config/container_vision.yaml`, ajuste HSV, ROI e área no campo.
  A Logitech deve publicar Image e CameraInfo calibrado para o detector de AprilTags.

## Interfaces

- `/container_detections` usa `ContainerDetectionArray`, com Header de origem, tamanho
  da imagem e lista de centros em pixels, cor e área em pixels quadrados.
- A ação `/move_segment` usa `MoveSegment.action` e só confirma parada com telemetria
  recente das quatro rodas. `target=move` continua disponível para comandos manuais.
- `/manipulator_command` usa `ManipulatorCommand`. `/manipulator_state` usa
  `manipulation_comm` com UID e estado do firmware.
- `/scheduler/cancel` usa `SchedulerCommand` com o UID do passo ativo. O scheduler
  só progride em `OK` e mantém a ocupação dos depósitos em `/scheduler/deposits`
  na ordem 1, 2 e 3. A ocupação é mantida durante a execução do processo.
- A busca reposiciona na mesma borda antes de cada alvo. Perda de leituras,
  expiração ou limite encerram o deslocamento. A entrega só começa depois que
  a busca e o alinhamento confirmam a parada.
