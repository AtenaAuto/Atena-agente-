#!/usr/bin/env bash
set -euo pipefail

echo "[ATENA] Endpoint Readiness Audit"
set +e
python3 - <<'PY'
import importlib
checks = {
  'pyautogui':'Desktop automation (mouse/keyboard)',
  'pynput':'Input hooks',
  'PIL':'Image capture/processing',
  'pytesseract':'OCR bridge',
  'psutil':'System telemetry',
}
missing=[]
for mod,desc in checks.items():
    try:
        importlib.import_module(mod)
        print(f'PASS {mod}: {desc}')
    except Exception:
        print(f'FAIL {mod}: {desc}')
        missing.append(mod)
if missing:
    print('MISSING=' + ','.join(missing))
    raise SystemExit(2)
print('ALL_REQUIRED_MODULES_OK')
PY
mod_status=$?

echo "Running critical agent tests..."
pytest -q tests/unit/test_computer_actuator.py tests/unit/test_terminal_assistant_internet_flow.py
test_status=$?
set -e
if [[ $mod_status -ne 0 || $test_status -ne 0 ]]; then
  echo "READINESS_STATUS=NOT_READY"
  echo "Dica: rode ./setup/install_endpoint_readiness.sh --apply"
  exit 1
fi
echo "READINESS_STATUS=READY"
