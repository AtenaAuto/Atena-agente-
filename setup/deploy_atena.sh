#!/bin/bash

# ==============================================================================
# ATENA Ω - SCRIPT DE IMPLANTAÇÃO AUTOMATIZADA (PRODUÇÃO)
# ==============================================================================
# Este script configura o ambiente completo para a ATENA Ω v4.0, incluindo:
# 1. Dependências do Sistema (Git, Python, SQLite, Build Tools)
# 2. Ambiente Virtual Python (venv)
# 3. Dependências de IA (FAISS, Transformers, FastAPI, Streamlit)
# 4. Configuração do Serviço Systemd (Persistência 24/7)
# ==============================================================================

set -e # Encerra em caso de erro

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧬 Iniciando Implantação da ATENA Ω v4.0...${NC}"

# 1. Atualizar Sistema e Instalar Dependências Base
echo -e "${GREEN}[1/5] Instalando dependências do sistema...${NC}"
sudo apt-get update
sudo apt-get install -y git python3-pip python3-venv sqlite3 build-essential libsqlite3-dev

# 2. Configurar Repositório e Ambiente Virtual
echo -e "${GREEN}[2/5] Configurando ambiente Python...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 3. Instalar Dependências Python
echo -e "${GREEN}[3/5] Instalando bibliotecas de IA e Web...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
# Garantir que dependências críticas para v4.0 estejam presentes
pip install fastapi uvicorn streamlit plotly pandas numpy faiss-cpu sentence-transformers

# 4. Configurar Permissões
echo -e "${GREEN}[4/5] Ajustando permissões...${NC}"
chmod +x atena_daemon.py install_service.sh
mkdir -p atena_evolution/knowledge
mkdir -p atena_evolution/code

# 5. Instalar como Serviço do Sistema (Systemd)
echo -e "${GREEN}[5/5] Registrando ATENA Ω como serviço persistente...${NC}"
WORKING_DIR=$(pwd)
PYTHON_PATH="$WORKING_DIR/venv/bin/python3"
SERVICE_NAME="atena-omega"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

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
Environment=PYTHONPATH=$WORKING_DIR

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}✅ IMPLANTAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "🚀 ATENA Ω está rodando em segundo plano."
echo -e "📊 Logs de Evolução: ${NC}tail -f atena_daemon.log"
echo -e "🧠 Neural Dashboard: ${NC}streamlit run neural_dashboard.py"
echo -e "🌐 Neural API:       ${NC}python3 neural_api.py"
echo -e "${BLUE}============================================================${NC}"
