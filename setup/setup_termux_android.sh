#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo "[ATENA] Atualizando pacotes do Termux..."
pkg update -y
pkg upgrade -y

echo "[ATENA] Instalando dependências base..."
pkg install -y git python clang rust

if [ ! -d "ATENA-" ]; then
  echo "[ATENA] Clonando repositório..."
  git clone https://github.com/AtenaAuto/ATENA-.git
fi

cd ATENA-

echo "[ATENA] Instalando dependências Python..."
python -m pip install --upgrade pip
python -m pip install -r setup/requirements.txt

echo "[ATENA] Setup concluído."
echo "Próximos passos:"
echo "  export DASHSCOPE_API_KEY=\"SUA_CHAVE\""
echo "  export ATENA_QWEN_BASE_URL=\"https://dashscope.aliyuncs.com/compatible-mode/v1\""
echo "  ./atena doctor"
echo "  ./atena assistant"
