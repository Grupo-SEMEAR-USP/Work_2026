# Utilitários e Bring-up (General Launch)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Shell](https://img.shields.io/badge/Shell-Bash-%234EAA25.svg?style=for-the-badge&logo=gnu-bash&logoColor=white)
![Hardware](https://img.shields.io/badge/Hardware-Topology-%235C5C5C.svg?style=for-the-badge&logo=nvidia&logoColor=white)

O pacote `robot_utils` é o ponto de entrada principal do sistema. Ele contém o **launch file mestre** ([`general.launch`](launch/general.launch)) que inicializa todo o hardware (sensores, microcontroladores) e software (visão, navegação) em uma única operação coordenada.

Além disso, ele centraliza as configurações críticas de infraestrutura, como filtros de lidar, configurações de log e regras de identificação de hardware (udev).

---

## Sumário

1. [Estrutura do Pacote](#estrutura)
2. [O Mestre: `general.launch`](#general)
    * [Fluxo de Inicialização e Remaps](#fluxo)
    * [Tabela de Argumentos e Customização](#args)
3. [Configuração de Hardware e Sensores (Udev Rules)](#udev)
4. [Scripts Utilitários](#scripts)
5. [Procedimento de Bring-up (Início da Rodada)](#uso)

---

## <a id="estrutura"></a>1. Estrutura do Pacote

```text
robot_utils/
├── CMakeLists.txt              # Configuração de build
├── package.xml                 # Dependências
├── config/                     
│   ├── laser_filter.yaml       # Filtro de "Caixa" (Remove o chassi do robô do Lidar)
│   └── rosconsole.config       # Configuração de Logs (Silencia avisos da RealSense)
├── launch/                     
│   └── general.launch          # O ARQUIVO MESTRE: Inicia o robô inteiro.
└── scripts/                    
    ├── align_with_container.py # (Legado) Lógica antiga de alinhamento por cor
    ├── image_save_*.py         # Utilitários para salvar fotos das câmeras
    ├── print_yaw.py            # Debug simples da bússola (IMU)
    └── timed_roslaunch.sh      # Script Bash para atrasar o início da navegação
```

---

## <a id="general"></a>2. O Mestre: [`general.launch`](launch/general.launch)

Este arquivo é o orquestrador do robô. Ele não apenas inicia nós, mas configura o pipeline de dados para que a navegação funcione. Abaixo detalhamos o comportamento interno de cada bloco.

### <a id="fluxo"></a>Fluxo de Inicialização e Pipelines

1.  **Pipeline de Odometria (IMU + RealSense):**
    * A câmera RealSense é iniciada com IMU ativado (`enable_gyro`, `enable_accel`).
    * **Filtro Madgwick:** O tópico bruto `/camera/imu` (que é ruidoso) é remapeado para `/imu/data_raw` e processado pelo nó `imu_filter_madgwick`.
    * **Estabilização:** O nó `imu_stable.py` pega o dado filtrado `/imu/data_filtered` e remove descontinuidades, publicando em `/imu/data_stable`.
    * *Resultado:* O pacote `robot_movement` usa esse dado estável para garantir que o robô ande reto.

2.  **Pipeline do Lidar (Filtragem de Chassi):**
    * O driver `rplidarNode` publica os dados brutos no tópico **`scan_raw`** (note o remap).
    * O nó `laser_filter` lê `scan_raw`, aplica a máscara definida em [`laser_filter.yaml`](config/laser_filter.yaml) (removendo os pontos que batem nos pilares do próprio robô) e publica o resultado limpo no tópico **`scan`**.
    * *Resultado:* O `gmapping` e `amcl` usam apenas o `scan` limpo, evitando que o robô ache que está colidindo consigo mesmo.

3.  **Pipeline de Navegação (Atraso Estratégico):**
    * A navegação (`robot_navigation`) é pesada e exige que a árvore de TF (Transformadas) esteja completa.
    * Para evitar erros de "Transform Timeout" no boot, o launch utiliza o script `timed_roslaunch.sh` para esperar **20 segundos** antes de subir o [`scheduler_nav.launch`](../robot_navigation/launch/scheduler_nav.launch), que é uma variação do launch de navegação sem interface gráfica e com menos poluição por *logs* no terminal.

### <a id="args"></a>Tabela de Argumentos e Customização

Você pode controlar exatamente o que o robô inicia alterando estes argumentos na linha de comando contido ao início do general.

#### Hardware (Ligado por padrão)
| Argumento | Padrão | Função | Quando desativar? (`:=false`) |
| :--- | :--- | :--- | :--- |
| `enable_realsense` | `true` | Inicia câmera RGBD e IMU. | Se o cabo USB da câmera estiver desconectado ou para testar apenas rodas. |
| `enable_lidar` | `true` | Inicia o laser 2D e o filtro de caixa. | Se o Lidar não estiver girando ou para testes de visão pura. |
| `enable_logitech` | `true` | Inicia a Webcam frontal USB. | Se a câmera não estiver conectada. |

#### Software e Funcionalidades
| Argumento | Padrão | Função | Quando desativar? (`:=false`) |
| :--- | :--- | :--- | :--- |
| `enable_communication` | `true` | Inicia por padrão a ponte UART (`uart_comm.py`). Ou então o devido protocolo. | **Crítico:** Desative se as ESPs estiverem desligadas para evitar spam de erro no terminal. |
| `enable_movement` | `true` | Inicia a Odometria e Cinemática (`movement.launch`). | Se quiser apenas visualizar sensores sem controlar motores. |
| `enable_urdf` | `true` | Carrega o modelo 3D do robô (`robot_description`). | Geralmente nunca, pois o TF depende disso. |
| `enable_vision` | `true` | Inicia o detector de AprilTags. | Se quiser economizar CPU ou não houver tags no ambiente. |

#### Integração com Scheduler (Modo Autônomo)
| Argumento | Padrão | Função | Cenário de Uso |
| :--- | :--- | :--- | :--- |
| `sched_navigation` | `true` | Inicia AMCL e MoveBase (com delay de 20s). | **Crítico:** Defina como `false` quando for criar um mapa novo (`gmapping`) ou então quando estiver rodando a navegação de forma visual para salvar pontos, pois o AMCL conflita com o SLAM. |
| `sched_movement` | `true` | Inicia scripts de alinhamento (`align_block`, etc). | Apenas se for testar a base móvel isoladamente. |
| `sched_manipulation` | `true` | Inicia scripts do braço (`manipulation.py`). | Se o braço estiver desligado ou em manutenção. |

> [!IMPORTANT]
> Esta é a etapa em que a maior parte dos erros aparece. Certas vezes, alguns processos de inicialização de hardware falham de forma aleatória, o mais comum destes é o lidar. Sempre que aparecer mensagens de erro (letras vermelhas) relacionadas, mate o terminal e rode `ls /dev/lidar`, se o lidar for encontrado não há erros, deve apenas tentar novamente até dar certo. Caso o alias do lidar não apareça, pode ser o conflito da Udev das ESPs, conforme descrito na [comunicação](../robot_communication/README.md), sendo necessário apenas reiniciar a jetson. Mas se continuar, pode ser um erro nas regras Udev do próprio lidar, devendo verificá-las nos documentos descritos na próxima seção.
> 
> Outro hardware que tende a falhar é a inicialização da imu, que deve ser feita sempre que a realsense for habilitada. Por isso, sempre que estiver finalizando o lançamento do general (indico testar isso após o lançamento com delay da navegação começar) você deve verificar o tópico básico da imu através de `rostopic echo /camera/imu`, se este tópico não possuir publicações, mate o lançamento e reinicie até que dê certo para garantir que a odometria será feito através dela e não dos encoders (que é possível, mas bem mais impreciso e difícil de tunar).
>
> Por fim, o erro mais comum de ocorrer nesta etapa é na comunicação. Caso esteja usando UART, tenha em mente que por vezes é possível que por uma condição de corrida apareça um erro relacionado à conexão uart ou não existência de `serial_port`, porém, se após isso aparecer `Conectado: ESP_rear` **e** `Conectado: ESP_front`, funcionou e pode ignorar o erro. Caso alguma das ESPs não conecte, observe o procedimento descrito na [comunicação](../robot_communication/README.md). Porém, indiferente de qual protocolo for usado, indico sempre verificar se as ESPs estão comunicando com o alto nível realizando `rostopic echo /encoder_data` e `rostopic echo /ultrasonic_distances`, devendo existir dados em ambos após o fim do launch.

---

## <a id="udev"></a>3. Configuração de Hardware e Sensores (Udev Rules)

O Linux atribui nomes como `/dev/ttyUSB0` de forma aleatória. Para garantir que o Lidar seja sempre o Lidar e as ESPs não se misturem, utilizamos regras **Udev**.

### Verificando as Regras Instaladas
Na Jetson, verifique o conteúdo da pasta `/etc/udev/rules.d/`:

```bash
ls /etc/udev/rules.d/
# Você deve ver:
# 99-usb-serial.rules  (Para as ESPs)
# 99-robot-sensors.rules (Para Lidar e Câmera)
# 99-usb-reset.rules   (Permissões de Reset)
```

### 1. Regra das ESPs (`99-usb-serial.rules`)
Utiliza **Topologia Física (Kernels)**. A porta do Hub onde você conecta o cabo define quem é a ESP.
* **Dependência:** Exige que o Hub USB esteja conectado na porta inferior esquerda da Jetson e as ESPs na ordem correta no Hub.
* **Aliases Criados:** `/dev/esp_front`, `/dev/esp_rear`, `/dev/esp_manip`.

### 2. Regra dos Sensores (`99-robot-sensors.rules`)
Utiliza **Identificadores Únicos (Serial/Vendor ID)**. Não importa onde você conecta, o sistema acha pelo ID do chip.

**Conteúdo do Arquivo:**
```text
# LIDAR: Identificado pelo Serial Number único do conversor CP2102
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="17a4395577272a4188a16e3495044469", SYMLINK+="lidar", MODE="0666"

# WEBCAM: Identificada pelo ID da Logitech
SUBSYSTEM=="video4linux", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="0825", ATTR{index}=="0", SYMLINK+="cam_logitech"
```

> [!WARNING]
> **Troca de Hardware:** Se você substituir o Lidar por outro igual, o número de série (`ATTRS{serial}`) mudará. Você **precisa** descobrir o novo serial com `udevadm info -a -n /dev/ttyUSBx | grep serial` e editar este arquivo, caso contrário o robô não achará o `/dev/lidar`.

### 3. Regra de Reset (`99-usb-reset.rules`)
Dá permissão (`MODE="0666"`) para que o script python [`reset_usb.py`](../robot_communication/scripts/reset_usb.py) possa resetar as portas USB sem precisar de senha de root/sudo.

---

## <a id="scripts"></a>4. Scripts Utilitários

### `timed_roslaunch.sh`
Um "wrapper" simples em Bash. O ROS não tem um comando nativo de "esperar X segundos antes de iniciar um nó". Este script resolve isso.
* **Sintaxe:** `timed_roslaunch.sh [segundos] [pacote] [arquivo_launch] [argumentos]`
* **Uso no General:** Usado para dar tempo ao Lidar e à RealSense publicarem TFs estáveis antes de iniciar o `amcl` contido no launch de navegação.

### `image_save_*.py`
Scripts rápidos para salvar uma foto da câmera (Logitech ou RealSense) no disco. Útil para coletar dataset ou validar se a lente está suja sem abrir o Rviz (o que é pesado na Jetson).
* **Caminho:** Salva em `~/Documents/Work_2025/jetson/robot_ws/src/robot_utils/imgs`, observando que este é um script obsoleto que ainda não foi adaptado, portanto, é preciso configurá-lo caso queira utilizar sua função.

### `align_with_container.py` (Legado)
Lógica antiga de alinhamento baseada em cor (HSV). **Não está em uso ativo** na arquitetura atual (que migrou para AprilTags no `robot_vision`), mas foi mantido no repositório como referência histórica de código de visão.

---

## <a id="uso"></a>5. Procedimento de Bring-up (Início da Rodada)

Este é o procedimento padrão de competição para garantir que tudo inicie sem falhas.

1.  **Reset USB (Obrigatório na primeira vez):**
    Antes de tudo, limpe o barramento USB para garantir que as ESPs não estão travadas.
    ```bash
    rosrun robot_communication reset_usb.py
    ```
    *Verifique se apareceram 3 [OK] e se `ls /dev/esp*` mostra 3 dispositivos.*

2.  **Launch Geral (Terminal 1):**
    Inicie o robô. Este terminal ficará rodando durante toda a prova.
    ```bash
    roslaunch robot_utils general.launch
    ```
    *Aguarde ~20 segundos. Você verá mensagens do "timed_roslaunch". Quando o AMCL disser "odom received", o robô está pronto.*

3.  **Iniciar Missão (Terminal 2):**
    Somente após o passo 2 estar estável.
    ```bash
    roslaunch robot_scheduler scheduler.launch
    ```