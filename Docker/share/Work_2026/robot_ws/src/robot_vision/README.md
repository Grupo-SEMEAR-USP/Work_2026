# Sistema de Visão Computacional (AprilTags)

![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-%235C3EE8.svg?style=for-the-badge&logo=opencv&logoColor=white)

Este pacote (`robot_vision`) é responsável pelo processamento de imagens e extração de informações do ambiente. Atualmente, seu foco principal é a detecção robusta de marcadores fiduciais **AprilTags** (família `tag36h11`), utilizados para localização de objetos manipuláveis ou re-localização do robô. Estas são as tags contídas nos arucos aplicados para a manipulação simplificada, como a feita na @Work Nacional 2025.

O sistema utiliza a biblioteca `pupil_apriltags` para alta performance em CPU, capaz de estimar a pose 3D (X, Y, Z e Orientação) de múltiplas tags simultaneamente, aplicando correções de escala automáticas baseadas no tamanho real da tag.

---

## Sumário

1. [Estrutura do Pacote](#estrutura)
2. [Pré-requisitos e Dependências](#pre-requisitos)
3. [Como Usar](#uso)
4. [Configuração de Tags](#configuracao)
5. [Detalhes Técnicos e Ajustes](#tecnica)

---

## <a id="estrutura"></a>1. Estrutura do Pacote

```text
robot_vision/
├── CMakeLists.txt              # Configuração de compilação
├── package.xml                 # Dependências ROS
├── config/                     
│   └── tags.yaml               # Banco de dados de tamanhos reais das tags
├── launch/                     
│   └── apriltag_detector.launch # Inicia o detector e carrega parâmetros
└── scripts/                    
    └── apriltag_detector.py    # Nó principal de processamento de imagem
```

---

## <a id="pre-requisitos"></a>2. Pré-requisitos e Dependências

### Hardware
* **Câmera USB:** Deve estar conectada e acessível pelo driver ROS (ex: `usb_cam`).
* **Calibração:** A câmera **deve** estar calibrada. O nó espera receber a matriz de calibração intrínseca pelo tópico `camera_info`. Sem isso, a estimativa de distância (Z) será incorreta.

### Software (Bibliotecas Python)
Este pacote depende de bibliotecas que não são instaladas automaticamente pelo `rosdep`. Na Jetson, foram instalados:

```bash
pip3 install pupil-apriltags
sudo apt-get install python3-opencv
```

---

## <a id="uso"></a>3. Como Usar

### 1. Iniciar o Driver da Câmera
Antes de rodar a visão, a câmera precisa estar publicando imagens. Isso é feito pelo `general.launch`, feito através da inicialização da câmera logitech.
*(Certifique-se que o tópico da imagem é `/usb_cam_logitech/image_raw` ou ajuste o argumento `camera_name` no launch da visão)*

### 2. Iniciar o Detector AprilTag
Essa detecção é feita através da inicialização do launch:

```bash
roslaunch robot_vision apriltag_detector.launch
```

Isso já está implementado e feito através do `general.launch`, contanto que este trecho esteja habilitado através das *flags* definidas nos argumentos iniciais.

### 3. Visualizar o Resultado
Para ver se as tags estão sendo detectadas (quadrado verde ao redor) e ler os IDs:
```bash
rqt_image_view
```
Selecione o tópico `/tag_detections_image`.

Isso deve ser possível através de um terminal que compartilhe a interface gráfica do host. Entretanto, todas as vezes em que verifiquei esta detecção foi vendo os dados numéricos (Posição X, Y, Z e ID da tag identificada):
```bash
rostopic echo /tag_detections
```

---

## <a id="configuracao"></a>4. Configuração de Tags (`tags.yaml`)

O sistema permite definir tamanhos físicos diferentes para cada ID de tag. Isso é crucial porque a distância é calculada baseada na relação entre o tamanho percebido em pixels e o tamanho real em metros. A configuração foi extraída através dos códigos antigos, testado com os arucos presentes na salinha, portanto, mudar apenas em necessidade. 

Edite o arquivo [`config/tags.yaml`](config/tags.yaml):

```yaml
standalone_tags:
  [
    {id: 1, size: 0.030, name: "cubo_pequeno"}, # 30mm
    {id: 2, size: 0.050, name: "base_dock"},    # 50mm
    ...
  ]
```

* **id:** O número da família `36h11` impresso na tag.
* **size:** O tamanho da aresta preta da tag em **metros**.
* **Lógica Interna:** O detector é inicializado com um `default_tag_size` (0.035m). Se o ID detectado estiver nesta lista com um tamanho diferente, o script aplica automaticamente um fator de escala na pose 3D. Isso evita ter que criar múltiplos detectores para tags de tamanhos variados.

---

## <a id="tecnica"></a>5. Detalhes Técnicos e Ajustes

### Parâmetro `tag_decimate`
Definido em [`launch/apriltag_detector.launch`](launch/apriltag_detector.launch):
```xml
<param name="tag_decimate" value="1.5" />
```
* **O que faz:** Reduz a resolução da imagem antes do processamento.
* **Valor Alto (ex: 2.0+):** Detecção muito mais rápida e maior alcance (detecta tags mais longe), mas perde precisão em tags muito pequenas ou próximas.
* **Valor Baixo (ex: 1.0):** Máxima precisão e estabilidade de pose, mas consome muito mais CPU e reduz a taxa de quadros (FPS).
* **Recomendação:** `1.5` é um bom ponto de equilíbrio para a capacidade de processamento da Jetson Nano.

> [!TIP]
> Este parâmetro é o melhor para a calibração. Como a maioria dos scripts feitos relacionados a detecção de arucos depende apenas de um callback, então estar captando em maiores distâncias tende a ser mais importante que a estabilidade. Mas é bom verificar o limite prático, pois esta camera tem um range bem limitado e se a instabilidade for demais, códigos como o de ajuste da garra podem ficar disfuncionais.

### Sistemas de Coordenadas
As poses publicadas seguem o padrão ótico do ROS:
* **Eixo Z:** Profundidade (distância da lente até a tag).
* **Eixo X:** Horizontal na imagem (direita).
* **Eixo Y:** Vertical na imagem (baixo).