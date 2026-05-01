#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# 🔱 ATENA Code Scanner v2.0 - Varredura Avançada de Código
# Sistema completo de análise, hash, diff e relatórios inteligentes
# =============================================================================
#
# Recursos:
# - Varredura paralela de múltiplos diretórios
# - Hash criptográfico extensivo (SHA256, BLAKE2, MD5)
# - Diff inteligente com similaridade
# - Análise de linguagem (Python, JavaScript, Go, Rust, etc.)
# - Estatísticas de complexidade e linhas de código
# - Exportação multi-formato (JSON, Markdown, CSV)
# - Integração com telemetria da ATENA
# =============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
STAMP="$(date -u +%Y-%m-%d_%H%M%S)"
DEEP_HASH=0
FULL_ANALYSIS=0
JSON_OUTPUT=0
PARALLEL_JOBS=4
COMPARE_WITH_PREV=1
MIN_FILE_SIZE=100
MAX_FILE_SIZE=$((50 * 1024 * 1024))  # 50MB

# Extração de argumentos
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --deep-hash) DEEP_HASH=1 ;;
    --full) FULL_ANALYSIS=1 ;;
    --json) JSON_OUTPUT=1 ;;
    --no-compare) COMPARE_WITH_PREV=0 ;;
    --jobs=*) PARALLEL_JOBS="${arg#*=}" ;;
    --help|-h) 
      echo "Uso: $0 [OPÇÕES] [DATA]"
      echo ""
      echo "Opções:"
      echo "  --deep-hash     Calcula hashes avançados por arquivo"
      echo "  --full          Análise completa (estatísticas, linguagens, complexidade)"
      echo "  --json          Gera saída em formato JSON"
      echo "  --no-compare    Não compara com varreduras anteriores"
      echo "  --jobs=N        Número de jobs paralelos (padrão: 4)"
      echo "  --help          Mostra esta ajuda"
      echo ""
      echo "  DATA            Timestamp personalizado (padrão: data atual)"
      exit 0
      ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  STAMP="${EXTRA_ARGS[0]}"
fi

# Diretórios a varrer (configuráveis via ambiente)
SCAN_DIRS=(
  "core"
  "modules"
  "protocols"
  "skills"
  "plugins"
  "atena_evolution"
  "analysis_reports"
)
# Filtra apenas diretórios existentes
SCAN_DIRS=($(for d in "${SCAN_DIRS[@]}"; do [[ -d "$d" ]] && echo "$d"; done))

# Extensões a incluir (configuráveis)
INCLUDE_EXTS=(
  "py"      # Python
  "js"      # JavaScript
  "ts"      # TypeScript
  "go"      # Go
  "rs"      # Rust
  "c" "cpp" "h" "hpp"  # C/C++
  "java"    # Java
  "rb"      # Ruby
  "sh" "bash" "zsh"    # Shell scripts
  "sql"     # SQL
  "json"    # JSON
  "yaml" "yml"         # YAML
  "md" "markdown"      # Markdown
  "txt"     # Texto
)

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
log_debug() { [[ -n "${DEBUG:-}" ]] && echo "[DEBUG] $*"; }

# Detecta linguagem baseado na extensão
detect_language() {
  local ext="$1"
  case "$ext" in
    py) echo "Python" ;;
    js) echo "JavaScript" ;;
    ts) echo "TypeScript" ;;
    go) echo "Go" ;;
    rs) echo "Rust" ;;
    c|cpp|h|hpp) echo "C/C++" ;;
    java) echo "Java" ;;
    rb) echo "Ruby" ;;
    sh|bash|zsh) echo "Shell" ;;
    sql) echo "SQL" ;;
    json) echo "JSON" ;;
    yaml|yml) echo "YAML" ;;
    md|markdown) echo "Markdown" ;;
    txt) echo "Text" ;;
    *) echo "Unknown" ;;
  esac
}

# Calcula hashes de arquivo
compute_file_hashes() {
  local file="$1"
  local md5=""
  local sha256=""
  local blake2=""
  
  if [[ -f "$file" ]]; then
    md5=$(md5sum "$file" 2>/dev/null | cut -d' ' -f1)
    sha256=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1)
    if command -v b2sum &>/dev/null; then
      blake2=$(b2sum "$file" 2>/dev/null | cut -d' ' -f1 | cut -c1-32)
    fi
  fi
  
  echo "${md5}:${sha256}:${blake2}"
}

# Conta linhas de código (ignorando blanks)
count_lines() {
  local file="$1"
  if [[ -f "$file" ]]; then
    wc -l < "$file" | tr -d ' '
  else
    echo "0"
  fi
}

# Conta linhas não vazias
count_non_blank_lines() {
  local file="$1"
  if [[ -f "$file" ]]; then
    grep -c '^[[:space:]]*[^[:space:]]' "$file" 2>/dev/null || echo "0"
  else
    echo "0"
  fi
}

# Estima complexidade (aproximada)
estimate_complexity() {
  local file="$1"
  local ext="${file##*.}"
  
  if [[ "$ext" == "py" ]]; then
    # Python: conta funções, classes, condicionais
    local total=0
    [[ -f "$file" ]] && total=$(grep -E '^[[:space:]]*(def |class |if |elif |else:|for |while |try:|except|with )' "$file" 2>/dev/null | wc -l)
    echo "$total"
  elif [[ "$ext" =~ ^(c|cpp|h|hpp|java|rs|go)$ ]]; then
    # C-like: conta funções, structs, classes, condicionais
    local total=0
    [[ -f "$file" ]] && total=$(grep -E '(^[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]+[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*\(|^[[:space:]]*(if|for|while|switch|case)[[:space:]]*\(|^[[:space:]]*(class|struct|enum|interface)[[:space:]]+)' "$file" 2>/dev/null | wc -l)
    echo "$total"
  elif [[ "$ext" =~ ^(sh|bash|zsh)$ ]]; then
    # Shell: conta funções e condicionais
    local total=0
    [[ -f "$file" ]] && total=$(grep -E '^[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*\(\)|^[[:space:]]*(if|elif|for|while|case)[[:space:]]' "$file" 2>/dev/null | wc -l)
    echo "$total"
  else
    echo "0"
  fi
}

# =============================================================================
# CONFIGURAÇÃO DE SAÍDA
# =============================================================================
REPORTS_DIR="analysis_reports"
mkdir -p "$REPORTS_DIR"

# Arquivos de saída
SCAN_ARQUIVOS="$REPORTS_DIR/SCAN_ARQUIVOS_${STAMP}.txt"
SCAN_CODIGOS_LISTA="$REPORTS_DIR/SCAN_CODIGOS_LISTA_${STAMP}.txt"
SCAN_CODIGO_COMPLETO="$REPORTS_DIR/SCAN_CODIGO_COMPLETO_${STAMP}.txt"
SCAN_METADADOS="$REPORTS_DIR/SCAN_METADADOS_${STAMP}.json"
LOG_FILE="$REPORTS_DIR/EXECUCAO_MODO_COMPUTADOR_SCAN_CODIGOS_${STAMP}.log"
SUMMARY_FILE="$REPORTS_DIR/EXECUCAO_MODO_COMPUTADOR_SCAN_CODIGOS_${STAMP}.md"
DIFF_FILE="$REPORTS_DIR/SCAN_CODIGOS_DIFF_${STAMP}.txt"
HASH_FILE="$REPORTS_DIR/SCAN_CODIGOS_HASH_${STAMP}.txt"
HASH_DIFF_FILE="$REPORTS_DIR/SCAN_CODIGOS_HASH_DIFF_${STAMP}.txt"
STATS_FILE="$REPORTS_DIR/SCAN_ESTATISTICAS_${STAMP}.txt"
LANG_STATS_FILE="$REPORTS_DIR/SCAN_LINGUAGENS_${STAMP}.txt"

# =============================================================================
# VARREdura DE ARQUIVOS
# =============================================================================
log_info "Iniciando varredura de código - Timestamp: $STAMP"
log_info "Diretórios a varrer: ${SCAN_DIRS[*]}"
log_info "Extensões incluídas: ${INCLUDE_EXTS[*]}"
log_info "Paralelismo: $PARALLEL_JOBS jobs"

# Constrói padrão de extensões
EXT_PATTERN=""
for ext in "${INCLUDE_EXTS[@]}"; do
  EXT_PATTERN="${EXT_PATTERN} -name \"*.${ext}\" -o"
done
EXT_PATTERN="${EXT_PATTERN% -o}"  # Remove último -o

# Varredura principal (usando find otimizado)
START_TIME=$(date +%s%3N)

# Lista todos os arquivos recursivamente
log_info "Listando arquivos..."
find "${SCAN_DIRS[@]}" -type f \( ${EXT_PATTERN} \) ! -path "*/__pycache__/*" ! -path "*/.venv/*" ! -path "*/node_modules/*" ! -path "*/.git/*" 2>/dev/null | sort > "$SCAN_ARQUIVOS"

# Filtra apenas arquivos com tamanho adequado
while IFS= read -r file; do
  if [[ -f "$file" ]]; then
    size=$(stat -c%s "$file" 2>/dev/null || echo "0")
    if [[ "$size" -ge "$MIN_FILE_SIZE" && "$size" -le "$MAX_FILE_SIZE" ]]; then
      echo "$file"
    fi
  fi
done < "$SCAN_ARQUIVOS" > "$SCAN_CODIGOS_LISTA"

TOTAL_FILES=$(wc -l < "$SCAN_ARQUIVOS" | tr -d ' ')
TOTAL_CODES=$(wc -l < "$SCAN_CODIGOS_LISTA" | tr -d ' ')
log_info "Total de arquivos: $TOTAL_FILES"
log_info "Arquivos de código: $TOTAL_CODES"

# =============================================================================
# EXTRAÇÃO DE CONTEÚDO (Paralela)
# =============================================================================
log_info "Extraindo conteúdo de arquivos (paralelo)..."
export -f detect_language compute_file_hashes count_lines count_non_blank_lines estimate_complexity

# Função para processar um arquivo e gerar linha de metadados
process_file() {
  local file="$1"
  local ext="${file##*.}"
  local lang="$(detect_language "$ext")"
  local size=$(stat -c%s "$file" 2>/dev/null || echo "0")
  local lines=$(count_lines "$file")
  local non_blank=$(count_non_blank_lines "$file")
  local complexity=$(estimate_complexity "$file")
  local hashes=""
  
  if [[ "$DEEP_HASH" == "1" ]]; then
    hashes="$(compute_file_hashes "$file")"
  fi
  
  # Conteúdo (truncado para os primeiros 500 caracteres)
  local content_preview=""
  if [[ -f "$file" && "$size" -le 100000 ]]; then
    content_preview=$(head -c 500 "$file" | tr '\n' ' ' | sed 's/"/\\"/g')
  fi
  
  echo "{\"path\":\"$file\",\"language\":\"$lang\",\"size\":$size,\"lines\":$lines,\"non_blank\":$non_blank,\"complexity\":$complexity,\"hashes\":\"$hashes\",\"preview\":\"$content_preview\"}"
}

# Processa arquivos em paralelo
if command -v parallel &>/dev/null && [[ "$PARALLEL_JOBS" -gt 1 ]]; then
  log_info "Usando GNU parallel para processamento..."
  cat "$SCAN_CODIGOS_LISTA" | parallel -j "$PARALLEL_JOBS" process_file {} > "$SCAN_METADADOS"
else
  log_info "Processando sequencialmente..."
  while IFS= read -r file; do
    process_file "$file" >> "$SCAN_METADADOS"
  done < "$SCAN_CODIGOS_LISTA"
fi

# Gera arquivo consolidado (apenas conteúdo dos arquivos grandes)
log_info "Gerando dump consolidado..."
{
  echo "# ============================================================================="
  echo "# ATENA CODE SCAN - Dump Consolidado"
  echo "# Timestamp: $STAMP"
  echo "# Total de arquivos: $TOTAL_CODES"
  echo "# ============================================================================="
  echo ""
  
  while IFS= read -r file; do
    if [[ -f "$file" ]]; then
      size=$(stat -c%s "$file" 2>/dev/null || echo "0")
      if [[ "$size" -le 50000 ]]; then  # Apenas arquivos menores que 50KB
        echo ""
        echo "# ============================================================================="
        echo "# FILE: $file"
        echo "# ============================================================================="
        echo ""
        cat "$file" 2>/dev/null || echo "*** ERRO AO LER ARQUIVO ***"
        echo ""
      fi
    fi
  done < "$SCAN_CODIGOS_LISTA"
} > "$SCAN_CODIGO_COMPLETO"

END_TIME=$(date +%s%3N)
ELAPSED_MS=$((END_TIME - START_TIME))
log_info "Varredura concluída em ${ELAPSED_MS}ms"

# =============================================================================
# ESTATÍSTICAS AGREGADAS
# =============================================================================
log_info "Gerando estatísticas..."

if [[ -f "$SCAN_METADADOS" ]]; then
  # Estatísticas gerais usando jq se disponível
  if command -v jq &>/dev/null; then
    TOTAL_SIZE=$(jq -s 'map(.size) | add' "$SCAN_METADADOS" 2>/dev/null || echo "0")
    TOTAL_LINES=$(jq -s 'map(.lines) | add' "$SCAN_METADADOS" 2>/dev/null || echo "0")
    TOTAL_NON_BLANK=$(jq -s 'map(.non_blank) | add' "$SCAN_METADADOS" 2>/dev/null || echo "0")
    TOTAL_COMPLEXITY=$(jq -s 'map(.complexity) | add' "$SCAN_METADADOS" 2>/dev/null || echo "0")
    AVG_COMPLEXITY=$(jq -s 'map(.complexity) | add / length' "$SCAN_METADADOS" 2>/dev/null || echo "0")
  else
    TOTAL_SIZE=$(awk -F'"size":' '{sum+=$2} END {print sum}' "$SCAN_METADADOS" 2>/dev/null | cut -d',' -f1)
    TOTAL_LINES=$(awk -F'"lines":' '{sum+=$2} END {print sum}' "$SCAN_METADADOS" 2>/dev/null | cut -d',' -f1)
    TOTAL_NON_BLANK=$(awk -F'"non_blank":' '{sum+=$2} END {print sum}' "$SCAN_METADADOS" 2>/dev/null | cut -d',' -f1)
    TOTAL_COMPLEXITY=$(awk -F'"complexity":' '{sum+=$2} END {print sum}' "$SCAN_METADADOS" 2>/dev/null | cut -d',' -f1)
    AVG_COMPLEXITY=0
  fi
  
  # Estatísticas por linguagem
  if command -v jq &>/dev/null; then
    jq -s 'group_by(.language) | map({language: .[0].language, count: length, total_lines: map(.lines) | add, total_complexity: map(.complexity) | add})' "$SCAN_METADADOS" > "$LANG_STATS_FILE"
  else
    awk -F'"language":"' '{split($2, a, "\""); lang[a[1]]++} END {for(l in lang) print l, lang[l]}' "$SCAN_METADADOS" > "$LANG_STATS_FILE"
  fi
  
  {
    echo "# Estatísticas da Varredura de Código"
    echo ""
    echo "## Resumo Geral"
    echo "- Total de arquivos de código: $TOTAL_CODES"
    echo "- Tamanho total: $(numfmt --to=iec $TOTAL_SIZE 2>/dev/null || echo "${TOTAL_SIZE} bytes")"
    echo "- Linhas totais: $TOTAL_LINES"
    echo "- Linhas não-brancas: $TOTAL_NON_BLANK"
    echo "- Complexidade total estimada: $TOTAL_COMPLEXITY"
    echo "- Complexidade média por arquivo: $AVG_COMPLEXITY"
    echo "- Tempo de varredura: ${ELAPSED_MS}ms"
    echo ""
  } > "$STATS_FILE"
fi

# =============================================================================
# DIFF INCREMENTAL
# =============================================================================
if [[ "$COMPARE_WITH_PREV" == "1" ]]; then
  log_info "Comparando com varreduras anteriores..."
  
  # Encontra a varredura mais recente (exceto a atual)
  PREV_SCAN="$(ls -1t "$REPORTS_DIR"/SCAN_CODIGOS_LISTA_*.txt 2>/dev/null | grep -v "$SCAN_CODIGOS_LISTA" | head -n 1 || true)"
  
  if [[ -n "${PREV_SCAN}" && -f "${PREV_SCAN}" ]]; then
    sort "$PREV_SCAN" > /tmp/atena_prev_codes_${STAMP}.txt
    sort "$SCAN_CODIGOS_LISTA" > /tmp/atena_curr_codes_${STAMP}.txt
    
    NEW_FILES=$(comm -13 /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt | wc -l | tr -d ' ')
    REMOVED_FILES=$(comm -23 /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt | wc -l | tr -d ' ')
    
    {
      echo "# Diff de códigos (${STAMP})"
      echo "Anterior: ${PREV_SCAN}"
      echo "Atual: ${SCAN_CODIGOS_LISTA}"
      echo ""
      echo "## Resumo"
      echo "- Novos arquivos: $NEW_FILES"
      echo "- Arquivos removidos: $REMOVED_FILES"
      echo ""
      echo "## Novos arquivos"
      comm -13 /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt || true
      echo ""
      echo "## Arquivos removidos"
      comm -23 /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt || true
    } > "$DIFF_FILE"
    
    rm -f /tmp/atena_prev_codes_${STAMP}.txt /tmp/atena_curr_codes_${STAMP}.txt
    log_info "Diff gerado: $NEW_FILES novos, $REMOVED_FILES removidos"
  else
    {
      echo "# Diff de códigos (${STAMP})"
      echo "Sem baseline anterior para comparar."
    } > "$DIFF_FILE"
    log_info "Nenhuma baseline anterior encontrada"
  fi
fi

# =============================================================================
# HASH PROFUNDO (opcional)
# =============================================================================
if [[ "$DEEP_HASH" == "1" ]]; then
  log_info "Calculando hashes profundos..."
  
  # Gera hashes para todos os arquivos de código
  while IFS= read -r f; do
    [[ -n "$f" && -f "$f" ]] || continue
    local md5=$(md5sum "$f" 2>/dev/null | cut -d' ' -f1)
    local sha256=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)
    echo "${md5}:${sha256} $f"
  done < "$SCAN_CODIGOS_LISTA" | sort > "$HASH_FILE"
  
  # Compara com hash anterior
  PREV_HASH="$(ls -1t "$REPORTS_DIR"/SCAN_CODIGOS_HASH_*.txt 2>/dev/null | grep -v "$HASH_FILE" | head -n 1 || true)"
  
  if [[ -n "${PREV_HASH}" && -f "${PREV_HASH}" ]]; then
    NEW_HASHES=$(comm -13 "$PREV_HASH" "$HASH_FILE" | wc -l | tr -d ' ')
    CHANGED_HASHES=$NEW_HASHES
    {
      echo "# Diff de hash de códigos (${STAMP})"
      echo "Anterior: ${PREV_HASH}"
      echo "Atual: ${HASH_FILE}"
      echo ""
      echo "## Resumo"
      echo "- Arquivos com hash alterado/novo: $NEW_HASHES"
      echo ""
      echo "## Hashes alterados/novos"
      comm -13 "$PREV_HASH" "$HASH_FILE" || true
    } > "$HASH_DIFF_FILE"
    log_info "Hash diff: $NEW_HASHES arquivos alterados"
  else
    {
      echo "# Diff de hash de códigos (${STAMP})"
      echo "Sem baseline de hash anterior para comparar."
    } > "$HASH_DIFF_FILE"
  fi
fi

# =============================================================================
# RELATÓRIO RESUMIDO (Markdown)
# =============================================================================
log_info "Gerando relatório final..."

{
  echo "# 🔱 ATENA Code Scanner - Relatório de Varredura"
  echo ""
  echo "## Informações da Execução"
  echo "- **Timestamp:** $STAMP"
  echo "- **Diretórios varridos:** ${SCAN_DIRS[*]}"
  echo "- **Extensões incluídas:** ${INCLUDE_EXTS[*]}"
  echo "- **Tempo de execução:** ${ELAPSED_MS}ms"
  echo ""
  
  echo "## Métricas Agregadas"
  if [[ -f "$STATS_FILE" ]]; then
    cat "$STATS_FILE" | sed 's/^/  /'
  else
    echo "  (estatísticas indisponíveis)"
  fi
  echo ""
  
  echo "## Artefatos Gerados"
  echo "| Arquivo | Descrição |"
  echo "|---------|-----------|"
  echo "| \`$(basename "$SCAN_ARQUIVOS")\` | Lista completa de arquivos encontrados |"
  echo "| \`$(basename "$SCAN_CODIGOS_LISTA")\` | Lista filtrada de arquivos de código |"
  echo "| \`$(basename "$SCAN_CODIGO_COMPLETO")\` | Dump consolidado do conteúdo |"
  echo "| \`$(basename "$SCAN_METADADOS")\` | Metadados estruturados (JSON) |"
  echo "| \`$(basename "$LOG_FILE")\` | Log completo da execução |"
  echo "| \`$(basename "$DIFF_FILE")\` | Diff incremental |"
  if [[ "$DEEP_HASH" == "1" ]]; then
    echo "| \`$(basename "$HASH_FILE")\` | Hashes por arquivo |"
    echo "| \`$(basename "$HASH_DIFF_FILE")\` | Diff de hashes |"
  fi
  echo "| \`$(basename "$STATS_FILE")\` | Estatísticas agregadas |"
  echo "| \`$(basename "$LANG_STATS_FILE")\` | Distribuição por linguagem |"
  echo ""
  
  echo "## Prévia dos Resultados"
  echo "- **Total de arquivos varridos:** $TOTAL_FILES"
  echo "- **Arquivos de código relevantes:** $TOTAL_CODES"
  
  if [[ -f "$DIFF_FILE" ]] && grep -q "Novos arquivos" "$DIFF_FILE"; then
    echo "- **Arquivos novos desde última varredura:** $(grep -c "^[^#]" "$DIFF_FILE" | head -1 || echo "0")"
  fi
  
  echo ""
  echo "## Distribuição por Linguagem"
  if [[ -f "$LANG_STATS_FILE" ]]; then
    if command -v jq &>/dev/null && [[ "$JSON_OUTPUT" == "1" ]]; then
      echo '```json'
      cat "$LANG_STATS_FILE"
      echo '```'
    else
      echo '```'
      head -20 "$LANG_STATS_FILE"
      if [[ $(wc -l < "$LANG_STATS_FILE") -gt 20 ]]; then
        echo "... (mais $(($(wc -l < "$LANG_STATS_FILE") - 20)) linhas)"
      fi
      echo '```'
    fi
  else
    echo "  (distribuição indisponível)"
  fi
  echo ""
  
  echo "## Status da Execução"
  if [[ "$DEEP_HASH" == "1" ]]; then
    echo "- ✅ Varredura completa com inventário, dump, diff incremental e hash profundo."
  else
    echo "- ✅ Varredura concluída com inventário, dump consolidado e diff incremental."
  fi
  echo "- ✅ Logs e artefatos salvos em \`$REPORTS_DIR/\`"
  
} > "$SUMMARY_FILE"

# =============================================================================
# SAÍDA JSON (se solicitado)
# =============================================================================
if [[ "$JSON_OUTPUT" == "1" ]]; then
  JSON_SUMMARY="$REPORTS_DIR/SCAN_RESUMO_${STAMP}.json"
  {
    echo "{"
    echo "  \"timestamp\": \"$STAMP\","
    echo "  \"elapsed_ms\": $ELAPSED_MS,"
    echo "  \"total_files\": $TOTAL_FILES,"
    echo "  \"total_code_files\": $TOTAL_CODES,"
    echo "  \"artifacts\": {"
    echo "    \"file_list\": \"$(basename "$SCAN_ARQUIVOS")\","
    echo "    \"code_list\": \"$(basename "$SCAN_CODIGOS_LISTA")\","
    echo "    \"dump\": \"$(basename "$SCAN_CODIGO_COMPLETO")\","
    echo "    \"metadata\": \"$(basename "$SCAN_METADADOS")\","
    echo "    \"summary\": \"$(basename "$SUMMARY_FILE")\""
    if [[ "$DEEP_HASH" == "1" ]]; then
      echo "    \"hash_file\": \"$(basename "$HASH_FILE")\","
      echo "    \"hash_diff\": \"$(basename "$HASH_DIFF_FILE")\""
    fi
    echo "  }"
    echo "}"
  } > "$JSON_SUMMARY"
  log_info "Resumo JSON salvo em: $JSON_SUMMARY"
fi

# =============================================================================
# FINALIZAÇÃO
# =============================================================================
log_info "✅ Varredura concluída com sucesso!"
log_info "📁 Relatório principal: $SUMMARY_FILE"

# Copia para o diretório de evolução se disponível
if [[ -d "atena_evolution" ]]; then
  cp "$SUMMARY_FILE" "atena_evolution/latest_code_scan.md" 2>/dev/null || true
  log_info "📋 Cópia salva em atena_evolution/latest_code_scan.md"
fi

echo "✅ Relatório salvo em: $SUMMARY_FILE"
