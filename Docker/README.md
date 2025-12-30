# Ambiente de Desenvolvimento ROS Noetic (Docker)

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![ROS](https://img.shields.io/badge/ros-%230A0FF9.svg?style=for-the-badge&logo=ros&logoColor=white)
![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)

Este repositório contém uma infraestrutura completa baseada em Docker para desenvolvimento com **ROS 1 Noetic**. O ambiente é totalmente containerizado, suportando interface gráfica (GUI), terminal personalizado (Zsh + Powerlevel10k), VS Code integrado e comunicação MQTT.

---

## Sumário

1. [Pré-requisitos](#pre-requisitos)
2. [Estrutura do Projeto](#estrutura)
3. [Configuração Inicial](#config-inicial)
4. [Como Usar](#como-usar)
5. [Fluxo de Trabalho e Arquivos](#fluxo)
6. [Personalização](#personalizacao)

---

## <a id="pre-requisitos"></a>1. Pré-requisitos

Antes de iniciar, você precisa ter o **Docker Engine** e o **Docker Compose** instalados na sua máquina host (Ubuntu/Linux).

### Instalação do Docker
Se você ainda não possui o Docker instalado, execute os comandos abaixo no seu terminal:

```bash
# 1. Atualize os pacotes e instale dependências
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg

# 2. Adicione a chave GPG oficial do Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL [https://download.docker.com/linux/ubuntu/gpg](https://download.docker.com/linux/ubuntu/gpg) | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Configure o repositório
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] [https://download.docker.com/linux/ubuntu](https://download.docker.com/linux/ubuntu) \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Instale o Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Adicione seu usuário ao grupo do Docker (para não precisar usar sudo sempre)
sudo usermod -aG docker $USER
newgrp docker
```

> [!IMPORTANT]
> Após adicionar seu usuário ao grupo `docker`, é necessário realizar o logout e login para garantir que as permissões sejam aplicadas corretamente.

---

## <a id="estrutura"></a>2. Estrutura do Projeto

Abaixo, a descrição detalhada de cada componente deste ambiente:

```text
Docker/
├── config/               # Arquivos de configuração injetados no container
│   ├── bashrc            # Configurações para Shell Bash
│   ├── zshrc             # Configurações para Shell Zsh
│   ├── p10k.zsh          # Tema visual do terminal (Powerlevel10k)
│   └── mosquitto.conf    # Configuração do broker MQTT
├── send/                 # Pasta de envio UNILATERAL (Host -> Container)
├── share/                # Pasta de sincronização BILATERAL (Host <-> Container)
├── docker-compose.yml    # Orquestrador do container
├── Dockerfile            # Receita de construção da imagem
├── entrypoint.sh         # Script mestre de inicialização (não apagar!)
└── .env                  # Variáveis de ambiente e configuração de caminhos
```

### Detalhes dos Arquivos de Configuração (`config/`)
* **[`config/bashrc`](config/bashrc) & [`config/zshrc`](config/zshrc)**: Scripts que rodam ao abrir o terminal. Já configuram o ambiente ROS (`source /opt/ros/noetic/setup.bash`), aliases úteis e o workspace do robô.

> [!IMPORTANT]
> **Configuração do Workspace do Robô**
>
> Dentro de [`config/bashrc`](config/bashrc) e [`config/zshrc`](config/zshrc), existe uma linha de comando `source` que carrega o workspace do seu projeto (ex: `source ~/Shared/Nome_Do_Projeto/devel/setup.bash`).
>
> **Você deve editar essa linha em ambos os arquivos** para que ela aponte corretamente para a pasta do seu projeto ROS que está dentro de [`share/`](share/). Se o nome da pasta mudar, atualize aqui, ou o terminal não reconhecerá seus pacotes customizados.

* **[`config/p10k.zsh`](config/p10k.zsh)**: Arquivo de estilo do terminal, garantindo ícones, status do Git e informações de sistema visualmente agradáveis.
* **[`entrypoint.sh`](entrypoint.sh)**: Script crítico que define o usuário correto (`rosUsr`) e prepara o ambiente antes de te entregar o controle do terminal.
* **[`config/mosquitto.conf`](config/mosquitto.conf)**: Configura o broker MQTT para permitir conexões anônimas e externas na porta 1883.

---

## <a id="config-inicial"></a>3. Configuração Inicial

Antes de rodar o container pela primeira vez, você **deve** configurar o caminho do projeto.

### 1. Definindo o `DPATH`
O arquivo [`.env`](.env) controla as variáveis fundamentais. A variável `DPATH` deve apontar para o **caminho absoluto** desta pasta no seu computador.

1.  Abra um terminal dentro desta pasta (`Docker`).
2.  Digite o comando abaixo para descobrir o caminho atual:
    ```bash
    pwd
    ```
3.  Copie o resultado (ex: `/home/seu_usuario/Projetos/Docker`). *obs: Para copiar em terminal, usar `Ctrl`+`Shift`+`C`*
4.  Abra o arquivo [`.env`](.env) e cole na variável `DPATH`:

```bash
# .env
DPATH=/home/seu_usuario/caminho/completo/ate/a/pasta/Docker
```

### 2. Outras Variáveis no `.env`
Você pode alterar os nomes conforme sua preferência, mas cuidado para não gerar conflitos se tiver múltiplos projetos.

| Variável | Descrição | Exemplo |
| :--- | :--- | :--- |
| `CNAME` | Nome do Container (deve ser único no sistema) | `WORK_2026` |
| `INAME` | Nome da Imagem Docker criada | `ros_noetic` |
| `DOCKER_USER` | Usuário interno do container | `rosUsr` |

---

## <a id="como-usar"></a>4. Como Usar

### 1. Habilitar Interface Gráfica (X11)
Para que ferramentas como **Rviz** e **Gazebo** abram janelas no seu monitor, execute este comando no host (necessário a cada reinicialização do PC):

```bash
xhost +
```

Esta é a maneira permissiva e mais simples de ser executada, porém, caso tenha garantia do grupo configurado para o docker, uma alternativa mais segura seria definir esta permissão apenas para o grupo necessário. (A não ser que se preocupe muito com isso, recomendo o primeiro método)

```bash
xhost +local:docker
```

### 2. Construir e Iniciar
Este comando baixa as dependências, constrói a imagem e inicia o container. Destacando que a utilização de todos os comandos `docker compose` exigem que esteja com o terminal na raiz desta pasta.

```bash
docker compose up -d --build
```

### 3. Acessar o Terminal
Para começar, é preciso ter noção que na execução do comando anterior para a construção do ambiente, foi utilizado a *flag* `-d` que mantém uma execução em segundo plano até que o sistema seja reinicializado, portanto, enquanto o sistema não for reiniciado, é como se existisse um terminal rodando paralelamente.

Existem alternativas para entrar no ambiente de desenvolvimento. Citando inicialmente as possibilidades que usam do *compose*, lembrando que estes possuem a limitação de serem executados apenas quando o terminal foi navegado até a pasta raiz da criação desta imagem (ao lado do [`docker-compose.yml`](docker-compose.yml)). Quando for abrir um terminal que não o primeiro, é possível executar:

```bash
docker compose exec ros_noetic zsh
```

Caso seja o primeiro terminal a ser aberto, sem nenhum processo rodando de fundo, utiliza-se:

```bash
docker compose start ros_noetic
```

> **Obs:** O nome `ros_noetic` é o nome do serviço definido no [`docker-compose.yml`](docker-compose.yml). Você pode abrir múltiplos terminais rodando esse mesmo comando.

Partindo para as alternativas sem o *compose*, sendo estas mais versáteis, utilizando o nome do contâiner (que é único) ao invés do serviço, sendo estas indicadas para uso. Temos, a princípio, a alternativa para inicializar o primeiro terminal:

```bash
docker start -i WORK_2026
```

Em demais terminais, deve ser executado:

```bash
docker exec -it WORK_2026 zsh
```

### 4. Parar o Ambiente
Para desligar o container e liberar recursos:

```bash
# Para apenas o container (mantém os dados)
docker compose stop

# Para e remove o container, apagando as imagens associadas 
docker compose down --rmi all
```

---

## <a id="fluxo"></a>5. Fluxo de Trabalho e Arquivos

O ambiente possui duas pastas especiais para troca de arquivos entre seu computador (Host) e o Container.

### Pasta [`share/`](share/) (Mapeada como `~/Shared`)
* **Tipo:** Sincronização Bilateral (Leitura e Escrita).
* **Uso:** É aqui que seu código fonte, workspaces (`catkin_ws`, `robot_ws`) e projetos devem ficar.
* **Comportamento:**
    * Se você criar um arquivo aqui no Host, ele aparece no Container.
    * Se você criar no Container, ele aparece no Host.
    * **Ideal para:** Desenvolvimento contínuo.

### Pasta [`send/`](send/) (Mapeada como `~/Sent`)
* **Tipo:** Cópia Unilateral (Host -> Container).
* **Uso:** Arquivos que você quer "injetar" no container, mas quer proteger os originais contra modificações acidentais ou corrupção por parte do container.
* **Comportamento:** O Docker copia o conteúdo desta pasta para dentro do container apenas durante o processo de *Build* da imagem.
* **Atenção:** Alterações feitas dentro do container nesta pasta **NÃO** são salvas de volta no seu computador.

---

## <a id="personalizacao"></a>6. Personalização

### VS Code
O container já vem com o VS Code instalado. Para abri-lo de dentro do container com suporte a interface gráfica, usualmente deveria ter que utilizar:

```bash
code --no-sandbox .
```

Porém, no [`Dockerfile`](Dockerfile) já é feito uma abordagem capaz de possibilitar o uso do comando com a sintaxe original:

```bash
code .
```

### Terminal
O terminal padrão é o **Zsh** com o tema **Powerlevel10k**. Se quiser alterar as configurações visuais, você pode editar o arquivo [`config/p10k.zsh`](config/p10k.zsh) no host e reconstruir o container, ou rodar `p10k configure` dentro do container (lembrando que alterações manuais dentro do container serão perdidas se o container for recriado, a menos que você copie o arquivo `.p10k.zsh` gerado de volta para a pasta [`config/`](config/)).

---

> [!NOTE]
> **Solução de Problemas Comuns:**
> * **Erro de Permissão (Display):** Se janelas não abrirem, verifique se rodou `xhost +`.