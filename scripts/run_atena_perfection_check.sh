#!/usr/bin/env bash
set -euo pipefail

python -m pip install -r generated/atena_battle_royale_stack/backend/requirements.txt >/dev/null
python -m playwright install chromium >/dev/null
if ! python -m playwright install-deps chromium >/dev/null; then
  echo "WARN: playwright install-deps falhou (rede/apt). Seguindo com fallback HTTP da missão."
fi

pytest -q \
  tests/unit/test_terminal_assistant_task_exec.py \
  tests/unit/test_terminal_assistant_internet_flow.py \
  tests/unit/test_terminal_assistant_five_topics.py \
  generated/atena_battle_royale_stack/backend/tests/test_health.py

python protocols/atena_complex_research_mission.py

echo "OK: Atena perfection check completed"
