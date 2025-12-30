#!/bin/bash          
# Argumentos: [segundos] [pacote] [arquivo_launch] [argumentos_extras...]

DELAY=$1
PKG=$2
FILE=$3
shift 3
ARGS=$@

echo ">>> AGUARDANDO $DELAY SEGUNDOS PARA INICIAR $PKG/$FILE..."
sleep $DELAY

echo ">>> INICIANDO $PKG/$FILE AGORA!"
roslaunch $PKG $FILE $ARGS