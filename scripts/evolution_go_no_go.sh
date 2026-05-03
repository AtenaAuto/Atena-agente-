#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REPORT_DIR="docs"
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
REPORT_FILE="$REPORT_DIR/EVOLUTION_GO_NO_GO_${TS}.md"

mkdir -p "$REPORT_DIR"

run_check() {
  local name="$1"
  local cmd="$2"
  echo "[CHECK] $name"
  if bash -lc "$cmd"; then
    echo "PASS|$name|$cmd"
  else
    echo "FAIL|$name|$cmd"
    return 1
  fi
}

{
  echo "# Evolution GO/NO-GO Report"
  echo
  echo "- Timestamp (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- Repo: $(basename "$ROOT_DIR")"
  echo
  echo "## Checks"
} > "$REPORT_FILE"

PASS_COUNT=0
TOTAL=0

CHECKS=(
  "unit_internet|pytest -q tests/unit/test_internet_challenge.py tests/unit/test_llm_router_auto_orchestrate.py"
  "unit_evolution|pytest -q tests/unit/test_skill_marketplace_validation.py tests/unit/test_atena_module_preloader.py tests/unit/test_production_programming_probe.py"
  "repo_connectivity|bash scripts/audit_repo_connectivity.sh"
  "assistant_modes|ATENA_FORCE=true ATENA_AUTO_ENDPOINT_SETUP=false bash -lc \"printf '/status\\n/sair\\n' | bash atena assistant\" >/tmp/atena_assistant_mode.log"
)

for entry in "${CHECKS[@]}"; do
  TOTAL=$((TOTAL+1))
  name="${entry%%|*}"
  cmd="${entry#*|}"
  if out="$(run_check "$name" "$cmd" 2>&1)"; then
    PASS_COUNT=$((PASS_COUNT+1))
    printf -- "- ✅ **%s**\n" "$name" >> "$REPORT_FILE"
  else
    printf -- "- ❌ **%s**\n" "$name" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    echo "$out" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
  fi
  echo "$out" | tail -n 5
  echo
 done

if [[ "$PASS_COUNT" -eq "$TOTAL" ]]; then
  STATUS="GO"
else
  STATUS="NO-GO"
fi

{
  echo
  echo "## Result"
  echo
  echo "- Status: **$STATUS**"
  echo "- Passed: **$PASS_COUNT/$TOTAL**"
} >> "$REPORT_FILE"

echo "REPORT_FILE=$REPORT_FILE"
echo "STATUS=$STATUS"
[[ "$STATUS" == "GO" ]]
