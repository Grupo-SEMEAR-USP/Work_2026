# Comunicação e Mensageria (Hardware Abstraction Layer)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![UART](https://img.shields.io/badge/Serial-UART-%23FF6F00.svg?style=for-the-badge&logo=arduino&logoColor=white)
![Hardware](https://img.shields.io/badge/Hardware-Topology-%235C5C5C.svg?style=for-the-badge&logo=nvidia&logoColor=white)

O pacote `robot_communication` atua como a **Camada de Abstração de Hardware (HAL)** do robô. Ele isola a complexidade de comunicação com os microcontroladores (ESP32) do resto do sistema ROS.

Seus principais objetivos são:
1.  **Padronização de Dados:** Define todas as mensagens customizadas (`.msg`) usadas no projeto.
2.  **Ponte de Comunicação (Bridge):** Converte tópicos ROS em pacotes binários (UART) ou JSON (MQTT) para os drivers de motor e sensores.
3.  **Gerenciamento de USB:** Garante que o Linux reconheça corretamente qual ESP32 é qual, baseado na porta física onde foi conectado.

---

## Sumário

1. [Estrutura do Pacote](#estrutura)
2. [Configuração Crítica de Hardware (USB Topology)](#usb-setup)
    * [Procedimento de Criação das Regras](#procedimento)
    * [Mapeamento por ID (Alternativo)](#alternativo)
3. [Definições de Mensagens (.msg)](#msgs)
4. [Scripts de Comunicação e Utilitários](#scripts)
5. [Execução e Lançamento (Launch)](#lancamento)

---

## <a id="estrutura"></a>1. Estrutura do Pacote

```text
robot_communication/
├── CMakeLists.txt              # Configuração de build (Gera headers das mensagens)
├── package.xml                 # Dependências
├── launch/                     
│   └── communication.launch    # Inicia a ponte (Seletor UART/MQTT)
├── msg/                        # Definições de Tipos de Dados
│   ├── encoder_comm.msg        # Feedback de Odometria
│   ├── velocity_comm.msg       # Comando de Motores
│   ├── ultrasonic_comm.msg     # Sensores de Distância
│   ├── SchedulerCommand.msg    # Protocolo de Missão
│   ├── SchedulerResponse.msg   # Feedback de Missão
│   └── ... (AprilTag msgs)
└── scripts/                    
    ├── uart_comm.py            # Ponte Serial Principal
    ├── mqtt_comm.py            # Ponte Wi-Fi (Debug)
    └── reset_usb.py            # Utilitário de Reset físico do barramento USB
```

---

## <a id="usb-setup"></a>2. Configuração Crítica de Hardware (USB Topology)

O robô utiliza **três microcontroladores ESP32** idênticos (mesmo driver CP2102). Como eles possuem o mesmo `idVendor` e `idProduct`, e muitas vezes números de série genéricos de fábrica, o Linux não consegue diferenciá-los automaticamente (hoje o `ttyUSB0` pode ser a roda, amanhã pode ser o braço).

Para resolver isso, criamos o arquivo `/etc/udev/rules.d/99-usb-serial.rules` na Jetson. Ele utiliza regras **baseadas em Kernel (Topology)**, o que significa que **a porta física onde o cabo é conectado define o nome da ESP**.

### A Regra de Ligação Física
Para que o software funcione, a montagem física **DEVE** seguir estritamente este diagrama:

1.  **Na Jetson Nano:** Conecte o HUB USB na porta **Inferior Esquerda** (USB 3.0).
2.  **No HUB USB:** Segure o Hub com o cabo virado para a esquerda. A ordem das portas é:



| Posição no Hub | Microcontrolador | Função | Alias no Linux |
| :--- | :--- | :--- | :--- |
| **Porta 1 (Esq)** | ESP Manipulação | Braço, Garra, Ultrassom | `/dev/esp_manip` |
| **Porta 2 (Meio)** | ESP Traseira | Rodas Traseiras (RL, RR) | `/dev/esp_rear` |
| **Porta 3 (Dir)** | ESP Frontal | Rodas Frontais (FL, FR) | `/dev/esp_front` |

### Arquivo de Regras (`99-usb-serial.rules`)
O conteúdo atual do arquivo na Jetson é:

```bash
# Caminho: /etc/udev/rules.d/99-usb-serial.rules

# Mapeamento por Topologia Física (Hub na porta USB inferior esquerda da Jetson)
SUBSYSTEM=="tty", KERNELS=="1-2.2.4:1.0", SYMLINK+="esp_manip"
SUBSYSTEM=="tty", KERNELS=="1-2.2.3:1.0", SYMLINK+="esp_rear"
SUBSYSTEM=="tty", KERNELS=="1-2.2.2:1.0", SYMLINK+="esp_front"
```

---

### <a id="procedimento"></a> Como replicar este procedimento (Passo a Passo)

Caso precise substituir o Hub USB ou mudar a porta na Jetson, os endereços `KERNELS` mudarão. Siga este tutorial para descobrir os novos endereços:

1.  **Desconecte tudo** da USB da Jetson, deixando apenas o Hub.
2.  **Conecte apenas UM dispositivo** na porta do Hub que deseja mapear (ex: Porta 1).
3.  Verifique qual nome temporário o Linux deu (geralmente `ttyUSB0`):
    ```bash
    ls /dev/ttyUSB*
    ```
4.  **Descubra o endereço do Kernel (KERNELS):**
    Rode o comando abaixo trocando `ttyUSB0` pelo que apareceu no passo anterior:
    ```bash
    udevadm info --name=/dev/ttyUSB0 --attribute-walk | grep KERNELS
    ```
    * Você verá uma lista. O endereço correto geralmente é o primeiro ou o segundo (o mais longo), ex: `"1-2.2.4:1.0"`.
    * Esse número representa: `Barramento-PortaJetson.PortaHub:Interface`.
5.  **Edite/Crie o arquivo de regras:**
    ```bash
    sudo nano /etc/udev/rules.d/99-usb-serial.rules
    ```
    Adicione a linha seguindo o padrão:
    `SUBSYSTEM=="tty", KERNELS=="<SEU_ENDERECO_ENCONTRADO>", SYMLINK+="<NOME_DESEJADO>"`
6.  **Repita** para as outras portas.
7.  **Aplique as alterações:**
    ```bash
    sudo udevadm control --reload-rules && sudo udevadm trigger
    ```
    Agora, ao rodar `ls /dev/esp*`, você deve ver seus dispositivos.

---

### <a id="alternativo"></a> Método Alternativo: Mapeamento por ID
Se, no futuro, você substituir as ESPs por placas diferentes (ex: um Arduino Mega e uma ESP32), elas terão identificadores únicos de fábrica. Nesse caso, **é mais seguro usar o ID do que a porta física**, pois permite ligar em qualquer lugar.

1.  Descubra o ID do dispositivo conectado:
    ```bash
    lsusb
    # Ou para detalhes:
    udevadm info -a -n /dev/ttyUSB0 | grep idVendor
    udevadm info -a -n /dev/ttyUSB0 | grep idProduct
    udevadm info -a -n /dev/ttyUSB0 | grep serial
    ```
2.  No arquivo `.rules`, a sintaxe mudaria para:
    ```text
    # Exemplo hipotético para Arduino e ESP
    SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0042", SYMLINK+="meu_arduino"
    SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{serial}=="0001", SYMLINK+="minha_esp"
    ```
    * **Nota:** No nosso projeto atual, não usamos isso porque as 3 ESPs possuem o mesmo `idVendor` e `idProduct`.

---

## <a id="msgs"></a>3. Definições de Mensagens (.msg)

Para garantir que todos os nós falem a mesma língua, definimos os seguintes tipos:

### Comandos e Feedback de Hardware
* **`velocity_comm.msg`**: Comando de velocidade alvo para as 4 rodas (rad/s).
* **`encoder_comm.msg`**: Leitura real da velocidade das rodas (rad/s) para a odometria.
* **`ultrasonic_comm.msg`**: Distâncias lidas pelos sensores ultrassônicos (passadas em cm).

### Protocolo de Missão (Scheduler)
* **`SchedulerCommand.msg`**: Envio de ordens do cérebro para os executores.
    * `uid`: ID único para rastreamento (timestamp).
    * `target`: Nó alvo (ex: "navigation", "manipulation").
    * `payload`: Parâmetros (ex: "WS1", "gripper,open").
    * `need_ack`: Se exige confirmação.
* **`SchedulerResponse.msg`**: Resposta dos executores. Status "OK" ou "FAIL".

---

## <a id="scripts"></a>4. Scripts de Comunicação e Utilitários

### <a id="reset"></a> `reset_usb.py` (Recuperação de Falhas)
Este é um script de infraestrutura vital.
* **O Problema:** Em sistemas embarcados, é comum que conversores Serial-USB (CP2102) travem eletricamente ou percam a sincronia durante o boot da Jetson, ou quando há picos de corrente nos motores.
* **A Solução:** Este script envia um comando `ioctl` (USBDEVFS_RESET) diretamente ao kernel do Linux. Isso simula a ação de **desplugar e plugar o cabo USB fisicamente**, mas via software.

> [!IMPORTANT]
> **Como é feito o uso:** Não é implementado em nenhum launch, pois depende de uma sequência de detecçÕes. Para executar este *script*, é preciso rodar em um terminal paralelo o comando abaixo. O procedimento de sua execução deve ser:
> * Preferencialmente, deveria ser executado toda vez antes rodar o `general.launch`, principalmente quando for manter a comunicação UART. Porém, após uma execução bem sucedida, não é preciso replicar até que aconteça algum erro crítico na inicialização. 
> * Uma execução bem sucedida desse script é tal que 3 ESPs são identificadas e resetadas via ele (marcadas com [OK] no terminal de execução do `reset_usb`). É indicado validar que os três aliases de esp aparecem ao rodar `ls /dev/esp*`, além disso, indico que verifique também `ls /dev/lidar`. Se todas estas condições forem satisfeitas, pode prosseguir com a inicialização do general.
> * Caso o script não encontre uma das três ESPs, rode novamente o `ls /dev/esp*`. Se realmente faltar o alias de alguma esp, retire a esp faltante do hub, conecte novamente e rode o `ls` de novo. Continuou sem achar, então resete as ESPs usando o Switch e tente buscá-las novamente. Se seguir sem achar, reinicie a jetson.
> * Caso o script não encontre uma das três ESPs, mas o `ls /dev/esp*` retorna o alias das três ESPs, provavelmente houve algum problema na inicialização da atribuição das regras via Kernel e uma destas ESPs é na verdade o lidar. Você pode inclusive validar isso ao rodar `ls /dev/lidar` que provavelmente não encontrará nada. Este é um caso que é necessário reiniciar a jetson diretamente.

```bash
rosrun robot_communication reset_usb.py
```
### <a id="uart"></a> `uart_comm.py` (Bridge Serial - Produção)
Esta é a ponte principal indicada para uso a princípio. É um ponto de segurança já implementado que vocês podem sempre voltar caso tenham problemas com a comunicação. Claro, é indicado buscarem uma abordagem mais sofisticada e robusta, mas pelo que eu vi ao testar este novo *workspace*, a implementação está bem satisfatória e robusta após o início da execução. O único problema é a necessidade da pessoa ter conhecimento de todo o processo de debbuging descrito acima, pois realmente é muito instável para inicializar. Sua implementação é composta de:

* **Multithreading:** Abre 3 threads paralelas, uma para cada porta serial (`/dev/esp_front`, `/dev/esp_rear`, `/dev/esp_manip`).
* **Protocolo Binário:** Utiliza `struct.pack` para enviar dados compactados, minimizando o overhead e latência.
* **Robustez:** Se uma das ESPs não estiver conectada no início, o nó falha intencionalmente para evitar operação parcial insegura.

### <a id="mqtt"></a> `mqtt_comm.py` (Bridge Wi-Fi - Debug)
Alternativa para testes sem fio. Foi implementada na @Work 2025 nacional. A princípio, houveram muitos problemas com limitação de distância e/ou interferência em um ambiente com múltiplos dispositivos, além da variabilidade no IP interferir muito, visto que o broker deve ser fixado nos scripts. As alternativas tomadas na competição foram de configurar a frequência de comunicação do roteador com a Jetson para 5GHz (pois a maior parte dos dispositivos *bare-metal* são 2.4GHz, então há muita interferência), fixar o IP da jetson para facilitar o processo de inicialização e definir adequadamente o QoS para casos em que a perda de dados era menos prejudicial que o atraso, aliados com a ideia de embarcar o roteador fizeram os resultados deste protocolo ao fim da competição serem suficientemente satisfatórios. Porém, ainda houveram problemas, visto que a inicialização das ESPs com o broker apresentava instabilidade certas vezes (ESP tentar conectar via WiFi indefinidamente), o que fazia com que precisássemos verificar via teleop se ambas as ESPs estão movendo as rodas todas as vezes que elas eram resetadas (Sim, foi exatamente ao esquecer isso que rolou o erro na rodada final da nacional :P). Sua implementação é composta de:

* **Broker:** Conecta ao Mosquitto rodando na própria Jetson (`192.168.1.100`).
* **Formato:** Troca dados em **JSON** (legível por humanos), facilitando o debug via celular ou computador externo. Podendo ser verificada facilmente por outros dispositivos na mesma rede que a jetson, contanto que possuam *mosquitto client*, usando o código:
```bash
mosquitto_sub -h 192.168.1.100 -t "<tópico que quer olhar>"
```

> [!TIP]
> Como foi citado, usar este protocolo fez com que fosse necessário realizar configurações diretamente no roteador. Logo, saber fazer isso é essencial.
>
> Comece por conectar à rede atenaopen2023, depois acessar o link http://tplinkwifi.net. Ao entrar será pedido a senha de acesso local, sendo ela: Open!2023. Na tela que abrir, vá em "Advanced". No menu lateral, clique em "Network" -> "DHCP Server". Em **DHCP Client List** terão os dispositivos conectados à rede, busque o dispositivo que você quer fixar o IP (isso fica mais fácil ao conhecer o IP dos demais dispositivos, rodando `ip a` e buscando pelo IP que aparece em "wlp2s0"->"inet", sendo, por exemplo, 192.168.1.13). Ao identificar o IP buscado em **Assigned IP Address**, olhe para o campo **MAC Address** contido na mesma linha do dispositivo a fixar. Com o endereço MAC salvo, é apenas clicar em *Address Reservation*, colar o endereço MAC e decidir o IP que será que será fixado, contanto que esteja na mesma banda (192.168.1).
>
> Este procedimento já foi feito no passado, fixando a jetson no IP 100 e a rasp no IP 101.

---

## <a id="lancamento"></a>5. Execução e Lançamento (Launch)
Você pode escolher o modo de comunicação via argumento definido no launch de comunicação. O padrão é `UART` (Serial) por ter tido bons resultados nos testes iniciais, mas é possível modificar em [`communication.launch`](launch/communication.launch):


```launch
  <!-- MQTT ou UART -->
  <arg name="comm_mode" default="UART" />
```

Mas o lançamento da comunicação é feito, de fato, no launch de *bring-up* contido no [`general.launch`](../robot_utils/launch/general.launch) 