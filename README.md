# Documentação e Contexto de Desenvolvimento — Projeto STAM

## 1. Visão Geral
- **Projeto:** STAM (Sistema de Transporte Autônomo de Medicamentos)
- **Objetivo:** Robô móvel para entrega de medicamentos em ambiente hospitalar.

---

## 2. Arquitetura de Hardware (Modular)
- **Base de Locomoção:** Plataforma de hoverboard modificada (firmware EFeru `VARIANT_USART`).
- **Processamento de Alto Nível (SBC):** Orange Pi 4 Pro (`aarch64`, hostname `orangepi4pro`).
- **Controle de Baixo Nível de Locomoção (MCU 1):** **ESP32 dedicado exclusivamente ao controle da placa-mãe do Hoverboard** (e possivelmente uma **IMU** no futuro), garantindo tempo real determinístico sem bloqueios de outros sensores.
- **Sensores e Periféricos:**
  - **Câmera USB:** **Logitech HD Pro Webcam C920** (USB ID `046d:08e5`, mapeada em `/dev/video0` e `/dev/video1`), conectada diretamente à porta USB da **Orange Pi 4 Pro**. Utilizada inicialmente para **teleoperação** e futuramente para visão computacional.
  - **Demais Sensores (Arquitetura em Definição):**
    - Módulos de seguimento de linha (*line-following*)
    - Leitores e tags RFID para localização e checkpoints hospitalares
    - Sensores ultrassônicos para detecção de obstáculos
    - *(Nota de Arquitetura: Estes sensores ficarão em um **segundo ESP32 dedicado a sensores** ou conectados diretamente aos pinos GPIO/I2C/SPI da **Orange Pi 4 Pro**, mantendo o ESP32 dos motores isolado).*

---

## 3. Arquitetura de Software e Middleware (ROS 2 Humble)
- **Framework Principal:** ROS 2 Humble (instalado tanto na Orange Pi 4 Pro quanto no PC de desenvolvimento).
- **Dinâmica de Integração Distribuída (DDS + Ponte Serial):**
  - **Orange Pi 4 Pro (Alto Nível):** Gerencia a inteligência, navegação, controle de missão e os nós do ROS 2 no robô (`stam_camera` para vídeo e `stam_base` para comunicação via USB Serial com o ESP32 dos motores).
  - **ESP32 de Locomoção (Baixo Nível — Ponte Serial em C++):** Mantém o loop de 20 Hz do protocolo binário EFeru (`USART2`), watchdog de segurança de 500 ms e envio de telemetria para a Orange Pi via USB Serial (`115200 bps`).
  - **PC / Estação Base:** Participa nativamente da mesma rede ROS 2 através do middleware **DDS (Data Distribution Service)**. Nós de visualização (`rqt_image_view`) e teleoperação pelas setas (`stam-teleop`) rodam no PC e publicam/assinam tópicos diretamente com a Orange Pi 4 Pro pela rede.

---

## 4. Ambiente de Rede e Acesso SSH
- **Conexão Física Direta (Ponto a Ponto via Ethernet):**
  - **PC (Gateway / NAT / Servidor DHCP):** Interface `enx207bd232c0f6` (`Wired connection 1` em modo `ipv4.method shared`), IP estático **`192.168.10.1/24`**. Compartilha a conexão de internet Wi-Fi com a Orange Pi.
  - **Orange Pi 4 Pro:** Interface `eth0` (MAC `e8:eb:0a:22:bd:d1`), IP estático **`192.168.10.2/24`**, Gateway e DNS apontando para `192.168.10.1`.
  - **IPv6 Link-Local (contingência):** `fe80::91eb:6389:b2fb:ecda%enx207bd232c0f6`
- **Acesso SSH:**
  - Configurado em [`~/.ssh/config`](file:///home/lucas/.ssh/config) com autenticação por chave pública (`~/.ssh/id_ed25519`, sem necessidade de senha):
    ```bash
    ssh orangepi
    ```

---

## 5. Workspace ROS 2 na Orange Pi 4 Pro (`~/stam_ws`)

O workspace `~/stam_ws` já está configurado no `~/.bashrc` da Orange Pi 4 Pro e contém dois pacotes principais:

### 5.1. Pacote da Câmera (`stam_camera`)
- **Caminho:** `~/stam_ws/src/stam_camera`
- **Nó Principal:** `camera_node` (`stam_camera/camera_node.py`)
- **Launch File:** `camera.launch.py`
- **Funcionamento:**
  - Configura a **Logitech C920** em modo **MJPEG** via V4L2 (`640x480` @ `15 FPS` por padrão).
  - **Economia inteligente (`get_subscription_count()`):** Só captura/codifica frames quando há pelo menos 1 assinante conectado.
  - **Tópicos publicados:**
    - `/stam/camera/image_raw/compressed` (`sensor_msgs/msg/CompressedImage`)
    - `/stam/camera/image_raw` (`sensor_msgs/msg/Image`)

### 5.2. Pacote de Controle de Locomoção (`stam_base`)
- **Caminho:** `~/stam_ws/src/stam_base`
- **Nó Principal:** `hoverboard_bridge_node` (`stam_base/hoverboard_bridge_node.py`)
- **Launch Files:**
  - `base.launch.py` (inicia apenas a ponte com o ESP32 dos motores)
  - `teleop_robot.launch.py` (inicia **Câmera + Base de Motores** simultaneamente)
- **Funcionamento:**
  - Detecta e reconecta automaticamente ao ESP32 em `/dev/ttyACM*` ou `/dev/ttyUSB*` (`115200 bps`).
  - **Tópico assinado:**
    - **`/cmd_vel`** (`geometry_msgs/msg/Twist`): Converte `linear.x` (m/s) e `angular.z` (rad/s) em comandos `V <speed> <steer>` enviados a 20 Hz para o ESP32. Possui timeout de segurança de 0,5 s.
  - **Tópicos publicados:**
    - **`/stam/base/wheel_rpm`** (`std_msgs/msg/Int32MultiArray`): `[rpm_direita, rpm_esquerda]`
    - **`/stam/base/battery_voltage`** (`std_msgs/msg/Float32`): Tensão da bateria do Hoverboard (V)
    - **`/stam/base/status`** (`std_msgs/msg/String`): Linha bruta de retorno do ESP32

---

## 6. Controle de Motores: ESP32 + Hoverboard (Firmware EFeru `VARIANT_USART`)

### 6.1. Especificações da Placa do Hoverboard
- **Firmware na placa-mãe do Hoverboard:** EFeru (`hoverboard-firmware-hack-FOC`) em modo **`VARIANT_USART`**.
- **Porta utilizada:** **Lado Esquerdo (`USART2`)** — pinos `PA2` (`TX2`) e `PA3` (`RX2`), lógica nativa de **3.3V** @ **`115200 bps`**.

### 6.2. Ligações Físicas (ESP32 de Locomoção $\leftrightarrow$ Hoverboard)
| Pino no ESP32 | Função no ESP32 | Pino no Hoverboard (Cabo Esquerdo `USART2`) | Observação Importante |
| :--- | :--- | :--- | :--- |
| **`GPIO 17`** | `TX2` (`Serial2 TX`) | **`PA3` (`RX2`)** — geralmente fio Verde | Cruzado (`TX` $\rightarrow$ `RX`) |
| **`GPIO 16`** | `RX2` (`Serial2 RX`) | **`PA2` (`TX2`)** — geralmente fio Azul | Cruzado (`RX` $\rightarrow$ `TX`) |
| **`GND`** | Terra | **`GND`** — fio Preto | **Obrigatório** compartilhar o GND |
| *(Não conectar)* | — | **`+12V / +15V`** — fio Vermelho | **PERIGO:** Isolar! Nunca ligar direto no ESP32 |

### 6.3. Ambiente Arduino IDE e Sketch do ESP32 no PC
- **Arduino IDE 2.3.10:** Instalado em `~/.local/opt/arduino-ide` (atalho de terminal `arduino-ide`, URL da Espressif configurada em [`~/.arduinoIDE/arduino-cli.yaml`](file:///home/lucas/.arduinoIDE/arduino-cli.yaml)).
- **Permissão USB Serial no PC:** Usuário `lucas` adicionado ao grupo `dialout` (porta do ESP32 mapeada como `/dev/ttyACM0`).
- **Arquivo do Sketch:** [`~/Arduino/stam_esp32_hoverboard/stam_esp32_hoverboard.ino`](file:///home/lucas/Arduino/stam_esp32_hoverboard/stam_esp32_hoverboard.ino)
- **Comandos aceitos pelo ESP32 via USB Serial (`115200 bps`):**
  - `V <speed> <steer>` — Define velocidade (`-1000` a `1000`) e direção (`-1000` a `1000`).
  - `S` — Parada imediata de emergência (`speed = 0`, `steer = 0`).
  - `W 0` / `W 1` — Desativa (`W 0`, teste manual) ou ativa (`W 1`, padrão ROS 2) o watchdog de 500 ms.

---

## 7. Ferramentas no PC (`stam-teleop` e `stam-monitor`)

### 7.1. Teleoperação pelas Setas (`stam-teleop`)
- **Script Executável:** [`~/.local/bin/stam-teleop`](file:///home/lucas/.local/bin/stam-teleop)
- **Funcionamento:** Nó ROS 2 em Python (`stam_arrow_teleop`) com leitura direta via descritor de arquivo (`os.read`) sem buffer para resposta imediata às setas do teclado, publicando `geometry_msgs/msg/Twist` no tópico `/cmd_vel`.
- **Mapeamento de Teclas:**
  - **`↑` / `↓`:** Frente / Ré
  - **`←` / `→`:** Girar para a Esquerda / Direita
  - **`Barra de Espaço` (ou `k` / `s`):** Parada imediata (`0.0 m/s`, `0.0 rad/s`)
  - **`+` / `-`:** Aumentar / Diminuir velocidade linear e angular
  - **`q` (ou `Ctrl + C`):** Freia e encerra o nó

### 7.2. Monitor de Telemetria da Placa-Mãe (`stam-monitor`)
- **Script Executável:** [`~/.local/bin/stam-monitor`](file:///home/lucas/.local/bin/stam-monitor)
- **Funcionamento:** Nó ROS 2 em Python (`stam_telemetry_monitor`) que assina `/stam/base/status` e exibe um painel em tempo real no terminal com:
  - Status da conexão (ONLINE / SEM SINAL), frequência (Hz) e contagem de pacotes
  - Tensão da bateria 10S (`V`), barra visual de carga (`%` entre `33.0 V` e `42.0 V`) e estado (`NORMAL` / `BAIXA` / `CRÍTICA`)
  - Temperatura interna da placa-mãe do Hoverboard (`°C`)
  - Rotação das rodas Esquerda e Direita (`RPM` e estimativa de velocidade tangencial em `m/s`)
  - Comandos atuais (`Speed` e `Steer`) enviados pelo ESP32 ao Hoverboard

---

## 8. Guia Rápido de Operação (Teleoperação Completa: Vídeo + Motores + Telemetria)

1. **Na Orange Pi 4 Pro (com Câmera C920 e ESP32 plugados nas portas USB):**
   ```bash
   ssh orangepi
   # Subir Câmera + Ponte do ESP32 juntas:
   ros2 launch stam_base teleop_robot.launch.py
   # (Ou apenas o nó dos motores: ros2 run stam_base hoverboard_bridge_node)
   ```

2. **No PC — Visualizar a Câmera:**
   ```bash
   ros2 run rqt_image_view rqt_image_view
   ```
   *(Selecionar o tópico `/stam/camera/image_raw`)*

3. **No PC — Controlar os Motores pelas Setas do Teclado:**
   - **Opção 1 (Nó oficial do STAM com Setas + Barra de Espaço para freio):**
     ```bash
     stam-teleop
     ```
   - **Opção 2 (Usando o `turtle_teleop_key` do Turtlesim remapeado para `/cmd_vel`):**
     ```bash
     ros2 run turtlesim turtle_teleop_key --ros-args -r /turtle1/cmd_vel:=/cmd_vel
     ```

4. **No PC — Monitorar a Telemetria do Hoverboard em Tempo Real:**
   ```bash
   stam-monitor
   ```

---

## 9. Diretrizes de Desenvolvimento
Todas as sugestões de desenvolvimento, nós (*nodes*), eletrônica ou scripts devem **obrigatoriamente** considerar:
1. O uso do **ROS 2 Humble**;
2. A arquitetura **ARM64 (`aarch64`) da Orange Pi 4 Pro**;
3. A separação modular: **ESP32 dedicado à locomoção (Hoverboard + futura IMU)** e demais sensores em avaliação (segundo ESP32 ou GPIO direto da Orange Pi 4 Pro).

---

## 10. Status Atual dos Testes e Próximos Passos
- **Teleoperação e Telemetria em Bancada (Validado):**
  - Comunicação bidirecional completa validada entre PC (`stam-teleop` / `stam-monitor`), Orange Pi 4 Pro (`hoverboard_bridge_node`), ESP32 (`USART2`) e Placa-Mãe do Hoverboard (`EFeru`).
  - Telemetria recebida a ~10 Hz com leituras coerentes de tensão da bateria 10S (~40,6 V), temperatura interna (~38–39 °C) e RPM das rodas.
- **Observação sobre Teleoperação via Teclado (`stam-teleop`):**
  - Identificado que pequenos engasgos ao segurar uma tecla decorrem do *Typematic Delay* de 500 ms do teclado no Linux coincidindo com o `cmd_vel_timeout` de `0.5 s` no `hoverboard_bridge_node` (além da limitação do terminal de enviar apenas uma tecla/direção por vez).
- **Próximo Passo Planejado (Controle de PS4 via Bluetooth):**
  - Integrar um controle **DualShock 4 (PS4)** conectado via **Bluetooth diretamente na Orange Pi 4 Pro** (`joy` + `teleop_twist_joy`), permitindo controle analógico suave e simultâneo de velocidade linear (`speed`) e curva (`steer`) sem engasgos.
