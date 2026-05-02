#!/usr/bin/env bash
set -euo pipefail

MODE="${1:---apply}"
echo "[ATENA] Endpoint readiness installer (${MODE})"

PY_PKGS=(pyautogui pynput pillow pytesseract psutil)

install_python_pkgs() {
  python3 -m pip install --upgrade pip
  python3 -m pip install "${PY_PKGS[@]}"
}

check_python_pkgs() {
  python3 - <<'PY'
import importlib
mods=['pyautogui','pynput','PIL','pytesseract','psutil']
missing=[]
for m in mods:
    try:
        importlib.import_module(m)
        print(f'OK {m}')
    except Exception:
        print(f'MISS {m}')
        missing.append(m)
if missing:
    raise SystemExit(2)
PY
}

install_tesseract() {
  case "$(uname -s)" in
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y tesseract-ocr || true
      elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y tesseract || true
      elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --noconfirm tesseract || true
      fi
      ;;
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        brew install tesseract || true
      fi
      ;;
    *)
      echo "Instale tesseract manualmente para este sistema." ;;
  esac
}

if [[ "$MODE" == "--check" ]]; then
  check_python_pkgs
  echo "READINESS_DEPENDENCIES=OK"
  exit 0
fi

install_python_pkgs
install_tesseract

echo "Executando auditoria final..."
./scripts/audit_agent_endpoint_readiness.sh || {
  echo "READINESS_DEPENDENCIES=PARTIAL (verifique dependências nativas/permissões)."
  exit 1
}

echo "READINESS_DEPENDENCIES=OK"
