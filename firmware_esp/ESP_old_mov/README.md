# Controle de Baixo Nível (ESP32 - Firmware de Movimentação)

![ESP32](https://img.shields.io/badge/ESP32-%23E7352C.svg?style=for-the-badge&logo=espressif&logoColor=white)
![C/C++](https://img.shields.io/badge/c/c++-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![FreeRTOS](https://img.shields.io/badge/FreeRTOS-%2344B81A.svg?style=for-the-badge&logo=freertos&logoColor=white)
![PlatformIO](https://img.shields.io/badge/PlatformIO-%2324292e.svg?style=for-the-badge&logo=platformio&logoColor=white)

Este diretório contém o firmware desenvolvido para o microcontrolador **ESP32**, responsável pelo controle de **locomoção** do robô (ponte H, encoders e PID). O sistema é modular e utiliza **FreeRTOS** para gerenciar tarefas de comunicação (MQTT ou UART) e controle em tempo real.

O código é projetado para rodar em duas placas simultaneamente: uma controlando o eixo **Frontal** e outra o eixo **Traseiro**.

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

A organização segue o padrão do PlatformIO com separação de componentes. O projeto inclui um componente customizado para PID na pasta `components`.

```text
ESP_MOV/
├── .pio/                   # Arquivos temporários de build
├── .vscode/                # Configurações do editor
├── components/
│   └── pid_ctrl/           # Componente IDF customizado para controle PID
├── include/                # Headers globais
├── lib/
│   ├── encoder/            # Driver do periférico PCNT (Leitura de quadratura)
│   ├── h_bridge/           # Driver do periférico LEDC (PWM motores)
│   ├── mqtt_communication/ # Cliente MQTT, Parser JSON e Wi-Fi
│   ├── pid/                # Implementação de alto nível do PID
│   ├── task_manager/       # Orquestrador das Tasks do FreeRTOS
│   ├── uart_communication/ # Driver UART e Parser de Bytes
│   └── utils/              # Definições globais, GPIOs e constantes
├── src/
│   ├── main.c              # Ponto de entrada (app_main)
│   └── CMakeLists.txt      # Configuração de build do source
├── platformio.ini          # Configuração do compilador e serial monitor
└── sdkconfig               # Configurações do ESP-IDF (via menuconfig)
```

---

## <a id="hardware"></a>3. Configuração de Hardware (Pinout)

O mapeamento dos pinos é definido em `lib/utils/utils.h`. O firmware suporta duas configurações (`FRONT` e `REAR`).

### Pinagem (ESP32 DevKit V1)

| Componente | Função | Pino Frontal | Pino Traseiro |
| :--- | :--- | :--- | :--- |
| **Motor Esq.** | PWM | GPIO `25` | GPIO `25` |
| | Input 1 | GPIO `2` | GPIO `27` |
| | Input 2 | GPIO `4` | GPIO `32` |
| **Motor Dir.** | PWM | GPIO `26` | GPIO `26` |
| | Input 1 | GPIO `32` | GPIO `4` |
| | Input 2 | GPIO `27` | GPIO `2` |
| **Encoder Esq.** | Canal A | GPIO `14` | GPIO `14` |
| | Canal B | GPIO `15` | GPIO `15` |
| **Encoder Dir.** | Canal A | GPIO `18` | GPIO `18` |
| | Canal B | GPIO `19` | GPIO `19` |
| **Standby** | Enable | GPIO `33` | GPIO `33` |

> [!NOTE]
> A UART utiliza os pinos padrão associados à UART0 (TX=1, RX=3) conectada via USB.

---

## <a id="configuracao"></a>4. Configuração do Firmware

Antes de carregar o código, você deve ajustar as definições no arquivo **`src/main.c`**. O sistema possui flags booleanas projetadas para validar a eletrônica e a montagem física antes de rodar o controle completo.

### 1. Parâmetros Principais
No início da função `app_main`, configure a identidade e o modo de operação:

```c
void app_main(void) {
    COMM_MODE = MQTT;       // Modos: UART, MQTT ou NONE
    ESP_POSITION = FRONT;   // Identidade: FRONT ou REAR
    
    // ... Flags de Debug (ver abaixo)
}
```

> [!IMPORTANT]
> **Conflito de Identidade:** Nunca ligue dois ESP32 com a mesma `ESP_POSITION` na mesma rede MQTT, pois haverá conflito de tópicos. Além de provavelmente manter uma esp disfuncional por seu gpio.

### 2. Modos de Debugging e Diagnóstico
As flags booleanas no `app_main` permitem isolar subsistemas para testes de hardware.

#### a) Debug de Encoders (`debug_encoders = true`)
Isola a leitura dos sensores para validação física.
* **Como testar:** Com a flag ativa e as demais desativadas, gire a roda do robô **com a mão**.
* **O que verificar:**
    * Girar para **Frente** deve **incrementar** a contagem.
    * Girar para **Trás** deve **decrementar** a contagem.
* **Correção:** Se a contagem estiver invertida (ex: diminuindo ao girar para frente), os GPIOs dos canais A e B estão trocados. Ajuste as definições em `lib/utils/utils.h`. Mas caso a contagem não for alterada em algum dos sentidos (ou ambos), pode ser uma definição errada de pinos ou problemas eletrônicos.

#### b) Debug de Ponte H (`debug_motors = true`)
Isola o acionamento dos motores, ignorando o PID e comandos externos.
* **Objetivo:** Validar se a Ponte H está recebendo os sinais de controle corretamente.
* **Uso:** Útil para a equipe de eletrônica verificar tensões com multímetro ou validar se os GPIOs de direção (IN1/IN2) e PWM estão mapeados corretamente para fazer o motor girar e no sentido correto, tendo em mente que o envio de um pwm positivo deve acionar o motor para frente, caso contrário, inverta IN1 e IN2.

#### c) Silenciar Logs (`disable_logs = true`)
Desativa globalmente os prints (`ESP_LOG`) do sistema.
* **Redução de Jitter:** A escrita na serial consome tempo de CPU e recurso de hardware. Desativar logs evita pequenos atrasos nas Tasks críticas, prevenindo concorrência de hardware e instabilidade temporal (*jitter*).
* **Limpeza da UART:** Se estiver usando `COMM_MODE = UART`, isso impede que textos de log se misturem com o stream de dados binários, mantendo o canal de comunicação limpo (embora o protocolo de frames seja robusto a ruídos).

### 3. Configurar Wi-Fi (Apenas MQTT)
Se `COMM_MODE = MQTT`, edite as credenciais em `lib/mqtt_communication/mqtt_communication.c`:

```c
#define WIFI_SSID       "atenaopen2023"
#define WIFI_PASS       "rrrmmmaaa"
#define BROKER_URI      "mqtt://192.168.1.100"
```

Sabendo que estas são as configurações padrões para o uso do roteador atual (2025) do semear, utilizando como *BROKER* o ip da jetson, fixado em `192.168.1.100`.

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

### Solução de Problemas de Upload

Caso o processo de **Upload** falhe, siga os passos de diagnóstico abaixo:

#### a) Erro de Permissão na Porta (Linux)
Se o upload falhar com mensagens de "Access denied" ou "Permission denied", o seu usuário pode não ter permissão de escrita na porta USB.

1. Abra um terminal novo (Ctrl+Shift+` ou terminal do sistema).
2. Desconecte o ESP32 e rode o comando:
   ```bash
   ls /dev/tty*
   ```
3. Conecte o ESP32 novamente e rode o mesmo comando. Identifique qual novo dispositivo apareceu (geralmente nomeado como `/dev/ttyUSB0`, `/dev/ttyACM0` ou similar).
4. Libere a permissão de leitura e escrita temporariamente para essa porta (substitua pelo nome encontrado):
   ```bash
   sudo chmod a+rw /dev/ttyUSB0
   ```
5. Tente realizar o **Upload** novamente pelo menu do PlatformIO.

> [!NOTE]
> Se a placa **não aparecer** na lista ao rodar `ls /dev/tty*` mesmo após conectar, é provável que seu cabo USB seja apenas de **carga** (não passa dados). Teste com outro cabo ou verifique se a placa está queimada.

#### b) Placa não entra em modo de Gravação
Se a permissão estiver correta, mas o upload falhar com "Connecting.............", a placa pode não estar entrando no modo *Bootloader* automaticamente.

1. Clique em **Upload**.
2. Assim que aparecer "Connecting..." no terminal, **pressione e segure** o botão **BOOT** na placa ESP32 (para evitar atrasos no clique, indico começar a segurar desde antes).
3. Quando o terminal mostrar que começou a baixar os dados (ex: "Writing at 0x00010000..."), solte o botão **BOOT** (novamente, para evitar questões de *timing*, indico segurar por mais tempo, como até a porcentagem de upload estar bem avançada).

Se mesmo após isso ainda não for possível subir código, é possível que a ESP esteja queimada. Teste com um código simples (ex: um 'Hello World') segurando o *boot* por todo o período de upload. Caso não funcione, pode ser realmente problema no microcontrolador, teste outro. 

---

## <a id="modulos"></a>6. Descrição Detalhada dos Módulos (`lib/`)

Esta seção detalha a arquitetura de software, descrevendo a responsabilidade de cada módulo, suas abordagens de implementação e a descrição de suas funções (públicas e privadas).

### 1. Módulo de uso do Encoder
**Localização:** [`lib/encoder/`](lib/encoder/)  
**Arquivos:** [`encoder.h`](lib/encoder/encoder.h), [`encoder.c`](lib/encoder/encoder.c)

Responsável pela leitura dos encoders de quadratura utilizando o periférico de hardware **PCNT** (Pulse Counter) do ESP32. Esta abordagem evita o uso de interrupções de CPU para cada pulso, economizando processamento. O módulo utiliza macros `ENCODER_A` e `ENCODER_B` para alternar automaticamente os GPIOs com base na definição de `ESP_POSITION` (`FRONT` ou `REAR`).

#### Funções Públicas
* **`init_encoder(encoder_side_t side)`**
    * *Parâmetros:* `side` (Esquerdo ou Direito).
    * *Descrição:* Configura a unidade PCNT, define os limites de contagem (-10000 a 10000) e ativa o **filtro de glitches** (1000ns) para ignorar ruídos elétricos. Configura os canais A e B para decodificação em quadratura X4 (contagem em todas as bordas).
* **`get_encoder_vel(pcnt_unit_handle_t handler)`**
    * *Parâmetros:* `handler` (Handle da unidade PCNT).
    * *Descrição:* Retorna a contagem de pulsos acumulada desde a última leitura e **limpa** o contador imediatamente. Essencial para cálculos de velocidade ($\Delta S / \Delta t$).
* **`get_encoder_position(pcnt_unit_handle_t handler)`**
    * *Descrição:* Retorna a contagem acumulada **sem limpar** o contador. Utilizado para odometria absoluta.

---

### 2. Módulo de uso da Ponte H
**Localização:** [`lib/h_bridge/`](lib/h_bridge/)  
**Arquivos:** [`h_bridge.h`](lib/h_bridge/h_bridge.h), [`h_bridge.c`](lib/h_bridge/h_bridge.c)

Gerencia o acionamento dos motores DC via periférico **LEDC** (PWM). O módulo abstrai a lógica de direção, convertendo um sinal de controle negativo em inversão de pinos físicos.

#### Funções Privadas (Internas)
* **`_set_forward(motor_side_t side)`**
    * *Descrição:* Configura os GPIOs da Ponte H para rotação no sentido horário (Ex: IN1=`HIGH`, IN2=`LOW`).
* **`_set_backward(motor_side_t side)`**
    * *Descrição:* Configura os GPIOs para rotação no sentido anti-horário (Ex: IN1=`LOW`, IN2=`HIGH`).

#### Funções Públicas
* **`init_h_bridge(motor_side_t side)`**
    * *Descrição:* Inicializa os pinos de direção como saída e configura o timer do LEDC para operar a **5 kHz** com resolução de 13 bits. Ativa o pino de *Standby* (`STBY`) da ponte H.
* **`update_motor(motor_side_t side, float u)`**
    * *Parâmetros:* `side` (Motor alvo), `u` (Ação de controle, podendo ser positiva ou negativa).
    * *Descrição:* Avalia o sinal de `u`. Se positivo, chama `_set_forward`; se negativo, chama `_set_backward`. Em seguida, calcula o valor absoluto do Duty Cycle e atualiza o canal PWM.

---

### 3. Módulo de comunicação MQTT
**Localização:** [`lib/mqtt_communication/`](lib/mqtt_communication/)  
**Arquivos:** [`mqtt_communication.h`](lib/mqtt_communication/mqtt_communication.h), [`mqtt_communication.c`](lib/mqtt_communication/mqtt_communication.c)

Gerencia a conexão Wi-Fi e o ciclo de vida do cliente MQTT. Utiliza JSON para troca de dados e implementa **Injeção de Dependência** para garantir Thread-Safety.

#### Funções Privadas (Internas)
* **`parse_motor_command(const char *data, int len, SemaphoreHandle_t mutex)`**
    * *Descrição:* Recebe o payload JSON cru. Utiliza a biblioteca `cJSON` para extrair os valores `left_front`, `right_front`, etc., baseando-se na identidade da placa. **Crítico:** Tenta obter o `mutex` antes de escrever nas variáveis globais `G_TARGET`, garantindo que o PID não leia um valor sendo modificado.
* **`mqtt_event_handler(...)`**
    * *Descrição:* Callback padrão do ESP-IDF. Gerencia eventos como `MQTT_EVENT_CONNECTED` (para realizar a inscrição no tópico) e `MQTT_EVENT_DATA` (que chama o parser quando chegam dados). O handle do Mutex é recuperado do contexto do evento (`user_context`).

#### Funções Públicas
* **`init_wifi()`**: Inicializa a stack TCP/IP, configura o SSID/Senha e conecta ao Access Point.
* **`mqtt_start(SemaphoreHandle_t mutex_handle)`**
    * *Parâmetros:* `mutex_handle` (O Mutex criado no `task_manager`).
    * *Descrição:* Configura e inicia o cliente MQTT. O ponto chave é que o `mutex_handle` é passado como argumento de contexto para o *Event Loop*, permitindo que o handler interno tenha acesso seguro às variáveis globais.
* **`mqtt_publish_encoders()`**: Cria um objeto JSON com as velocidades atuais (`G_RADS_L/R`) e publica no tópico de estado.
* **`mqtt_stop()`**
    * *Descrição:* Desconecta o cliente do Broker, destroi a instância do cliente MQTT para liberar memória da Heap e reseta o handle estático `s_client` para `NULL` para evitar uso indevido.

---

### 4. Módulo de controle PID
**Localização:** [`lib/pid/`](lib/pid/)  
**Arquivos:** [`pid.h`](lib/pid/pid.h), [`pid.c`](lib/pid/pid.c)

Atua como um *wrapper* de alto nível para o componente nativo `pid_ctrl` do ESP-IDF. Realiza a conversão de unidades (Ticks $\to$ Rad/s) e aplica a ação de controle acumulativa.

#### Funções Privadas (Internas)
* **`PWM_limit(float *PWM)`**
    * *Parâmetros:* `PWM` (Ponteiro para o valor de saída).
    * *Descrição:* Aplica saturação (Clamping). Se o valor calculado exceder `LEDC_MAX_DUTY` (8191), ele é limitado a este teto. O mesmo vale para o limite inferior negativo.

#### Funções Públicas
* **`init_pid(pid_side_t side)`**
    * *Descrição:* Cria o bloco de controle PID, configurando as constantes $K_p, K_i, K_d$ e os limites de *Wind-up* do integrador definidos nas macros (`KP_L`, `KI_L`, etc).
* **`pid_calculate(...)`**
    * *Parâmetros:* Handles dos blocos PID e dos Encoders (Esq/Dir).
    * *Descrição:* 
        1. Lê a velocidade crua dos encoders via `get_encoder_vel`.
        2. Converte ticks para Radianos/segundo usando a constante `TICKS_TO_RADS`.
        3. Calcula o erro ($Target - Atual$).
        4. Computa a saída do PID e soma à variável global de PWM (`G_PWM_L/R`), caracterizando um controle incremental na saída.
        5. Aplica `PWM_limit` para segurança.

---

### 5. Módulo de organizador das Tasks
**Localização:** [`lib/task_manager/`](lib/task_manager/)  
**Arquivos:** [`task_manager.h`](lib/task_manager/task_manager.h), [`task_manager.c`](lib/task_manager/task_manager.c)

Orquestrador do sistema. Inicializa drivers globais (NVS, Mutexes) e fixa as tarefas nos núcleos do ESP32.

#### Tarefas Internas (Tasks)
* **`actuators_task` (Core 1, Prioridade Alta)**: Responsável pelo controle fino.
    * Usa `vTaskDelayUntil` para garantir um período de execução estrito de 50ms (20Hz).
    * Protege a chamada do cálculo PID com `xDataMutex`.
* **`mqtt_task` / `uart_task` (Core 0, Prioridade Média)**: 
    * Inicializa a comunicação escolhida.
    * No caso do MQTT, repassa o `xDataMutex` para o driver.
    * Loop infinito verificando dados recebidos e publicando telemetria periodicamente.

#### Funções Públicas
* **`init_tasks()`**: Cria o Mutex Global, inicializa o armazenamento NVS e dispara as tasks `xTaskCreatePinnedToCore` conforme o modo de operação selecionado (`COMM_MODE`).

---

### 6. Módulo de comunicação UART
**Localização:** [`lib/uart_communication/`](lib/uart_communication/)  
**Arquivos:** [`uart_communication.h`](lib/uart_communication/uart_communication.h), [`uart_communication.c`](lib/uart_communication/uart_communication.c)

Implementa um protocolo binário customizado robusto, baseado em **Máquina de Estados Finita (FSM)**, para comunicação via cabo USB (Serial).

#### Funções Privadas (Internas)
* **`calculate_checksum()`**: Soma todos os bytes do payload e aplica uma máscara de 8 bits (`& 0xFF`).
* **`process_received_byte(uint8_t byte, uart_comm_t *cmd)`**: O coração do parser. Implementa a FSM com os estados:
    1.  `STATE_WAIT_SOF`: Aguarda o Byte de Início (`0xAA`).
    2.  `STATE_WAIT_DATA`: Armazena os bytes seguintes no buffer até completar o tamanho da struct.
    3.  `STATE_WAIT_CHK`: Compara o checksum recebido com o calculado.
    4.  `STATE_WAIT_EOF`: Valida o Byte de Fim (`0xBB`). Se tudo estiver correto, popula a struct `cmd`.
* **`uart_send_frame(uart_comm_t *cmd)`**: Serializa a struct em um array de bytes, adiciona cabeçalho, rodapé e checksum, e envia via `uart_write_bytes`.

#### Funções Públicas
* **`init_uart()`**
    * *Descrição:* Configura a UART0 com Baud Rate de **115200**, 8 bits de dados, sem paridade e 1 stop bit (8N1). Instala o driver com buffers de TX e RX (1024 bytes) para evitar bloqueios.
* **`uart_read(uart_comm_t *cmd)`**
    * *Descrição:* Lê o buffer da UART em blocos e alimenta a função `process_received_byte`. Retorna `true` apenas se um pacote completo e válido foi decodificado.
* **`uart_send(uart_comm_t *cmd)`**
    * *Parâmetros:* `cmd` (Ponteiro para a struct de comando).
    * *Descrição:* Interface pública para envio. Chama internamente `uart_send_frame` para empacotar os dados (adicionar SOF, Checksum, EOF) e escrever na porta serial.

---

### 7. Módulo Utils
**Localização:** [`lib/utils/`](lib/utils/)  
**Arquivos:** [`utils.h`](lib/utils/utils.h), [`utils.c`](lib/utils/utils.c)

Atua como o "coração de dados" do sistema, centralizando todas as definições de hardware, constantes físicas e, crucialmente, as **variáveis globais** que permitem a troca de informações entre as Tasks (Comunicação e Controle).

#### Abordagem de Hardware
O arquivo define macros para todos os GPIOs utilizados. Ele separa fisicamente as definições de pinos para o eixo frontal (`F_...`) e traseiro (`R_...`).
* **Enums de Configuração:** Define os tipos `esp_pos_t` (`FRONT`/`REAR`) e `communication_mode_t` (`UART`/`MQTT`), que são usados no `main.c` para decidir o comportamento do firmware em tempo de execução.

#### Variáveis Globais (Estado Compartilhado)
Como o FreeRTOS divide o código em tarefas isoladas, o `utils` fornece o espaço de memória comum onde os dados são trocados.
* **Configuração:** `COMM_MODE` e `ESP_POSITION`.
* **Controle (Setpoints):** `G_TARGET_L`, `G_TARGET_R`. São escritas pela Task de Comunicação (protegidas por Mutex) e lidas pela Task de Atuação (PID).
* **Feedback (Sensores):** `G_RADS_L`, `G_RADS_R`. Armazenam a velocidade real em Rad/s calculada pelo PID, para ser lida e enviada pela Task de Comunicação.
* **Atuação:** `G_PWM_L`, `G_PWM_R`. Armazenam o esforço de controle calculado para debug ou telemetria.
* **Flags:** `BREAK_FLAG`. Usada para sinalizar condições de parada total ou emergência.

---

## <a id="arquitetura"></a>7. Arquitetura de Tarefas (RTOS)

O sistema utiliza o **FreeRTOS** para dividir o processamento em dois núcleos (*Cores*) do ESP32, garantindo que a comunicação não bloqueie o controle dos motores.

| Task | Core | Descrição |
| :--- | :--- | :--- |
| **`actuators_task`** | 1 | Executa o loop de controle PID a 20Hz (50ms). Lê encoders, calcula erro e atualiza PWM. |
| **`mqtt_task`** ou `uart_task` | 0 | Gerencia a conexão. Recebe comandos de velocidade e publica a telemetria dos encoders. |

### Sincronização
O acesso às variáveis globais de *Setpoint* (`G_TARGET`) é protegido por um **Mutex** (`xDataMutex`), evitando que o controlador PID leia um valor de velocidade "pela metade" enquanto a comunicação está atualizando os dados.

---

## <a id="protocolos"></a>8. Protocolos de Comunicação

### Modo MQTT (Wi-Fi)
Utiliza JSON para troca de mensagens. O ESP subscreve em comandos e publica estados.

* **Tópico de Comando:** `command/motors`
* **Payload Recebido:**
  ```json
  {
    "left_front": 5.0,
    "right_front": 5.0,
    "left_rear": 5.0,
    "right_rear": 5.0
  }
  ```
  *(O ESP filtra apenas as chaves referentes à sua `ESP_POSITION`).*

* **Tópico de Estado:** `state/encoders`
* **Payload Publicado:**
  ```json
  {
    "left_front": 4.9,
    "right_front": 5.1
  }
  ```

### Modo UART (Serial/USB)
Utiliza um protocolo binário customizado para máxima velocidade e menor overhead.

**Estrutura do Frame (15 bytes):**
`[SOF] [Payload] [Checksum] [EOF]`

* `SOF` (Start of Frame): `0xAA`
* `Payload` (8 bytes): 2 `floats` (Esquerda, Direita).
* `Checksum`: Soma simples dos bytes do payload.
* `EOF` (End of Frame): `0xBB`

---

> [!NOTE]
> **Debugging Comum:**
> * **Brownout:** Se a ESP reiniciar indefinidamente, pode ser um problema com a alimentação da mesma. Deve-se verificar a conexão da ESP no Hub, ou de componentes que podem puxar corrente da ESP.
> * **Timeout MQTT:** Verifique se o IP do `BROKER_URI` está correto e se o computador e o ESP estão na mesma rede (ping o IP do computador).