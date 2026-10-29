# Controle de Baixo Nível (ESP32 - Firmware de Manipulação)

![ESP32](https://img.shields.io/badge/ESP32-%23E7352C.svg?style=for-the-badge&logo=espressif&logoColor=white)
![C/C++](https://img.shields.io/badge/c/c++-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![FreeRTOS](https://img.shields.io/badge/FreeRTOS-%2344B81A.svg?style=for-the-badge&logo=freertos&logoColor=white)
![PlatformIO](https://img.shields.io/badge/PlatformIO-%2324292e.svg?style=for-the-badge&logo=platformio&logoColor=white)

Este diretório contém o firmware desenvolvido para o microcontrolador **ESP32**, responsável pelo controle de **manipulação** do robô. O sistema gerencia motores de passo (base e elevador), servomotores (punho e garra) e sensores ultrassônicos de distância. A arquitetura é modular e utiliza **FreeRTOS** para orquestrar tarefas de comunicação (MQTT, UART ou CLI) e controle de hardware.

---

## Sumário

1. [Pré-requisitos](#pre-requisitos)
2. [Estrutura do Projeto](#estrutura)
3. [Configuração de Hardware (Pinout)](#hardware)
4. [Configuração do Firmware](#configuracao)
5. [Como Compilar e Carregar](#como-usar)
6. [Descrição Detalhada dos Módulos](#modulos)
7. [Arquitetura de Tarefas (RTOS)](#arquitetura)
8. [Protocolos de Comunicação](#protocolos)

---

## <a id="pre-requisitos"></a>1. Pré-requisitos

Para compilar e subir o código, você precisará do **VS Code** com a extensão **PlatformIO**.

### Instalação
1. Instale o [VS Code](https://code.visualstudio.com/).
2. Na aba de extensões (Ctrl+Shift+X), procure por **PlatformIO IDE** e instale.
3. Certifique-se de ter os drivers da ponte USB-Serial (CP210x ou CH340) instalados no seu sistema operacional.

---

## <a id="estrutura"></a>2. Estrutura do Projeto

A organização segue o padrão do PlatformIO, separando componentes de terceiros/drivers genéricos ([`components/`](components/)) da lógica de aplicação específica do robô ([`lib/`](lib/)).

```text
ESP_MANIPULATOR/
├── .pio/                       # Arquivos temporários de build
├── .vscode/                    # Configurações do editor
├── components/                 # Drivers Genéricos e Bibliotecas Externas
│   ├── esp_idf_lib_helpers/    # Macros auxiliares para compatibilidade IDF
│   ├── ssd1306/                # Driver para display OLED (I2C/SPI)
│   ├── stepper_motor_encoder/  # Driver RMT para encoder de motor de passo
│   └── ultrasonic/             # Driver de baixo nível para sensor HC-SR04
├── include/                    # Headers globais
├── lib/                        # Lógica de Aplicação (Específica do Robô)
│   ├── mqtt_communication/     # Cliente MQTT e Parser JSON
│   ├── servo_control/          # Controle de Servos (LEDC)
│   ├── stepper_control/        # Controle de Steppers (GPIO Bit-banging)
│   ├── task_manager/           # Orquestrador das Tasks do FreeRTOS
│   ├── terminal_cli/           # Interface de linha de comando para debug
│   ├── uart_communication/     # Protocolo Serial Binário
│   ├── ultrasonic_distance/    # Gerenciador dos 3 sensores de distância
│   └── utils/                  # Definições globais, GPIOs e constantes
├── src/
│   ├── main.c                  # Ponto de entrada (app_main)
│   └── CMakeLists.txt          # Configuração de build do source
├── platformio.ini              # Configuração do compilador e serial monitor
└── sdkconfig                   # Configurações do ESP-IDF (via menuconfig)
```

---

## <a id="hardware"></a>3. Configuração de Hardware (Pinout)

O mapeamento dos pinos é centralizado em [`lib/utils/utils.h`](lib/utils/utils.h).

### Pinagem (ESP32 DevKit V1)

| Atuador / Sensor | Função | Pino (GPIO) | Observação |
| :--- | :--- | :--- | :--- |
| **Stepper Elevador** | Passo (STEP) | `15` | Movimento Vertical |
| | Direção (DIR) | `2` | |
| **Stepper Base** | Passo (STEP) | `14` | Rotação da Base |
| | Direção (DIR) | `27` | |
| **Servo Punho** | PWM | `22` | Controle Angular (Wrist) |
| **Servo Garra** | PWM | `32` | Abertura/Fechamento (Gripper) |
| **Ultrassom 1** (Esq.) | Trigger | `26` | Front Left |
| | Echo | `25` | |
| **Ultrassom 2** (Dir.) | Trigger | `17` | Front Right |
| | Echo | `16` | |
| **Ultrassom 3** (Tras.)| Trigger | `19` | Rear Left |
| | Echo | `18` | |

> [!NOTE]
> A comunicação UART (Modo Serial) utiliza os pinos padrão da USB: **TX=1** e **RX=3**.

---

## <a id="configuracao"></a>4. Configuração do Firmware

Antes de carregar o código, ajuste o modo de operação no arquivo [`src/main.c`](src/main.c).

### 1. Seleção de Modo
No início da função `app_main` em [`src/main.c`](src/main.c), defina a variável `COMM_MODE`:

```c
void app_main(void) {
    // Escolha: MQTT, UART, CLI ou NONE
    COMM_MODE = MQTT; 
    
    // ...
}
```

* **MQTT:** Conecta ao Wi-Fi e recebe comandos via JSON.
* **UART:** Recebe comandos binários via Serial (USB).
* **CLI:** Abre um terminal de texto interativo para testes manuais (digite `help` no monitor serial).

### 2. Configurar Wi-Fi (Apenas Modo MQTT)
Se `COMM_MODE = MQTT`, edite as credenciais em [`lib/mqtt_communication/mqtt_communication.c`](lib/mqtt_communication/mqtt_communication.c):

```c
#define INTERNAL_WIFI_SSID       "atenaopen2023"
#define INTERNAL_WIFI_PASS       "rrrmmmaaa"
#define INTERNAL_BROKER_URI      "mqtt://192.168.1.100"
```

---

## <a id="como-usar"></a>5. Como Compilar e Carregar

O processo de compilação e gravação é feito inteiramente pela interface gráfica do PlatformIO dentro do VS Code.

### 1. Acessando o Menu do PlatformIO
1. Abra o VS Code **exatamente na pasta raiz do projeto** (`ESP_MOV`). Isso é crucial para que a extensão reconheça o arquivo `platformio.ini`.
2. No menu lateral esquerdo, localize o ícone do **PlatformIO** (ícone que parece uma **cabeça de formiga** ou alienígena).
   * *Caso o ícone não esteja visível:* Verifique se ele está oculto no menu "Additional Views" (clicando nos **três pontinhos** na parte inferior da barra lateral).
3. Aguarde alguns segundos até que a seção **Project Tasks** seja carregada no painel lateral.

### 2. Fluxo de Trabalho
Dentro de **Project Tasks**, expanda a opção referente à sua placa (ex: `esp32doit-devkit-v1/General`) e utilize os botões na seguinte ordem:

1. **Build:** Compila o código. Verifique se aparece `SUCCESS` no terminal.
2. **Upload:** Grava o firmware na placa conectada via USB.
3. **Monitor:** Abre o monitor serial para visualizar os logs (certifique-se de que a placa continua conectada).

---

## <a id="modulos"></a>6. Descrição Detalhada dos Módulos ([`lib/`](lib/))

Esta seção descreve a responsabilidade dos módulos de aplicação desenvolvidos.

### 1. Módulo `stepper_control`
**Localização:** [`lib/stepper_control/`](lib/stepper_control/)

* **Função:** Gerencia os motores de passo (Elevador e Base).
* **Lógica:** Utiliza bit-banging otimizado para gerar pulsos. Mantém uma fila de "passos restantes" (`s_remain`) e processa o movimento de forma bloqueante (mas cedendo CPU via `vTaskDelay`) para garantir o timing preciso dos pulsos.
* **API:** `move_stepper_elevator(int steps)`, `stepper_loop_process()`.

### 2. Módulo `servo_control`
**Localização:** [`lib/servo_control/`](lib/servo_control/)

* **Função:** Abstração do periférico **LEDC** para controle de servomotores.
* **Detalhes:** Configura o PWM a 50Hz. Converte ângulos (0° a 180°) para Duty Cycle (500us a 2500us).
* **API:** `set_servo_gripper(float angle)`, `set_servo_wrist(float angle)`.

### 3. Módulo `ultrasonic_distance`
**Localização:** [`lib/ultrasonic_distance/`](lib/ultrasonic_distance/)

* **Função:** Gerencia a leitura sequencial dos 3 sensores HC-SR04.
* **Dependência:** Usa o driver de baixo nível [`components/ultrasonic/`](components/ultrasonic/).
* **Lógica:** Realiza as leituras ciclicamente e atualiza o vetor global `G_US_CM` definido em [`lib/utils/`](lib/utils/). Insere pequenos delays entre leituras para evitar interferência de eco.

### 4. Módulo `mqtt_communication`
**Localização:** [`lib/mqtt_communication/`](lib/mqtt_communication/)

* **Função:** Gerencia Wi-Fi e Cliente MQTT.
* **Comportamento:**
    * **Subscribe:** Tópico `command/manipulator`. Recebe JSON com alvos (`arm`, `base`, `wrist`, `grip`).
    * **Publish:** Tópico `state/ultrasonic_distance`. Envia JSON com leituras dos sensores.
* **Lógica de Controle:** Ao receber um comando para Stepper, o valor é **somado** à variável global (Acumulador de Posição Absoluta).

### 5. Módulo `uart_communication`
**Localização:** [`lib/uart_communication/`](lib/uart_communication/)

* **Função:** Protocolo binário leve para comunicação serial rápida.
* **Frame:** `[SOF 0xAA] [Payload] [Checksum] [EOF 0xBB]`.
* **Uso:** Ideal para controle via Jetson/Raspberry Pi via USB, sem latência de rede.

### 6. Módulo `task_manager`
**Localização:** [`lib/task_manager/`](lib/task_manager/)

* **Função:** O cérebro do sistema. Inicializa drivers e cria as Tasks do FreeRTOS.
* **Lógica de Controle:**
    * Calcula o **Delta** entre a posição desejada (`G_STEPPER`) e a última posição processada (`last_pos`).
    * Envia apenas a diferença para o driver do motor (`move_stepper`).
    * Garante que comandos absolutos recebidos via MQTT/UART sejam traduzidos corretamente em movimentos relativos para o hardware.

---

## <a id="arquitetura"></a>7. Arquitetura de Tarefas (RTOS)

O sistema divide o processamento nos dois núcleos do ESP32 para máxima eficiência.

| Task | Core | Prioridade | Função |
| :--- | :--- | :--- | :--- |
| **`actuators_task`** | 1 | Alta (5) | Loop de controle de movimento (PID/Pulsos). Lê globais e aciona servos/steppers. |
| **`sensors_task`** | 1 | Média (3) | Leitura bloqueante dos sensores ultrassônicos. |
| **`comm_task`** | 0 | Alta (5) | Gerencia Wi-Fi/MQTT ou UART. Atualiza setpoints globais. |

> **Nota:** A separação de *cores* impede que o processamento pesado do Wi-Fi (Core 0) interfira na geração de pulsos dos motores (Core 1).

---

## <a id="protocolos"></a>8. Protocolos de Comunicação

### Modo MQTT (JSON)
* **Comando (Recebido):**
  ```json
  {
    "arm": 100.0,   // Incremento de passos
    "base": -50.0,
    "wrist": 90.0,  // Graus (Absoluto)
    "grip": 45.0
  }
  ```
* **Estado (Enviado):**
  ```json
  {
    "ts_ms": 12500,
    "front_left": 15.4,
    "front_right": 20.1,
    "rear_left": 0.0
  }
  ```

### Modo UART (Binário)
Estrutura `packed` para máxima velocidade.

* **Comando (Recebido - 16 bytes payload):**
    * `float arm_val`
    * `float base_val`
    * `float wrist_val`
    * `float grip_val`
* **Telemetria (Enviado - 12 bytes payload):**
    * `float front_left`
    * `float front_right`
    * `float rear_left`

---

> [!TIP]
> **Dica de Debug:** Se precisar testar um motor individualmente sem conectar ao Wi-Fi, altere `COMM_MODE` para `CLI` em [`src/main.c`](src/main.c), suba o código e use o monitor serial para digitar comandos como `arm 100` ou `grip 180`. É possível verificar os comandos com `help`.