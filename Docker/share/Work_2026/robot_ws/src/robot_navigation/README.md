# Sistema de Navegação Autônoma (ROS Noetic)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![C++](https://img.shields.io/badge/c++-%2300599C.svg?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![Jetson](https://img.shields.io/badge/NVIDIA-Jetson-%2376B900.svg?style=for-the-badge&logo=nvidia&logoColor=white)

Este pacote (`robot_navigation`) é o cérebro de movimentação autônoma do robô. Ele integra a **Localization (AMCL)**, o **Planejamento de Trajetória (Move Base / DWA)** e o **Mapeamento (GMapping)** para permitir que o robô navegue em ambientes conhecidos desviando de obstáculos dinâmicos.

O sistema foi configurado para um robô **Holonômico** (Omnidirecional) e possui integração direta com o sistema de agendamento de tarefas (`robot_scheduler`), permitindo a execução de missões baseadas em pontos nomeados (Waypoints).

---

## Sumário

1. [Pré-requisitos e Dependências](#pre-requisitos)
2. [Estrutura do Pacote](#estrutura)
3. [Procedimentos de Operação](#procedimentos)
    * [Fase 1: Mapeamento (SLAM)](#fase1)
    * [Fase 2: Gravação de Pontos (Waypoints)](#fase2)
    * [Fase 3: Navegação Autônoma](#fase3)
4. [Detalhes Técnicos da Navegação](#tecnica)
5. [Scripts e Integração](#scripts)
6. [Solução de Problemas Comuns](#troubleshooting)

---

## <a id="pre-requisitos"></a>1. Pré-requisitos e Dependências

Para que a navegação funcione, o hardware e os drivers de baixo nível devem estar operacionais.

### Hardware Obrigatório
* **Lidar 2D:** Deve estar publicando no tópico `/scan`.
* **Odometria:** O pacote `robot_utils` deve estar rodando para fornecer a transformação TF `odom -> base_footprint`.
* **Jetson Nano:** Ambiente Ubuntu 20.04 com ROS Noetic instalado.

### Dependências de Software
Para o funcionamento, foram instalados os seguintes pacotes ROS que estão na Jetson:

```bash
sudo apt-get install ros-noetic-navigation ros-noetic-gmapping ros-noetic-map-server ros-noetic-amcl ros-noetic-move-base ros-noetic-dwa-local-planner
```

Além dos pacotes internos do workspace:
* `robot_communication`: Para definições de mensagens (`SchedulerCommand`).
* `robot_scheduler`: Para armazenamento do arquivo `points.yaml`.

---

## <a id="estrutura"></a>2. Estrutura do Pacote

```text
robot_navigation/
├── CMakeLists.txt              # Configuração de compilação
├── package.xml                 # Dependências do pacote
├── config/                     # Parâmetros de calibração da navegação
│   ├── amcl_params.yaml        # Filtro de partículas (Localização)
│   ├── costmap_common.yaml     # Configurações comuns (Obstáculos/Inflação)
│   ├── costmap_global.yaml     # Mapa estático completo
│   ├── costmap_local.yaml      # Mapa dinâmico (janela deslizante)
│   ├── move_base_params.yaml   # Frequência do controlador
│   └── planner_local_dwa.yaml  # Velocidades e acelerações (DWA)
├── launch/                     # Arquivos de inicialização
│   ├── mapping.launch          # Inicia o SLAM (Gmapping)
│   ├── navigation.launch       # Inicia AMCL + MoveBase
│   └── scheduler_nav.launch    # Inicia Navegação + Nó de Controle Python
├── maps/                       # Arquivos gerados pelo SLAM (.pgm / .yaml)
├── rviz/                       # Predefinições de visualização
│   └── navigation.rviz
└── scripts/                    # Lógica de Aplicação
    ├── navigation.py           # Nó que recebe comandos do Scheduler
    └── waypoint_saver.py       # Utilitário para salvar coordenadas
```

---

## <a id="procedimentos"></a>3. Procedimentos de Operação

### <a id="fase1"></a>Fase 1: Mapeamento (SLAM)
Cria um mapa digital do ambiente.

1.  **Conexão SSH com Interface Gráfica:**
    Para visualizar o processo no seu computador, é preciso conectar-se à Jetson usando o X11 forwarding. Para isso, começamos por permitir o acesso à interface gráfica do computador *host* (seu pc) para outros elementos:

    ```bash
    # No seu computador (Host)
    xhost +
    ```

    Após ter permitido o acesso, podemos acessar a jetson via ssh compartilhando os recursos gráficos do host:

    ```bash
    ssh -X rmajetson@192.168.1.100
    ```

    Com esta flag após o ssh, será disponibilizado um acesso ao uso da interface gráfica do computador de origem, tendo atenção para o fato de ser "-X" para permitir o acesso, pois "-x" em letra minúscula faz o posto e retira este acesso aos elementos gráficos. Para verificar se o seu terminal interno à jetson está dispondo de elementos de interface do seu computador, é possível executar:

    ```bash
    echo $DISPLAY
    ```

    Espera-se visualizar algum localhost como retorno deste comando. Se o retorno for vazio, refaça o procedimento - verificando se realmente foi feito o `xhost +` antes -, pois o compartilhamento dos elementos gráficos não está sendo feito. 

2.  **Iniciar Hardware Base:**

    Como nesta etapa serão utilizados elementos do hardware do robô, como o lidar, é preciso que tenha sido executado o bring-up que inicialize os componentes. Isso pode ser feito em um outro terminal sem acesso à interface gráfica, usualmente o primeiro terminal que abrimos na jetson.

    ```bash
    roslaunch robot_utils general.launch
    ```

    Observe que esta etapa de inicialização é crítica, apresentando diversos tipos de erros que serão melhor detalhados na descrição do pacote [robot_utils](../robot_utils/README.md).

3.  **Iniciar Mapeamento:**

    Agora, podemos prosseguir ao possuir um terminal rodando o *general* e um terminal com acesso aos elementos gráficos do host para viabilizar a visualização do Rviz (**Obs:** NÃO é preciso instalar Rviz no seu pc, nem ao menos ter uma versão específica de Ubuntu. O software será executado internamente à jetson que já o possui, usando apenas a tela do seu computador). Começamos o procedimento de mapeamento com o comando:

    ```bash
    roslaunch robot_navigation mapping.launch
    ```
    * O **Rviz** abrirá automaticamente na tela do seu computador.
    * Guie o robô pelo ambiente até que o mapa esteja completo e sem buracos pretos nas áreas transitáveis, garantindo o mínimo de imperfeições ao mover o robô lentamente. Para movimentá-lo, utilize o *teleop* ao abrir um terceiro terminal e rodar:

    ```bash
    rosrun teleop_twist_keyboard teleop_twist_keyboard.py
    ```


4.  **Salvar o Mapa:**
    Abra um novo terminal na Jetson e execute:
    ```bash
    roscd robot_navigation/maps
    rosrun map_server map_saver -f nome_do_mapa
    ```
    * Isso criará `nome_do_mapa.pgm` (imagem) e `nome_do_mapa.yaml` (metadados). Estes arquivos serão salvos na pasta [maps/](maps/) e só após isso é permitido finalizar o processo nos terminais do *mapping* e do *teleop*.

5.  **Refinar o Mapa:**
    Quando o mapa for completo, ele provavelmente possuirá imperfeições. Você deve corrigí-las manualmente usando o bom senso, colorindo a pgm gerada com algum software (ex: Gimp, que pode ser instalado via `sudo apt install gimp`). Utilize o mesmo tom escuro da pgm para barreiras e retire possíveis pontos pretos em zonas transitáveis que foram captados por erro. Salve o mapa editado também na mesma pasta com um nome identificável.

    > [!IMPORTANT]
    > Para garantir a funcionalidade do novo mapa, é preciso garantir que a nova pgm possua EXATAMENTE o mesmo tamanho e resolução da anterior, portanto, não altere isso. A escala das cores também é essencial para a interpretabilidade do mapa por parte do robô, garanta isso usando funções como conta gotas.

    Com o mapa pronto, é preciso editar o arquivo de metadados para referenciar a nova pgm, abra o `nome_do_mapa.yaml` e modifique a primeira linha para que fique de acordo.

    ```yaml
    image: nome_do_mapa_clean.pgm
    ...
    ```

---

### <a id="fase2"></a>Fase 2: Gravação de Pontos (Waypoints)
Define os locais de interesse (ex: "Base", "Entrega", "Recarga") no mapa salvo.

1.  **Iniciar Navegação:**
    Com o mapa corrigido já sendo referenciado pelo *yaml* gerado na etapa de mapeamento, é possível inicializar a navegação sobre este mapa. Para isso, é preciso editar a primeira linha no *launch* da navegação ([navigation.launch](launch/navigation.launch))

    ```launch
    <arg name="map_file" default="$(find robot_navigation)/maps/nome_do_mapa.yaml"/>
    ...
    ```
    Agora sim é possível executar o *Rviz* com a configuração da navegação. Lembrando que isto irá precisar da interface gráfica do host para executar, enão utilize o mesmo terminal que foi garantido este acesso feito para a etapa de *mapping*. Rode:

    ```bash
    roslaunch robot_navigation navigation.launch
    ```

2.  **Executar Script de Gravação:**
    O salvamento de pontos de interesse é automatizado utilizando um script desenvolvido. Em um terceiro terminal execute a linha abaixo. Este terminal ficará aguardando qualquer publicação feita pelo Nav Goal para salvar um novo *waypoint*.

    ```bash
    rosrun robot_navigation waypoint_saver.py
    ```

3.  **Marcar Pontos:**
    * Comece por verificar a posição do robô com relação ao mapa. Verifique se as linhas geradas pelo scan do lidar coincidem com as paredes do mapa. Até que a posição real (dada pelo Lidar) e a posição mapeada (verificada no Rviz) coincidam, utilize a função do **"Pose Estimate"**.
    * Após ter posicionado o robô, ainda no Rviz, use a ferramenta **"2D Nav Goal"** e clique no local desejado. Isto irá fazer o robô navegar até o ponto mas também irá possibilitar seu salvamento. Um procedimento comum é posicionar o robô na zona em que será o *Start* para começar este procedimento, portanto, o primeiro Nav Goal deve ser coincidente com a posição que o robô começou pelo Pose Estimate. 

    > [!TIP]
    > Para facilitar que você tenha um controle sobre onde está posicionando o robô, é bom que você entenda que ao escolher um ponto, você está definindo a origem do frame principal do robô que, neste projeto, está no base_footprint, localizado com o eixo z (para cima) colinear ao eixo do fuso do manipulador. Isso facilitará a definição da posição, devendo apenas orientar o robô conforme o desejado, sabendo que a seta do Nav Goal aponta para o x positivo (para frente do robô).

    * Se você tiver mantido o script para salvar os pontos rodando, assim que você definir uma nova posição a partir do Nav Goal, o terminal do script irá perguntar o nome do ponto. 
    * Digite o nome (ex: `WS1`) e dê Enter.
    > [!IMPORTANT]
    > Os scripts de navegação utilizados em conjunto com o scheduler consideram que o robô sempre é inicializado no Start. Logo, é importante que o primeiro ponto, configurado onde o robô será inicializado, tenha exatamente o nome "Start" e também é preciso que o `general.launch` obedecendo o scheduler seja executado apenas com o robô na posição de Start.

    * O ponto será salvo automaticamente em [`robot_scheduler/config/points.yaml`](../robot_scheduler/config/points.yaml).

---

### <a id="fase3"></a>Fase 3: Navegação Autônoma (Produção)
Modo padrão de operação onde o robô aceita comandos de outros nós. Ao executar o seguinte comando, ele sobe o mapa, a localização (AMCL), o planejador (Move Base) e o nó de integração ([`navigation.py`](scripts/navigation.py)).
```bash
roslaunch robot_navigation scheduler_nav.launch
```
> [!IMPORTANT] 
> **Nota:** O Rviz não abre automaticamente neste modo para economizar recursos e nnão há poluição dos logs. Este é um modo feito para ser executado via `general.launch` e para que ele não concorra com a execução dos launchs das etapas anteriores, é preciso que o *general* não esteja com ele sendo inicializado. Para isso, editar o [`general.launch`](../robot_utils/launch/general.launch):
    
```launch
...
<!-- Habilitação de Comandos via scheduler -->
<arg name="sched_navigation"      default="false"/>
...
```

Este mesmo argumento deve ser definido para `true` após ter concluído as etapas anteriores, matando o terminal de launch geral anterior para gerar um novo.

---

## <a id="tecnica"></a>4. Detalhes Técnicos da Navegação

### Planejador Local (DWA Planner)
Configurado em `planner_local_dwa.yaml`. Utilizamos o **Dynamic Window Approach** otimizado para robôs **Holonômicos**.

* **`holonomic_robot: true`**: Permite que o robô ande lateralmente (eixo Y) sem precisar girar.
* **`max_vel_x` / `max_vel_y`**: Definidos para **0.5 m/s** e **0.3 m/s** respectivamente.
* **`xy_goal_tolerance: 0.15`**: O robô considera que chegou se estiver dentro de um raio de **15cm** do alvo.

### Costmaps (Mapas de Custo)
O robô usa dois mapas para evitar colisões, configurados em [`costmap_common.yaml`](config/costmap_common.yaml).

1.  **Obstacle Layer (Camada de Obstáculos):**
    * Usa dados do Lidar (`/scan`).
    * **`obstacle_range: 2.5`**: Obstáculos detectados a menos de 2.5m são marcados como letais.
    * **`raytrace_range: 3.0`**: Se o laser passar livre por uma área anteriormente marcada, ela é limpa (obstáculo dinâmico saiu).

2.  **Inflation Layer (Camada de Inflação):**
    * Cria uma "zona de perigo" ao redor dos obstáculos.
    * **`inflation_radius: 0.5`**: Mantém o robô a pelo menos 50cm de distância das paredes para segurança, reduzindo a velocidade se precisar passar mais perto.

### Localização (AMCL)
O arquivo [`amcl_params.yaml`](config/amcl_params.yaml) configura o filtro de partículas probabilístico.
* **`odom_model_type: "omni-corrected"`**: Modelo de movimento específico para bases mecanum/omni, considerando o deslizamento lateral na odometria.

---

## <a id="scripts"></a>5. Scripts e Integração

### `navigation.py` (O Integrador)
Este nó atua como uma ponte entre o sistema de missões (`Scheduler`) e o sistema de movimento (`Move Base`).

* **Subscrição:** `/scheduler/commands` (Mensagens do tipo `SchedulerCommand`).
* **Publicação:** `/scheduler/feedback` (Status `OK` ou `FAIL`).
* **Arquivo de Pontos:** Carrega `points.yaml` do pacote `robot_scheduler`.
* **Lógica:**
    1.  Recebe um comando com um `uid` e um `payload` (nome do ponto, ex: "Estante_1").
    2.  Verifica se o ponto existe no YAML carregado.
    3.  Envia a coordenada para a Action Server do `move_base`.
    4.  Espera o robô chegar.
    5.  Retorna o status para o Scheduler liberar a próxima tarefa.

### `waypoint_saver.py` (Ferramenta de Configuração)
Facilita a criação do mapa de pontos sem precisar editar arquivos YAML manualmente.
* Converte cliques visuais no Rviz (`/move_base_simple/goal`) em coordenadas persistentes.

---

## <a id="troubleshooting"></a>6. Solução de Problemas Comuns

### "Waiting for transform" ou "TF Error" no Rviz
* **Causa:** O `robot_utils` não está rodando ou a odometria do microcontrolador parou.
* **Solução:** Reinicie o `general.launch` e verifique se o tópico `/odom` está sendo publicado (`rostopic hz /odom`).

### Robô gira mas não sai do lugar (Recovery Behavior)
* **Causa:** O robô está cercado por obstáculos no Costmap ou perdeu a localização.
* **Solução:**
    1.  Verifique no Rviz se há "manchas" (costmap inflado) bloqueando o robô.
    2.  Use o "2D Pose Estimate" para relocalizar o robô em uma área livre.
    3.  Verifique se o Lidar não está detectando partes do próprio robô (ajuste o `footprint` em `costmap_common.yaml`). Tmbém é possível realizar filtros na detecção do lidar para evitar captações errôneas, configurado no arquivo [`laser_filter.yaml`](../robot_utils/config/laser_filter.yaml).

### Erro: "Arquivo points.yaml não encontrado"
* **Causa:** O pacote `robot_scheduler` não está no workspace ou o arquivo não foi criado.
* **Solução:** Rode o `waypoint_saver.py` pelo menos uma vez para gerar a estrutura de arquivos inicial.

### X11 Forwarding lento ou falhando
* **Causa:** Rede Wi-Fi instável.
* **Solução:** Se o Rviz estiver muito lento via SSH, é possíve utilizar o Rviz no seu computador pessoal configurando as variáveis de rede:
```bash
# No PC Pessoal:
export ROS_MASTER_URI=http://192.168.1.100:11311
export ROS_IP=SEU_IP_DO_PC
rviz
```

Porém, acredito que é preferível ter paciência com o ssh mesmo, visto que esta etapa com o Rviz é apenas uma configuração inicial, feito no dia de aquecimento.