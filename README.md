# Work_2026 - RMA

![Project](https://img.shields.io/badge/Project-RMA_2026-%23FF6F00?style=for-the-badge)
![ROS](https://img.shields.io/badge/ROS-Noetic-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)
![Docker](https://img.shields.io/badge/Environment-Docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Jetson_Nano-%2376B900.svg?style=for-the-badge&logo=nvidia&logoColor=white)

Este repositório (`Work_2026`) centraliza todo o ecossistema de desenvolvimento da equipe RMA para o projeto da RoboCup@Work 2026. Ele contém a infraestrutura de virtualização, os códigos embarcados de baixo nível e a aplicação de robótica de alto nível.

## Estrutura do Repositório

O projeto é dividido em três pilares principais. Clique nos links abaixo para navegar para a documentação específica de cada módulo:

1.  [**Ambiente Docker (`/Docker`)**](#docker)
    * Infraestrutura containerizada para desenvolvimento. **Opcional**, recomendada para quem não possui Ubuntu 20.04 nativo.
2.  [**Firmware Embarcado (`/firmware_esp`)**](#firmware)
    * Códigos para os microcontroladores ESP32 (Movimentação e Manipulação).
3.  [**ROS Workspace (`/robot_ws`)**](#robot_ws)
    * O "cérebro" do robô. Implementa o alto nível, realizando a manipulação, navegação e visão.

Além destes, na raiz do repositório encontram-se os arquivos `frames.gv` e `frames.pdf`, que documentam visualmente a árvore de transformadas (TF Tree) padrão do robô.

---
---

## <a id="docker"></a> Ambiente de Desenvolvimento (Docker)

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

Este diretório contém uma infraestrutura completa baseada em Docker para desenvolvimento com **ROS 1 Noetic**.

> [!NOTE]
> **Esta pasta é opcional.**
> Criada para possibilitar o desenvolvimento em versões distintas do Ubuntu. Se você já usa Ubuntu 20.04 com ROS Noetic, pode ignorar esta etapa. É apenas um conhecimento interessante que será compartilhado para auxiliar quem achar interessante

Para instruções de instalação e uso do container (VS Code integrado, GUI, etc), consulte o [README interno](Docker/README.md).

---
---

## <a id="firmware"></a> Firmware Embarcado (ESP32)

Esta seção contém os códigos para os dois subsistemas de hardware do robô, desenvolvidos em PlatformIO + ESP-IDF.

### [1. Firmware de Manipulação (`ESP_manip`)](firmware_esp/ESP_manip/)
Responsável pelo braço robótico (Steppers e Servos) e leitura dos sensores ultrassônicos. **[Ver Documentação de Manipulação](firmware_esp/ESP_manip/README.md)**

### [2. Firmware de Movimentação (`ESP_mov`)](firmware_esp/ESP_mov/)
Responsável pela locomoção (Ponte H, Encoders e PID). O mesmo código é utilizado nas placas Frontal e Traseira, diferenciadas por flag de software. **[Ver Documentação de Movimentação](firmware_esp/ESP_mov/README.md)**

---
---

## <a id="robot_ws"></a> ROS Workspace (`robot_ws`)

![ROS](https://img.shields.io/badge/ROS-Workspace-%2322314E.svg?style=for-the-badge&logo=ros&logoColor=white)

Este é o diretório principal da aplicação. Aqui residem os pacotes de Navegação, Visão Computacional, Tarefas Modularizadas (Scheduler) e Drivers.

Para o guia completo de **instalação, compilação (catkin), acesso SSH e fluxo de operação**, acesse a **[documentação dedicada](robot_ws/README.md)**.

### Credenciais Rápidas

Caso precise apenas conectar rapidamente ao robô:

* **Rede Wi-Fi:** `atenaopen2023` (Senha: `rrrmmmaaa`)

| Dispositivo | IP | Usuário | Senha |
| :--- | :--- | :--- | :--- |
| **Jetson Nano** | `192.168.1.100` | `rmajetson` | `rmajetson` |
| **Raspberry Pi** | `192.168.1.101` | `ubuntu` | `rmarasp` |

**Comando de Acesso:**
```bash
ssh rmajetson@192.168.1.100
```