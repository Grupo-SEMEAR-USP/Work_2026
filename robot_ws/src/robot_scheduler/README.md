# Gerenciador de Missão (Scheduler)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![Mission Control](https://img.shields.io/badge/Controle_de_Missão-%23FF6F00.svg?style=for-the-badge&logo=google-tasks&logoColor=white)

O pacote `robot_scheduler` atua como o **cérebro central** do robô. Ele é responsável por orquestrar a execução sequencial da missão, enviando comandos para os nós executores (Navegação, Manipulação, Visão) e aguardando confirmação de sucesso antes de prosseguir.

Este é o pacote **final** da pilha de software. Ele assume que todos os sistemas de baixo nível (hardware, sensores) e médio nível (algoritmos de alinhamento e navegação) já estão operacionais. Sua função é encadear essas capacidades modulares para realizar a prova completa da competição.

---

## Sumário

1. [Fluxo de Competição (Como Rodar)](#competicao)
2. [Estrutura do Pacote](#estrutura)
3. [Arquitetura de Comando](#arquitetura)
4. [Configurando a Missão](#missao)
5. [Pontos de Navegação](#pontos)

---

## <a id="competicao"></a>1. Fluxo de Competição (Como Rodar)

Para iniciar uma rodada oficial (Run), o procedimento foi simplificado para o uso de apenas dois terminais.

### Passo 1: Bring-up (Terminal 1)
Inicializa todo o hardware, sensores, drivers e os nós que ficam em "stand-by" (como a navegação e a visão).
```bash
roslaunch robot_utils general.launch
```
* **O que verificar:** Esta é a etapa que mais apresentará erros, devendo ser verificados os *debugs* descritos no [general](../robot_utils/README.md). Vocês terão alguns minutos para configurar o robô até iniciar a rodada, nestes momentos devem focar principalmente em garantir que o general rode de forma adequada. Assim que ele estiver ok, rodar o scheduler não será prolema e será o que marcará o início da rodada.

### Passo 2: Iniciar Missão (Terminal 2)
Assim que o general estiver ok, deve avisar que irá iniciar e então execute este comando. O robô aguardará um período para estabilização e iniciará a primeira tarefa do plano imediatamente.
```bash
roslaunch robot_scheduler scheduler.launch
```

> [!TIP]
> **Parada de Emergência:** Se precisar abortar a missão, dê um `Ctrl+C` no terminal do **Scheduler** (Terminal 2). O robô deve parar de receber comandos, mas continuará ligado e seguro pelo Terminal 1. Claro que no cenário de competição isso só é feito caso aborte a rodada.

---

## <a id="estrutura"></a>2. Estrutura do Pacote

```text
robot_scheduler/
├── CMakeLists.txt              # Configuração de compilação
├── package.xml                 # Dependências
├── config/                     
│   └── points.yaml             # Banco de dados de Waypoints (Poses de navegação)
├── launch/                     
│   └── scheduler.launch        # Inicia o nó mestre
└── scripts/                    
    └── scheduler.py            # O Script Principal (Máquina de Estados)
```

---

## <a id="arquitetura"></a>3. Arquitetura de Comando

O Scheduler não controla hardware diretamente. Ele delega tarefas através de um protocolo customizado sobre tópicos ROS.

### Fluxo de Comunicação
1.  **Envio (`/scheduler/commands`):** O Scheduler gera um ID único (`uid`) e envia um comando.
    * *Exemplo:* `uid=12345, target="navigation", payload="WS1", expect_ack=True, timeout=60`
    * O `uid` é um identificador para evitar a múltipla interpretação do mesmo comando.
    * O `target` está associado ao termo aguardado pelo nó que busca que capte o comando através do callback. Cada um dos nós adaptados para o scheduler possuem um específico.
    * O `payload` também é específico para o nó, podendo ser o nome no ponto que deve navegar, o tempo que uma movimentação vai ser mantida, a distância entre o alinhamento do robô e a mesa ou outros.
    * O `expect_ack` é apenas uma forma de especificar se o nó que está sendo comunicado possui tratamento para *feedback*. Caso seja verdadeiro, então o *scheduler* espera receber algum comando de retorno, como a validação da finalização da ação. Caso seja falso, apenas aguardará o tempo limite até o fim da ação.
    * Por fim, o `timeout` serve como um limite de tempo para efetuar a ação. Se for uma ação com *feedback*, este tempo é apenas um limite de segurança, caso a ação demore demais este será o tempo limite para que ignore tal função e pule para a próxima. No caso da ausência de *feedback*, este se torna o único fator que irá finalizar a ação, como no caso do `move_time`.
2.  **Burst:** O comando é enviado múltiplas vezes (8x) em rápida sucessão para garantir o recebimento mesmo em redes instáveis ou bridges seriais. A múltipla interpretação do mesmo comando é feito através do `uid`.
3.  **Execução:** O nó alvo (ex: `navigation.py`) recebe o comando, verifica se é para ele, e inicia a tarefa.
4.  **Feedback (`/scheduler/feedback`):** Ao terminar, o nó alvo responde.
    * *Exemplo:* `uid=12345, status="OK"`
5.  **Próximo Passo:** O Scheduler recebe o "OK", desbloqueia a thread principal e passa para a próxima linha do plano. Assim, não precisando aguardar até o fim do `timeout`.

### Campos da Tarefa
Cada passo da missão é definido por uma tupla:
`(Target, Payload, Need_Ack, Timeout)`

| Campo | Descrição |
| :--- | :--- |
| **Target** | Nome do nó executor (ex: `"navigation"`, `"manipulation"`, `"align_table"`). |
| **Payload** | Parâmetro da tarefa (ex: Nome do ponto, Distância em cm, ID do bloco). |
| **Need Ack** | `True`: Espera resposta "OK/FAIL" para continuar. `False`: Apenas espera o tempo passar (Open Loop). |
| **Timeout** | Tempo máximo (segundos) para esperar o Ack ou duração da pausa (se Ack=False). |

---

## <a id="missao"></a>4. Configurando a Missão

Para alterar a estratégia da competição, edite o script Python diretamente. Não é necessário recompilar.

1.  Abra [`scripts/scheduler.py`](scripts/scheduler.py).
2.  Localize a lista `self.plan` dentro do método `__init__`.
3.  Adicione ou remova passos conforme a estratégia da rodada.

**Exemplo de Plano de Missão:**
```python
self.plan = [
    # 1. Navegar até a Área de Trabalho 1 (Espera confirmação por até 60s)
    ("navigation", "WS1", True, 60),
    
    # 2. Alinhar com a mesa a 20cm (Espera alinhamento ultrassônico)
    ("align_table", "20.0", True, 15),
    
    # 3. Baixar o braço (Comando Open-Loop, espera 5s para garantir)
    ("manipulation", "arm,top_to_bottom15", False, 5.0),
    
    # 4. Alinhamento Fino Visual no Bloco 3
    ("align_block", "3", True, 30),
    
    # 5. Fechar a garra
    ("manipulation", "gripper,close", False, 2.0),
    
    # 6. Voltar para a Base (Start)
    ("navigation", "Start", True, 60)
]
```

---

## <a id="pontos"></a>5. Pontos de Navegação (`points.yaml`)

O arquivo [`config/points.yaml`](config/points.yaml) atua como o "mapa mental" dos locais importantes da arena.

* **Quem usa:** O nó `navigation.py` (do pacote `robot_navigation`) lê este arquivo para saber as coordenadas XYZ/Quaternion de destinos como "Start", "WS1", "Depósito".
* **Como gerar:** Utilize o script `waypoint_saver.py` (documentado em [`robot_navigation`](../robot_navigation/README.md)) para gravar novos pontos clicando no Rviz.
* **Importante:** O ponto chamado **`Start`** é especial. O sistema assume que o robô é ligado fisicamente exatamente nesta coordenada. Se o robô for ligado em outro lugar, toda a navegação subsequente estará deslocada.