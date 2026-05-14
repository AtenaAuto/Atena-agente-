#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT="docs/ATENA_GO_NO_GO_DAILY_${STAMP}.md"

status="GO"
notes=()

run_step() {
  local cmd="$1"
  local label="$2"
  if eval "$cmd"; then
    notes+=("✅ ${label}: OK")
  else
    notes+=("❌ ${label}: FAIL")
    status="NO-GO"
  fi
}

run_step "python -m pip install -r generated/atena_battle_royale_stack/backend/requirements.txt >/dev/null" "Dependências backend gerado"
run_step "pytest -q tests/unit/test_terminal_assistant_task_exec.py tests/unit/test_terminal_assistant_internet_flow.py tests/unit/test_terminal_assistant_five_topics.py generated/atena_battle_royale_stack/backend/tests/test_health.py" "Testes críticos"
run_step "python protocols/atena_module_smoke_mission.py" "Module smoke mission"
run_step "python protocols/atena_complex_research_mission.py" "Missão internet complexa"
run_step "python protocols/atena_enterprise_internet_strategy_mission.py" "Missão internet empresarial"
run_step "python scripts/atena_scorecard.py" "Scorecard ATENA (nota final)"

{
  echo "# ATENA GO/NO-GO Diário"
  echo
  echo "- Timestamp UTC: ${STAMP}"
  echo "- Status final: **${status}**"
  echo
  echo "## Evidências"
  for n in "${notes[@]}"; do
    echo "- ${n}"
  done
  echo
  echo "## Próxima ação"
  if [[ "$status" == "GO" ]]; then
    echo "- Liberar execução assistida e monitoramento contínuo."
  else
    echo "- Bloquear promoção e abrir investigação dos checks com falha."
  fi
} > "$REPORT"

echo "Relatório diário: $REPORT"
if [[ "$status" == "GO" ]]; then
  exit 0
fi
exit 1
