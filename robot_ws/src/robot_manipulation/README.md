# Controle de Manipulação (Braço Robótico)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![Kinematics](https://img.shields.io/badge/Cinemática-Direta-%23FF6F00.svg?style=for-the-badge&logo=geometry&logoColor=white)

Este pacote (`robot_manipulation`) gerencia a lógica de alto nível para o controle do braço robótico de 3 graus de liberdade não bloqueantes (Base Rotativa, Elevador Vertical e Punho) com uma garra. Ele traduz comandos abstratos de missão (ex: "abrir garra", "mover para depósito") em valores numéricos de baixo nível (passos de motor e ângulos de servo) que são enviados ao microcontrolador.

O sistema opera com uma lógica de **presets de movimento**, onde posições conhecidas são mapeadas para deslocamentos relativos pré-calibrados.

---

## Sumário

1. [Estrutura do Pacote](#estrutura)
2. [Arquitetura de Controle](#arquitetura)
3. [Como Usar](#uso)
    * [Lançar o Nó de Manipulação](#launch)
    * [Enviar Comandos Manuais](#manual)
4. [Mapeamento de Movimentos (Calibration Map)](#mapa)
    * [Entendendo os Valores](#valores)
    * [Adicionando Novas Posições](#novas)
5. [Ajuste Automático de Garra](#ajuste)

---

## <a id="estrutura"></a>1. Estrutura do Pacote

```text
robot_manipulation/
├── CMakeLists.txt              # Configuração de compilação
├── package.xml                 # Dependências
├── launch/                     
│   └── scheduler_manip.launch  # Inicia o nó de interface principal
└── scripts/                    
    ├── manipulation.py         # Nó principal: Traduz comandos do Scheduler
    └── gripper_adjust.py       # Nó auxiliar: Ajuste fino baseado em visão computacional
```

---

## <a id="arquitetura"></a>2. Arquitetura de Controle

O pacote funciona como um tradutor entre o `Scheduler` (Gerenciador de Missão) e o Hardware.

1.  **Entrada:** Tópico `/scheduler/commands` (Mensagem `SchedulerCommand`).
    * Formato esperado no payload: `"componente, ação"` (ex: `"gripper, open"`).
2.  **Processamento:** O script `manipulation.py` consulta um dicionário interno (`ACTION_MAP`) para encontrar os valores correspondentes.
3.  **Saída:**
    * `/arm_control` (`Float32MultiArray`): `[passos_base, passos_elevador]`
    * `/end_effector_control` (`Float32MultiArray`): `[angulo_punho, angulo_garra]`

> [!WARNING]
>
> **Atenção à Lógica de Movimento:**
> * **Motores de Passo (Base/Elevador):** Os valores enviados são interpretados pelo firmware como **Incrementos Relativos (Delta)**. Enviar o comando "subir" (1000 passos) duas vezes fará o robô subir 2000 passos.
> * **Servos (Punho/Garra):** Os valores são interpretados como **Ângulos Absolutos (Graus)**. Enviar "abrir" (15°) duas vezes manterá a garra na mesma posição (15°).
>
> **Lógica Implementada:**
> * Estes valores de movimentação buscados foram definidos manualmente, portanto, podem ser re-calibrados. 
> * Além disso, me recordo de uma limitação que foi posta em algum momento relacionada a não ser feito a leitura de dois comandos subsequentes com o mesmo valor para o mesmo sentido nos steppers, precisando alterar o número de passos mesmo que em uma unidade. Não me lembro se isso ainda está implementado pois não foi possível verificar a manipulação no novo workspace.

---

## <a id="uso"></a>3. Como Usar

### <a id="launch"></a>Lançar o Nó de Manipulação
Este nó deve rodar sempre que o robô estiver operacional para manipulação. Ele geralmente é chamado pelo `general.launch`, mas pode ser testado isoladamente:

```bash
roslaunch robot_manipulation scheduler_manip.launch
```

### <a id="manual"></a>Enviar Comandos Manuais
Para testar movimentos sem o Scheduler, você pode publicar diretamente no tópico de comandos. Isso é útil para calibrar posições.

**Exemplo 1: Abrir a Garra**
```bash
rostopic pub -1 /scheduler/commands robot_communication/SchedulerCommand "{uid: 1, target: 'manipulation', payload: 'gripper, open'}"
```

**Exemplo 2: Mover Elevador para o Topo**
```bash
rostopic pub -1 /scheduler/commands robot_communication/SchedulerCommand "{uid: 2, target: 'manipulation', payload: 'arm, top_to_deposit'}"
```

---

## <a id="mapa"></a>4. Mapeamento de Movimentos (Calibration Map)

Toda a inteligência cinemática do robô está contida no dicionário `ACTION_MAP` dentro de [`scripts/manipulation.py`](scripts/manipulation.py).

### <a id="valores"></a>Entendendo os Valores

| Componente | Chave no Código | Unidade | Comportamento | Exemplo |
| :--- | :--- | :--- | :--- | :--- |
| **Garra** | `gripper` | Graus (0-180) | Absoluto | `open`: 15.0 (Abre a pinça) |
| **Punho** | `wrist` | Graus (0-180) | Absoluto | `center`: 80.0 (Alinha com o braço) |
| **Base** | `rotatory_base` | Passos (Steps) | **Relativo** | `front_to_deposit1_left`: 3700.0 (pega o objeto e leva pela esquerda até o primeiro suporte) |
| **Elevador** | `arm` | Passos (Steps) | **Relativo** | `top_to_bottom0`: -14400.0 (Desce até altura da base) |

### <a id="novas"></a>Adicionando Novas Posições
Se você mudar a altura das prateleiras ou a distância dos depósitos, **não altere o código do Arduino**. Ajuste aqui:

1.  Abra `scripts/manipulation.py`.
2.  Localize o `ACTION_MAP`.
3.  Adicione ou edite a entrada desejada.
    * *Dica:* Para inverter a direção de um motor de passo, basta inverter o sinal do valor (ex: de `3000` para `-3000`).

---

## <a id="ajuste"></a>5. Ajuste Automático de Garra (`gripper_adjust.py`)

Este script implementa uma lógica reativa simples baseada em visão computacional. Ele serve para alinhar o punho da garra com objetos específicos (ex: Chave Allen) detectados pela câmera. Aparentemente foi implementado e utilizado na @Work Internacional, mas como não foram manipulados objetos reais na nacional de 2025, não utilizamos. 

* **Funcionamento:** Escuta o tópico `/identificacao`. Se detectar o objeto alvo (configurável, padrão "Allen"), envia uma rajada de comandos para o Scheduler solicitando um ajuste fino do punho.
* **Parâmetros:**
    * `target_class`: Nome do objeto a ser rastreado.
    * `burst_repeats`: Quantas vezes enviar o comando (para garantir que não se perca via UDP/Serial).

**Para rodar separadamente:**
```bash
rosrun robot_manipulation gripper_adjust.py _target_class:="Allen"
```