# Descrição e Modelagem do Robô (URDF)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![URDF](https://img.shields.io/badge/URDF-XML-%23FF6F00.svg?style=for-the-badge&logo=xml&logoColor=white)
![Meshes](https://img.shields.io/badge/CAD-SolidWorks-%23D32D41.svg?style=for-the-badge&logo=dassaultsystemes&logoColor=white)

Este pacote (`robot_description`) contém a representação digital completa do robô. Ele define a geometria física (links), as conexões mecânicas (joints), os limites de movimento e a aparência visual (meshes) utilizando o formato **URDF** (Unified Robot Description Format).

Este pacote é fundamental para todo o sistema ROS, pois é ele quem "ensina" ao computador onde está cada sensor em relação ao centro do robô (Árvore de Transformadas - TF), permitindo que o Lidar e a Câmera funcionem corretamente na navegação.

---

## Sumário

1. [Estrutura do Pacote](#estrutura)
2. [Entendendo o Modelo (URDF)](#modelo)
3. [Como Usar (Launch Files)](#uso)
4. [Árvore de Transformadas (TF Tree)](#tf)

---

## <a id="estrutura"></a>1. Estrutura do Pacote

```text
robot_description/
├── CMakeLists.txt              # Configuração de compilação
├── package.xml                 # Dependências
├── config/                     # Configurações de controladores de juntas
│   └── joint_names_robot_description.yaml
├── launch/                     # Arquivos de inicialização
│   ├── display.launch          # Visualização isolada (Rviz + GUI)
│   ├── gazebo.launch           # Simulação física no Gazebo
│   └── real_robot_description.launch # Para rodar no robô real
├── meshes/                     # Modelos 3D (.STL) exportados do CAD
│   ├── base_link.STL
│   ├── lidar_link.STL
│   └── ... (outros links)
└── urdf/                       # O arquivo descritivo principal
    └── robot_description.urdf
```

---

## <a id="modelo"></a>2. Entendendo o Modelo (URDF)

O arquivo [`urdf/robot_description.urdf`](urdf/robot_description.urdf) foi gerado a partir do **SolidWorks** e descreve a hierarquia cinemática do robô.

### Frames Principais
* **`base_footprint`**: É o frame "pai" de todos. Ele representa a projeção do robô no chão (Z=0). Este foi um frame criado manualmente para que a referencia inicial não possua inércia, foi posicionado como uma cópria do `base_link`, porém posicionado no chão. 
    * *Nota de Design:* O eixo Z deste frame é **coaxial** (alinhado) ao fuso central do manipulador. Isso facilita o posicionamento do robô em mapas, pois o centro de giro é previsível.
* **`base_link`**: Representa o chassi físico do robô. Está elevado **14.4 cm** (`z=0.144`) em relação ao chão.
* **`laser`**: Representa o sensor Lidar. Note que no URDF ele possui uma rotação de 180° (`yaw=3.14159`), indicando a montagem física do sensor, que está de ponta cabeça.
* **`camera_link`**: Representa a câmera RealSense, posicionada com uma leve inclinação (`pitch=~10°`) para ver o chão à frente.

### Juntas Móveis (Manipulador)
O robô possui um braço manipulador integrado descrito pelas seguintes juntas:
1.  **`plat_joint` (Revolute):** Rotação da base do braço.
2.  **`manip_joint` (Prismatic):** Movimento linear vertical (Elevador).
3.  **`pulso_joint` (Revolute):** Rotação do efetuador final.
4.  **`garra1_joint` / `garra2_joint` (Prismatic):** Abertura e fechamento da garra.

---

## <a id="uso"></a>3. Como Usar (Launch Files)

Este pacote oferece três modos de operação principais:

### A. Visualização e Teste (`display.launch`)
Este launch é utilizado para verificar a integridade do modelo URDF e testar os limites das juntas manualmente.

```bash
roslaunch robot_description display.launch
```
* **Requisito:** Exige interface gráfica. Se estiver rodando na Jetson, certifique-se de ter conectado via `ssh -X`.
* **O que acontece:** Abre o Rviz e uma pequena janela chamada "Joint State Publisher GUI".
* **Teste:** Mova os sliders na janelinha GUI. Você verá o braço do robô se mexer no Rviz. Isso confirma que os limites das juntas e as conexões pais-filhos estão corretos.

> [!TIP]
> Outra forma de validar o urdf é por meio da execução do [`navigation.launch`](../robot_navigation/launch/navigation.launch), onde será possível visualizar também a posição dos *scans* do lidar, verificando se não está configurado rotacionado em relação à posição real. Esta normalmente foi a que mais usei, medindo a posição dos elementos no [URDF](urdf/robot_description.urdf) e verificando como ficavam no Rviz ao rodar a navegação conforme descrito no [`robot_navigation`](../robot_navigation/README.md).

### B. Operação no Robô Real (`real_robot_description.launch`)
Este é o launch que deve ser incluído pelo `general.launch` ou rodado na Jetson durante a operação real.

```bash
roslaunch robot_description real_robot_description.launch
```
* **Diferença:** Ele **não** abre o Rviz e **não** abre a GUI de sliders.
* **Função:** Ele apenas carrega o URDF no Parameter Server e inicia o `robot_state_publisher`, que fica aguardando dados reais dos motores (via tópicos de *joint_states*) para atualizar a posição do braço no TF.

### C. Simulação (`gazebo.launch`)
Carrega o robô em um mundo vazio no simulador Gazebo, spawnando o modelo físico com gravidade e inércia.

```bash
roslaunch robot_description gazebo.launch
```

---

## <a id="tf"></a>4. Árvore de Transformadas (TF Tree)

O pacote utiliza dois nós essenciais do ROS para manter a coerência espacial do robô:

1.  **`joint_state_publisher`**:
    * Lê a posição dos motores (encoders).
    * Publica no tópico `/joint_states` um vetor com o ângulo/posição atual de cada junta (`plat_joint`, `manip_joint`, etc).
    
2.  **`robot_state_publisher`**:
    * Ouve o `/joint_states`.
    * Lê o arquivo URDF.
    * **Calcula a matemática:** "Se a base está girada 30 graus e o elevador subiu 10cm, onde está a câmera agora?".
    * Publica o resultado no `/tf` e `/tf_static`.

> [!TIP]
> **Debug de TF:** Se ao abrir o Rviz o robô aparecer "desmontado" (todas as peças amontoadas no chão no ponto 0,0,0) ou branco, significa que o `robot_state_publisher` não está rodando ou não recebeu o URDF corretamente. Verifique se o parâmetro `robot_description` foi carregado corretamente com `rosparam get /robot_description`.

### Validação da Integridade da Árvore

Para garantir que o robô foi montado corretamente pelo software, é vital verificar se a árvore de transformadas (TF Tree) é contínua. Uma árvore saudável deve ter uma única raiz (`base_footprint` ou `map`) e não pode ter "ilhas" (nós desconectados) ou nós com múltiplos pais.

Para gerar o diagrama da árvore atual, execute com o robô rodando:

```bash
rosrun tf view_frames
```

Este comando gera um arquivo `frames.pdf` no diretório atual. Verifique se:

1. Todos os links (`base_link`, `laser`, etc.) estão presentes.

2. Existe uma cadeia contínua ligando todos eles.

3. A média de publicação dos links estáticos é ~10.000Hz (Latch) e dos dinâmicos conforme configurado.

Isto já foi executado neste projeto em sua forma inicial, gerando os resultados vistos em [`frames.pdf`](../../../frames.pdf).