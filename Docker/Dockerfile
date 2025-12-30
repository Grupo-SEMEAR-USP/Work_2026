# Imagem base para ROS 1 Noetic, que usa Ubuntu 20.04 (Focal)
FROM osrf/ros:noetic-desktop-full

ARG USERNAME
ARG USER_UID
ARG USER_GID

# Cria usuário e estrutura inicial
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && mkdir /home/$USERNAME/.config \
    && chown $USER_UID:$USER_GID /home/$USERNAME/.config

# Correção do ROS
## Encontra e apaga TODAS as listas de repositórios em /etc/apt/sources.list.d/
RUN find /etc/apt/sources.list.d/ -type f -name "*.list" -delete

## Atualiza a lista de pacotes e instala as ferramentas necessárias.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    lsb-release

## Adiciona a chave GPG correta e recria o arquivo do repositório ROS.
RUN mkdir -p /etc/apt/keyrings \
    && curl -sSL 'http://keyserver.ubuntu.com/pks/lookup?op=get&search=0xF42ED6FBAB17C654' \
    | gpg --dearmor -o /etc/apt/keyrings/ros-noetic-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-noetic-keyring.gpg] http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list

# Agora, com o repositório corrigido, atualiza e instala tudo de uma vez
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99retries

RUN apt-get update && apt-get install -y --no-install-recommends \
    adwaita-icon-theme \
    dbus-x11 \
    fontconfig \
    gvfs-backends \
    nautilus \
    git \
    nano \
    unzip \
    wget \
    zsh \
    # Para rede
    openssh-client \
    nmap \
    iproute2 \
    mosquitto \
    mosquitto-clients \
    # Ferramentas de desenvolvimento padrão do ROS 1
    build-essential \
    python3-paho-mqtt \ 
    python3-pip \
    python3-argcomplete \
    python3-rosdep \
    python3-rosinstall \
    python3-rosinstall-generator \
    python3-wstool \
    ros-noetic-catkin \
    python3-catkin-tools \
    # Dependências para VSCode e GUI
    ca-certificates \
    libasound2 \
    libfontconfig1 \
    libgtk-3-0 \
    libnss3 \
    libx11-xcb1 \
    libxss1 \
    sudo \
    libxkbfile1 \
    xdg-utils \
    libsecret-1-0 \
    gnome-icon-theme \
    gnome-themes-extra \
    libcanberra-gtk3-module \
    libcanberra-gtk-module \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i 's|log_dest file /var/log/mosquitto/mosquitto.log|log_dest stdout|' /etc/mosquitto/mosquitto.conf \
    && sed -i 's|persistence true|persistence false|' /etc/mosquitto/mosquitto.conf

# Permite uso do sudo pelo usuário
RUN echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Atualiza pip
RUN python3 -m pip install --upgrade pip

# Instala o VSCode manualmente
RUN wget -qO /tmp/code.deb "https://code.visualstudio.com/sha/download?build=stable&os=linux-deb-x64" \
    && apt-get update \
    && apt-get install -y --no-install-recommends gdebi-core \
    && DEBIAN_FRONTEND=noninteractive gdebi -n /tmp/code.deb \
    && rm /tmp/code.deb \
    && rm -rf /var/lib/apt/lists/*

# Adiciona alias para usar "code" com --no-sandbox
RUN echo 'alias code="code --no-sandbox"' >> /etc/zsh/zshrc \
    && echo 'alias code="code --no-sandbox"' >> /etc/bash.bashrc

# Instala Oh My Zsh e Powerlevel10k
USER $USERNAME
WORKDIR /home/$USERNAME

RUN git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git .oh-my-zsh \
    && git clone --depth=1 https://github.com/romkatv/powerlevel10k.git .oh-my-zsh/custom/themes/powerlevel10k

# Instala fontes MesloLGS NF
USER $USERNAME
WORKDIR /home/$USERNAME
RUN mkdir -p ~/.local/share/fonts && \
    git clone --depth=1 https://github.com/romkatv/powerlevel10k-media.git /tmp/p10k_media && \
    cp /tmp/p10k_media/*.ttf ~/.local/share/fonts/ && \
    rm -rf /tmp/p10k_media && \
    fc-cache -f -v

# Volta para root para copiar arquivos de configuração
USER root
COPY --chown=root:root config/mosquitto.conf /etc/mosquitto/conf.d/default.conf
COPY --chown=$USERNAME:$USERNAME config/zshrc /home/$USERNAME/.zshrc
COPY --chown=$USERNAME:$USERNAME config/p10k.zsh /home/$USERNAME/.p10k.zsh
COPY --chown=$USERNAME:$USERNAME config/bashrc /home/$USERNAME/.bashrc
COPY --chown=$USERNAME:$USERNAME send /home/$USERNAME/Sent
COPY config/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

# Define shell padrão
RUN chsh -s /bin/zsh $USERNAME

ENTRYPOINT ["/entrypoint.sh"]
CMD ["zsh"]