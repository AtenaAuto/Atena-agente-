#!/bin/bash

# Script de Instalação do Serviço ATENA Ω (Systemd)
# Garante que a ATENA rode em segundo plano e inicie com o sistema.

SERVICE_NAME="atena-omega"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
WORKING_DIR=$(pwd)
PYTHON_PATH=$(which python3)

echo "🛠️ Configurando serviço ATENA Ω..."

# Criar o arquivo de serviço systemd
sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=ATENA Ω - Inteligência Digital Evolutiva
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKING_DIR
ExecStart=$PYTHON_PATH $WORKING_DIR/atena_daemon.py
Restart=always
RestartSec=10
StandardOutput=append:$WORKING_DIR/atena_daemon.log
StandardError=append:$WORKING_DIR/atena_daemon.log

[Install]
WantedBy=multi-user.target
EOF"

# Recarregar systemd e habilitar o serviço
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo "✅ Serviço '$SERVICE_NAME' instalado e iniciado com sucesso!"
echo "📊 Para ver os logs: tail -f atena_daemon.log"
echo "🛑 Para parar: sudo systemctl stop $SERVICE_NAME"
echo "🚀 Para iniciar: sudo systemctl start $SERVICE_NAME"
echo "🔄 Para reiniciar: sudo systemctl restart $SERVICE_NAME"
