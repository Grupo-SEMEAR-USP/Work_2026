# Sistema de Movimentação e Odometria

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![C++](https://img.shields.io/badge/C++-11-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![Kinematics](https://img.shields.io/badge/Omnidirecional-Mecanum-%23FF6F00.svg?style=for-the-badge&logo=geometry&logoColor=white)

Este pacote (`robot_movement`) é o responsável por traduzir comandos de velocidade em movimento físico e estimar a posição do robô no espaço. Ele implementa a **cinemática omnidirecional** (permitindo movimentos laterais), funde dados de **encoders e IMU** para uma odometria precisa e fornece scripts de **alinhamento fino** baseados em sensores.

A arquitetura híbrida (C++ para odometria/controle e Python para comportamentos de alto nível) garante performance na malha de controle e flexibilidade nas estratégias de alinhamento.

---

## Sumário

1. [Estrutura do Pacote](#estrutura)
2. [Interface de Hardware (C++)](#hw)
3. [Scripts de Comportamento e Alinhamento](#scripts)
4. [Calibração e Testes](#calibracao)
5. [Instalação e Uso](#uso)

---

## <a id="estrutura"></a>1. Estrutura do Pacote

```text
robot_movement/
├── CMakeLists.txt               # Configuração de compilação
├── package.xml                  # Dependências
├── config/                     
│   └── wheel_specification.yaml # Parâmetros físicos do robô (raio, separação)
├── include/                    
│   └── hw_interface.hpp         # Header da classe de cinemática
├── src/                        
│   └── hw_interface.cpp         # Implementação da Odometria e Cinemática
├── launch/                     
│   ├── movement.launch          # Inicia a interface de hardware (Base)
│   └── scheduler_mov.launch     # Inicia os nós de alinhamento para o Scheduler
└── scripts/                    
    ├── align_block.py           # Alinhamento visual com AprilTag
    ├── align_table.py           # Alinhamento paralelo com ultrassom
    ├── border_detect.py         # Detecção de bordas de mesa
    ├── move_time.py             # Movimentos simples por temporizador
    ├── imu_stable.py            # Filtro de estabilidade para IMU
    ├── teste_linear.py          # Calibração de translação
    └── teste_angular.py         # Calibração de rotação
```

---

## <a id="hw"></a>2. Interface de Hardware (`hw_interface_node`)

Este nó C++ (`src/hw_interface.cpp`) é o coração da locomoção. Ele atua como uma ponte bidirecional entre o ROS e o Microcontrolador (via tópicos de comunicação):

### Entrada: Comandos (`/cmd_vel`)
Recebe velocidades lineares (X, Y) e angulares (Z) e aplica a **Cinemática Inversa Omnidirecional** para calcular a velocidade individual de cada uma das 4 rodas.
* **Segurança (Watchdog):** Implementa um sistema de desaceleração automática. Se o robô parar de receber comandos por 0.2s, ele desacelera suavemente as rodas até zero (`deceleration_rate` configurada no [`wheel_specification.yaml`](config/wheel_specification.yaml)), evitando paradas bruscas que poderiam derrubar a carga ou danificar as caixas de redução.

### Saída: Odometria (`/odom` e `/tf`)
Lê o feedback dos encoders e da IMU para estimar onde o robô está.
* **Fusão de Sensores na Odometria:** 
    * **Translação (X/Y):** Calculada exclusivamente pelos Encoders (média das velocidades das rodas convertidas pela cinemática direta).
    * **Rotação (Yaw):** Prioriza a **IMU** (`/imu/data_filtered`). Se a IMU estiver ativa, o yaw da odometria é travado no yaw da IMU. Isso elimina o erro acumulado de giro (drift) que é muito comum em rodas mecanum devido ao deslizamento dos roletes.

---

## <a id="scripts"></a>3. Scripts de Comportamento e Alinhamento

Estes nós Python são "Executores" que respondem ao tópico `/scheduler/commands` (target: `align_block`, `align_table`, etc). Eles implementam lógicas de malha fechada para manobras de precisão onde o *Navigation Stack global* não seria adequado.

### `align_block.py` (Alinhamento Visual Fino)
Centraliza o robô na frente de um bloco específico para permitir a pega correta pela garra.
* **Sensores:** Câmera (AprilTags).
* **Lógica de Controle:** 
    1. Procura a tag com o ID especificado.
    2. Calcula o erro lateral (eixo X da câmera) e o erro de profundidade (eixo Z da câmera).
    3. Aplica velocidades proporcionais (`cmd_vel.linear.y` para lateral, `cmd_vel.linear.x` para profundidade).
    4. Considera "Alinhado" quando o erro lateral é < 1cm e a distância é ~30cm. (*threshold*)
* **Payload do Scheduler:** `"ID_DO_BLOCO"` (ex: `"3"`).
* **Uso Típico:** Executado logo após chegar na área de manipulação para corrigir erros da varredura lateral.

### `align_table.py` (Alinhamento Perpendicular)
Garante que o robô esteja perfeitamente paralelo a uma bancada ou parede e a uma distância fixa.
* **Sensores:** Ultrassom Frontal Esquerdo e Direito (`/ultrasonic_distances`).
* **Lógica de Controle (Máquina de Estados):**
    1.  **STATE_ALIGNING:** Gira o robô (`angular.z`) comparando a leitura da esquerda e da direita. O objetivo é zerar a diferença (`diff = dir - esq`), o que garante paralelismo.
    2.  **STATE_FIX_DISTANCE:** Move linearmente (`linear.x`) até que a menor distância lida seja igual à distância alvo.
* **Payload do Scheduler:** `"DISTANCIA_ALVO_CM"` (ex: `"20.0"`).
* **Uso Típico:** Preparação para depositar objetos em prateleiras ou pegar itens alinhados na borda.

### `border_detect.py` (Detecção de Borda)
Move o robô lateralmente até encontrar uma descontinuidade no ambiente (ex: o fim de uma mesa ou o início de uma caixa).
* **Sensores:** Ultrassom Frontal Esquerdo e Direito.
* **Lógica de Controle:**
    * Desloca o robô lateralmente (`linear.y`) na direção solicitada.
    * Monitora a diferença entre a média dos sensores esquerdo e direito.
    * Se a diferença súbita ultrapassar `edge_threshold_cm` (15cm), assume que um dos sensores "saiu" da mesa (borda detectada).
    * Para imediatamente.
* **Payload do Scheduler:** `"esquerda"` ou `"direita"`.
* **Uso Típico:** Encontrar o ponto zero de uma bancada longa para indexar posições de depósito.

### `move_time.py` (Movimento Temporizado / Open-Loop)
Executa movimentos "cegos" baseados em tempo, sem feedback de posição (apenas velocidade constante).
* **Lógica:** Publica uma velocidade fixa (`Twist`) correspondente à direção solicitada durante o tempo especificado no `timeout` do comando.
* **Payload do Scheduler:** Direção (`"frente"`, `"tras"`, `"esquerda"`, `"direita"`, `"horario"`, `"antihorario"`). O tempo é definido pelo campo `timeout` da mensagem.
* **Uso Típico:** Recuar de uma doca de carga (onde sensores podem ficar confusos), sair da inércia, ou pequenas manobras onde a precisão milimétrica não é crítica.

### `imu_stable.py` (Utilitário de IMU)
Este nó não recebe comandos do Scheduler, mas roda em background para limpar os dados da IMU.
* **Problema:** IMUs brutas podem ter saltos de ângulo (ex: de -179° para +179°) ou iniciar com um offset aleatório (ex: Norte magnético).
* **Solução:** 
    * Zera o ângulo (Tare) na inicialização do nó.
    * Filtra descontinuidades matemáticas.
    * Publica `/imu/data_stable` para uso na odometria.

---

## <a id="calibracao"></a>4. Calibração e Testes

A precisão da navegação depende inteiramente da calibração física definida em [`config/wheel_specification.yaml`](config/wheel_specification.yaml).

```yaml
wheel_specification:
  wheel_radius: 0.0536       # Raio da roda (metros)
  wheel_separation_width: 0.15 # Distância lateral entre rodas
  wheel_separation_length: 0.1982 # Distância longitudinal entre rodas
```

### Procedimento de Calibração
O pacote inclui scripts para validar se "1 metro no código" equivale a "1 metro no chão".

1.  **Teste Linear (`teste_linear.py`):**
    ```bash
    rosrun robot_movement teste_linear.py
    ```
    * Edite o script para definir o eixo ('x' ou 'y') e a distância. O robô andará baseado na odometria.
    * Meça o deslocamento real. Se ele andou menos do que deveria, diminua o `wheel_radius`. Se andou mais, aumente.

2.  **Teste Angular (`teste_angular.py`):**
    ```bash
    rosrun robot_movement teste_angular.py
    ```
    * Faz o robô girar um número definido de voltas.
    * Se o giro físico não corresponder ao giro da odometria (IMU), verifique se a IMU está bem fixada e calibrada.

---

## <a id="uso"></a>5. Instalação e Uso

### Compilação
No workspace da Jetson:
```bash
cd ~/Work_2026/robot_ws
catkin build robot_movement
source devel/setup.bash
```

### Execução
Para rodar todo o sistema de movimentação (Hardware + Alinhadores):

1.  **Interface de Hardware:** (Geralmente incluído no `general.launch`)
    ```bash
    roslaunch robot_movement movement.launch
    ```

2.  **Alinhadores:** (Necessário para obedecer comandos do Scheduler)
    ```bash
    roslaunch robot_movement scheduler_mov.launch
    ```

> [!TIP]
> **Separação dos Launchs:** É importante saber que a separação dos launchs entre `movement.launch` (hardware) e `scheduler_mov.launch` é feito para que um destes seja sempre executado (`movement.launch`) para garantir a possibilidade de ao menos teleoperar o robô. Já o segundo só é necessário de ser habilitado através da *flag* `sched_movement` contida no [`general.launch`](../robot_utils/launch/general.launch) quando forem utilizados os nós que aguardam e tratam a comunicação através dos tópicos do *scheduler*.