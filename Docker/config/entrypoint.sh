#!/bin/bash
set -e

# Detecta o comando final (primeiro argumento)
CMD="$1"

# Detecta tipo de shell a ser iniciado
detect_shell_type() {
  case "$1" in
    zsh|*/zsh)
      echo "zsh"
      ;;
    bash|*/bash)
      echo "bash"
      ;;
    *)
      # Fallback para SHELL ou bash
      if [[ -n "$SHELL" ]]; then
        basename "$SHELL"
      else
        echo "bash"
      fi
      ;;
  esac
}

SHELL_TYPE="$(detect_shell_type "$CMD")"

# Configuração do mosquitto
sudo -E -b -u mosquitto /usr/sbin/mosquitto -c /etc/mosquitto/mosquitto.conf
sleep 2

# Verifica se o setup do ROS existe
ROS_SETUP="/opt/ros/noetic/setup.${SHELL_TYPE}"
[[ -f "$ROS_SETUP" ]] || echo "[Entrypoint] ⚠️ Setup ROS não encontrado em $ROS_SETUP"

# Pega o comando do "CMD" do Dockerfile (ex: "zsh")
CMD="$1"

# Se o comando for zsh ou bash, executa como um shell de login
# para garantir que .zshrc/.bashrc/.profile sejam carregados.
if [[ "$CMD" == "zsh" || "$CMD" == "/bin/zsh" ]]; then
    # Executa 'zsh -l' (login shell) como rosUsr
    exec sudo -E -u rosUsr /bin/zsh -l

elif [[ "$CMD" == "bash" || "$CMD" == "/bin/bash" ]]; then
    # Executa 'bash --login' (login shell) como rosUsr
    exec sudo -E -u rosUsr /bin/bash --login

else
    # Se for qualquer outro comando
    # executa-o diretamente como rosUsr
    exec sudo -E -u rosUsr "$@"
fi