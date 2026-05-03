#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/content/projects/ATENA-}"
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON_BIN="$VENV_DIR/bin/python"

mkdir -p "$(dirname "$PROJECT_ROOT")"

if [[ ! -d "$PROJECT_ROOT" ]]; then
  echo "[ATENA] Clonando repositório em $PROJECT_ROOT"
  git clone https://github.com/AtenaAuto/ATENA-.git "$PROJECT_ROOT"
fi

cd "$PROJECT_ROOT"

if [[ ! -d "$VENV_DIR" ]]; then
  "$(${PYTHON:-python3} -c 'import sys;print(sys.executable)')" -m venv "$VENV_DIR"
fi

# Corrige casos raros de venv sem pip (ensurepip failed)
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "[ATENA] pip ausente no venv. Aplicando fallback get-pip.py"
  GET_PIP="$(dirname "$PROJECT_ROOT")/get-pip.py"
  if command -v wget >/dev/null 2>&1; then
    wget -q https://bootstrap.pypa.io/get-pip.py -O "$GET_PIP"
  else
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$GET_PIP"
  fi
  "$PYTHON_BIN" "$GET_PIP"
  rm -f "$GET_PIP"
fi


"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r setup/requirements-pinned.txt
"$PYTHON_BIN" -m pip install -r setup/requirements-dev.txt

# Dependências de sistema necessárias para OCR/headless
apt-get update -y
apt-get install -y tesseract-ocr

# Playwright (opcional para browser agent)
"$PYTHON_BIN" -m playwright install chromium || true

cat <<'EOF'
✅ Bootstrap concluído.
Use um destes comandos no Colab:
  !bash atena doctor
  !ATENA_AUTO_ENDPOINT_SETUP=false USER=colab bash atena assistant
EOF
