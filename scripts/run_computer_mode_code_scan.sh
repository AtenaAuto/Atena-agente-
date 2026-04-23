#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="$(date -u +%Y-%m-%d)"
DEEP_HASH=0
for arg in "$@"; do
  case "$arg" in
    --deep-hash) DEEP_HASH=1 ;;
    *) STAMP="$arg" ;;
  esac
done
REPORTS_DIR="analysis_reports"
mkdir -p "$REPORTS_DIR"

SCAN_ARQUIVOS="$REPORTS_DIR/SCAN_ARQUIVOS_${STAMP}.txt"
SCAN_CODIGOS_LISTA="$REPORTS_DIR/SCAN_CODIGOS_LISTA_${STAMP}.txt"
SCAN_CODIGO_COMPLETO="$REPORTS_DIR/SCAN_CODIGO_COMPLETO_${STAMP}.txt"
LOG_FILE="$REPORTS_DIR/EXECUCAO_MODO_COMPUTADOR_SCAN_CODIGOS_${STAMP}.log"
SUMMARY_FILE="$REPORTS_DIR/EXECUCAO_MODO_COMPUTADOR_SCAN_CODIGOS_${STAMP}.md"
DIFF_FILE="$REPORTS_DIR/SCAN_CODIGOS_DIFF_${STAMP}.txt"
HASH_FILE="$REPORTS_DIR/SCAN_CODIGOS_HASH_${STAMP}.txt"
HASH_DIFF_FILE="$REPORTS_DIR/SCAN_CODIGOS_HASH_DIFF_${STAMP}.txt"

printf '/run rg --files > %s\n/run find core modules protocols -type f > %s\n/run cat core/atena_terminal_assistant.py modules/computer_actuator.py protocols/atena_invoke.py > %s\n/exit\n' \
  "$SCAN_ARQUIVOS" "$SCAN_CODIGOS_LISTA" "$SCAN_CODIGO_COMPLETO" \
  | ./atena assistant | tee "$LOG_FILE"

# Gera diff incremental contra a última varredura disponível.
PREV_SCAN="$(ls -1t "$REPORTS_DIR"/SCAN_CODIGOS_LISTA_*.txt 2>/dev/null | grep -v "$SCAN_CODIGOS_LISTA" | head -n 1 || true)"
if [[ -n "${PREV_SCAN}" && -f "${PREV_SCAN}" ]]; then
  sort "$PREV_SCAN" > /tmp/atena_prev_codes_${STAMP}.txt
  sort "$SCAN_CODIGOS_LISTA" > /tmp/atena_curr_codes_${STAMP}.txt
  {
    echo "# Diff de códigos (${STAMP})"
    echo "Anterior: ${PREV_SCAN}"
    echo "Atual: ${SCAN_CODIGOS_LISTA}"
    echo
    echo "## Novos arquivos"
    comm -13 /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt || true
    echo
    echo "## Arquivos removidos"
    comm -23 /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt || true
  } > "$DIFF_FILE"
  rm -f /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt
else
  echo "# Diff de códigos (${STAMP})" > "$DIFF_FILE"
  echo "Sem baseline anterior para comparar." >> "$DIFF_FILE"
fi

if [[ "$DEEP_HASH" == "1" ]]; then
  # Hash de conteúdo por arquivo de código para detectar mudanças reais.
  while IFS= read -r f; do
    [[ -n "$f" && -f "$f" ]] || continue
    sha256sum "$f"
  done < "$SCAN_CODIGOS_LISTA" | sort > "$HASH_FILE"

  PREV_HASH="$(ls -1t "$REPORTS_DIR"/SCAN_CODIGOS_HASH_*.txt 2>/dev/null | grep -v "$HASH_FILE" | head -n 1 || true)"
  if [[ -n "${PREV_HASH}" && -f "${PREV_HASH}" ]]; then
    {
      echo "# Diff de hash de códigos (${STAMP})"
      echo "Anterior: ${PREV_HASH}"
      echo "Atual: ${HASH_FILE}"
      echo
      echo "## Hashes novos/alterados"
      comm -13 "$PREV_HASH" "$HASH_FILE" || true
      echo
      echo "## Hashes removidos"
      comm -23 "$PREV_HASH" "$HASH_FILE" || true
    } > "$HASH_DIFF_FILE"
  else
    {
      echo "# Diff de hash de códigos (${STAMP})"
      echo "Sem baseline de hash anterior para comparar."
    } > "$HASH_DIFF_FILE"
  fi
fi

{
  echo "# Execução modo computador — varredura de códigos (${STAMP})"
  echo
  echo "## Artefatos gerados"
  echo "- \`${SCAN_ARQUIVOS}\`"
  echo "- \`${SCAN_CODIGOS_LISTA}\`"
  echo "- \`${SCAN_CODIGO_COMPLETO}\`"
  echo "- \`${LOG_FILE}\`"
  echo "- \`${DIFF_FILE}\`"
  if [[ "$DEEP_HASH" == "1" ]]; then
    echo "- \`${HASH_FILE}\`"
    echo "- \`${HASH_DIFF_FILE}\`"
  fi
  echo
  echo "## Prévia"
  echo "- Total de arquivos listados: $(wc -l < "$SCAN_ARQUIVOS" | tr -d ' ')"
  echo "- Total de códigos (core/modules/protocols): $(wc -l < "$SCAN_CODIGOS_LISTA" | tr -d ' ')"
  if [[ -n "${PREV_SCAN}" && -f "${PREV_SCAN}" ]]; then
    echo "- Baseline anterior: \`${PREV_SCAN}\`"
  else
    echo "- Baseline anterior: não encontrado"
  fi
  echo
  echo "## Status"
  if [[ "$DEEP_HASH" == "1" ]]; then
    echo "Varredura concluída no modo computador com inventário, dump, diff incremental e diff por hash."
  else
    echo "Varredura concluída no modo computador com extração de inventário, dump consolidado e diff incremental."
  fi
} > "$SUMMARY_FILE"

echo "✅ Relatório salvo em: $SUMMARY_FILE"
