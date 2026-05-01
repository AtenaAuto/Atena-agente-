#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# 🔱 ATENA Ω - Push to Main Script v3.0
# Script avançado para push seguro ao branch main com validações e rollback
# =============================================================================

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Configurações padrão
RUN_ATENA=false
RUN_CODE_SCAN=false
RUN_TESTS=true
RUN_LINT=true
RUN_SECURITY_SCAN=false
VERBOSE=false
DRY_RUN=false
FORCE=false
TENANT="empresa-alpha"
GOAL="planejar migração; validar risco; executar rollout"
REMOTE="origin"
COMMIT_MESSAGE="chore: atualizar Atena antes do push"
BRANCH_NAME="main"
BACKUP_BRANCH=""
MAX_RETRIES=3
RETRY_DELAY=5

# Arquivos e diretórios
REPORT_DIR="analysis_reports/push_reports"
BACKUP_DIR="atena_evolution/backups/pre_push"

# =============================================================================
= Funções de Utilitário
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $*"
    fi
}

log_success() {
    echo -e "${GREEN}✅${NC} $*"
}

log_failure() {
    echo -e "${RED}❌${NC} $*"
}

print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════════════╗"
    echo "  ║                    🔱 ATENA Ω - Push to Main                       ║"
    echo "  ║                       v3.0 - Advanced Push                        ║"
    echo "  ╚═══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_separator() {
    echo -e "${CYAN}─────────────────────────────────────────────────────────────────${NC}"
}

# =============================================================================
= Funções de Validação
# =============================================================================

check_git_repo() {
    log_debug "Verificando se está em um repositório git..."
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "Não está em um repositório git"
        exit 1
    fi
    log_debug "Repositório git encontrado"
}

check_git_clean() {
    log_debug "Verificando estado do repositório..."
    if [[ -n "$(git status --porcelain)" ]]; then
        log_warn "Há mudanças não commitadas no repositório"
        if [[ "$FORCE" == "true" ]]; then
            log_warn "FORCE ativado - continuando mesmo com mudanças"
        else
            log_error "Commit ou stash as mudanças antes de prosseguir (ou use --force)"
            return 1
        fi
    fi
    return 0
}

check_remote_branch() {
    local remote="$1"
    local branch="$2"
    log_debug "Verificando se branch $branch existe no remote $remote..."
    
    if git ls-remote --heads "$remote" "$branch" | grep -q "$branch"; then
        log_debug "Branch $branch existe no remote"
        return 0
    else
        log_warn "Branch $branch não existe no remote $remote"
        return 1
    fi
}

check_local_branch() {
    local branch="$1"
    log_debug "Verificando branch local $branch..."
    
    if git show-ref --verify --quiet "refs/heads/$branch"; then
        log_debug "Branch local $branch existe"
        return 0
    else
        log_debug "Branch local $branch não existe"
        return 1
    fi
}

# =============================================================================
# Funções de Backup e Rollback
# =============================================================================

create_backup_branch() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    BACKUP_BRANCH="backup/pre_push_${timestamp}"
    
    log_info "Criando branch de backup: $BACKUP_BRANCH"
    git branch "$BACKUP_BRANCH"
    log_success "Backup criado: $BACKUP_BRANCH"
}

restore_from_backup() {
    if [[ -n "$BACKUP_BRANCH" ]] && git show-ref --verify --quiet "refs/heads/$BACKUP_BRANCH"; then
        log_warn "Restaurando do backup: $BACKUP_BRANCH"
        git reset --hard "$BACKUP_BRANCH"
        log_success "Restauração concluída"
    else
        log_error "Nenhum backup disponível para restauração"
    fi
}

save_pre_push_state() {
    local state_file="$BACKUP_DIR/pre_push_state_$(date +%Y%m%d_%H%M%S).json"
    mkdir -p "$BACKUP_DIR"
    
    cat > "$state_file" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "branch": "$(git branch --show-current)",
    "commit": "$(git rev-parse HEAD)",
    "commit_message": "$COMMIT_MESSAGE",
    "remote": "$REMOTE",
    "tenant": "$TENANT",
    "goal": "$GOAL"
}
EOF
    log_debug "Estado pré-push salvo em: $state_file"
}

# =============================================================================
# Funções de Validação de Código
# =============================================================================

run_code_scan() {
    log_info "🔍 Executando varredura de código..."
    
    local scan_report="$REPORT_DIR/code_scan_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p "$REPORT_DIR"
    
    if [[ -f "scripts/run_computer_mode_code_scan.sh" ]]; then
        bash scripts/run_computer_mode_code_scan.sh --deep-hash > "$scan_report" 2>&1
        
        if grep -q "ERRO" "$scan_report" || grep -q "❌" "$scan_report"; then
            log_warn "⚠️ Possíveis problemas encontrados na varredura de código"
            if [[ "$FORCE" != "true" ]]; then
                log_error "Corrija os problemas ou use --force"
                return 1
            fi
        else
            log_success "✅ Varredura de código OK"
        fi
    else
        log_warn "Script de varredura de código não encontrado"
    fi
    
    return 0
}

run_tests() {
    log_info "🧪 Executando testes..."
    
    local test_report="$REPORT_DIR/test_report_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p "$REPORT_DIR"
    
    if command -v pytest &> /dev/null; then
        if pytest tests/ -v --tb=short --maxfail=5 > "$test_report" 2>&1; then
            log_success "✅ Todos os testes passaram"
            return 0
        else
            log_error "❌ Alguns testes falharam"
            tail -50 "$test_report"
            return 1
        fi
    else
        log_warn "pytest não encontrado, pulando testes"
        return 0
    fi
}

run_lint() {
    log_info "🔍 Executando linting..."
    
    local lint_report="$REPORT_DIR/lint_report_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p "$REPORT_DIR"
    
    local lint_errors=0
    
    # Ruff
    if command -v ruff &> /dev/null; then
        if ! ruff check core/ modules/ protocols/ > "$lint_report" 2>&1; then
            log_warn "⚠️ Ruff encontrou problemas"
            ((lint_errors++))
        fi
    fi
    
    # Black
    if command -v black &> /dev/null; then
        if ! black --check core/ modules/ protocols/ >> "$lint_report" 2>&1; then
            log_warn "⚠️ Black encontrou problemas de formatação"
            ((lint_errors++))
        fi
    fi
    
    # MyPy
    if command -v mypy &> /dev/null; then
        if ! mypy core/ modules/ --ignore-missing-imports >> "$lint_report" 2>&1; then
            log_warn "⚠️ MyPy encontrou problemas de tipagem"
            ((lint_errors++))
        fi
    fi
    
    if [[ $lint_errors -gt 0 ]]; then
        log_warn "⚠️ Encontrados $lint_errors problemas de linting"
        if [[ "$FORCE" != "true" ]]; then
            log_error "Corrija os problemas ou use --force"
            return 1
        fi
    else
        log_success "✅ Linting OK"
    fi
    
    return 0
}

run_security_scan() {
    log_info "🔒 Executando scan de segurança..."
    
    local security_report="$REPORT_DIR/security_scan_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p "$REPORT_DIR"
    
    # Secret scan
    if [[ -f "core/secret_scanner.py" ]]; then
        python3 core/secret_scanner.py --root . > "$security_report" 2>&1
        
        if grep -q "❌" "$security_report"; then
            log_warn "⚠️ Possíveis segredos encontrados"
            if [[ "$FORCE" != "true" ]]; then
                log_error "Remova os segredos ou use --force"
                return 1
            fi
        else
            log_success "✅ Scan de segurança OK"
        fi
    else
        log_warn "Secret scanner não encontrado"
    fi
    
    return 0
}

# =============================================================================
# Funções de Execução da ATENA
# =============================================================================

run_atena_mission() {
    log_info "🚀 Executando missão ATENA: enterprise-advanced"
    log_info "   Tenant: $TENANT"
    log_info "   Goal: $GOAL"
    
    local mission_report="$REPORT_DIR/atena_mission_$(date +%Y%m%d_%H%M%S).json"
    mkdir -p "$REPORT_DIR"
    
    if [[ -f "./atena" ]]; then
        if ./atena enterprise-advanced --tenant "$TENANT" --goal "$GOAL" --json > "$mission_report" 2>&1; then
            log_success "✅ Missão ATENA executada com sucesso"
            
            # Extrai score do relatório
            if command -v jq &> /dev/null; then
                local score=$(jq -r '.score // "N/A"' "$mission_report" 2>/dev/null)
                log_info "   Score: $score"
            fi
            return 0
        else
            log_error "❌ Missão ATENA falhou"
            tail -20 "$mission_report"
            return 1
        fi
    else
        log_error "Executável ./atena não encontrado"
        return 1
    fi
}

run_enterprise_mission() {
    log_info "🏢 Executando missão enterprise-advanced..."
    
    local enterprise_report="$REPORT_DIR/enterprise_$(date +%Y%m%d_%H%M%S).json"
    mkdir -p "$REPORT_DIR"
    
    if [[ -f "./atena" ]]; then
        if ./atena enterprise-advanced --tenant "$TENANT" --goal "$GOAL" --full --json > "$enterprise_report" 2>&1; then
            log_success "✅ Missão enterprise concluída"
            return 0
        else
            log_error "❌ Missão enterprise falhou"
            tail -20 "$enterprise_report"
            return 1
        fi
    else
        log_warn "Executável ./atena não encontrado"
        return 0
    fi
}

# =============================================================================
# Funções de Git e Push
# =============================================================================

ensure_main_branch() {
    local branch="$1"
    
    log_info "📌 Garantindo branch $branch..."
    
    if check_local_branch "$branch"; then
        git checkout "$branch"
        log_success "✅ Mudou para branch $branch"
    else
        log_info "Branch $branch não existe localmente, criando..."
        git checkout -b "$branch"
        log_success "✅ Branch $branch criada"
    fi
}

sync_with_remote() {
    local remote="$1"
    local branch="$2"
    
    log_info "🔄 Sincronizando com remote $remote/$branch..."
    
    # Fetch latest changes
    git fetch "$remote" --prune
    
    if check_remote_branch "$remote" "$branch"; then
        # Verifica se há divergência
        local local_commit=$(git rev-parse HEAD)
        local remote_commit=$(git rev-parse "$remote/$branch" 2>/dev/null || echo "")
        
        if [[ "$local_commit" != "$remote_commit" ]]; then
            log_warn "Branch local e remoto divergentes"
            log_info "Local:  $local_commit"
            log_info "Remote: $remote_commit"
            
            # Tenta rebase
            if git rebase "$remote/$branch"; then
                log_success "✅ Rebase bem-sucedido"
            else
                log_error "❌ Falha no rebase"
                git rebase --abort
                return 1
            fi
        else
            log_success "✅ Branch já sincronizada"
        fi
    else
        log_info "Branch $branch não existe no remote, será criada no push"
    fi
    
    return 0
}

commit_changes() {
    local message="$1"
    
    if [[ -n "$(git status --porcelain)" ]]; then
        log_info "📝 Committing changes..."
        git add -A
        git commit -m "$message"
        log_success "✅ Changes committed"
    else
        log_info "No changes to commit"
    fi
}

push_with_retry() {
    local remote="$1"
    local branch="$2"
    local max_retries="$3"
    local retry_delay="$4"
    
    log_info "📤 Push para $remote/$branch..."
    
    for attempt in $(seq 1 $max_retries); do
        log_debug "Tentativa $attempt/$max_retries"
        
        if git push "$remote" "$branch" 2>&1; then
            log_success "✅ Push bem-sucedido"
            return 0
        else
            log_warn "Push falhou (tentativa $attempt)"
            
            if [[ $attempt -lt $max_retries ]]; then
                log_info "Aguardando $retry_delay segundos antes de tentar novamente..."
                sleep "$retry_delay"
                
                # Atualiza antes de tentar novamente
                git fetch "$remote"
                git rebase "$remote/$branch" 2>/dev/null || true
            fi
        fi
    done
    
    log_error "❌ Push falhou após $max_retries tentativas"
    return 1
}

# =============================================================================
# Funções de Relatório
# =============================================================================

generate_push_report() {
    local status="$1"
    local report_file="$REPORT_DIR/push_report_$(date +%Y%m%d_%H%M%S).md"
    mkdir -p "$REPORT_DIR"
    
    cat > "$report_file" << EOF
# 🔱 ATENA Push Report

## Informações Gerais
- **Data:** $(date -Iseconds)
- **Branch:** $BRANCH_NAME
- **Remote:** $REMOTE
- **Status:** $status
- **Commit:** $(git rev-parse HEAD)
- **Commit Message:** $COMMIT_MESSAGE

## Validações Executadas
| Validação | Status |
|-----------|--------|
| Código Scan | $([ "$RUN_CODE_SCAN" = true ] && echo "✅" || echo "⏭️") |
| Testes | $([ "$RUN_TESTS" = true ] && echo "✅" || echo "⏭️") |
| Linting | $([ "$RUN_LINT" = true ] && echo "✅" || echo "⏭️") |
| Segurança | $([ "$RUN_SECURITY_SCAN" = true ] && echo "✅" || echo "⏭️") |

## Missões ATENA
- **Enterprise Advanced:** $([ "$RUN_ATENA" = true ] && echo "✅" || echo "⏭️") | Tenant: $TENANT

## Push Result
- **Push Status:** $status
- **Backup Branch:** ${BACKUP_BRANCH:-N/A}
- **Retries:** $MAX_RETRIES

## Arquivos Alterados
\`\`\`
$(git diff --stat HEAD~1 2>/dev/null || echo "N/A")
\`\`\`

## Próximos Passos
1. Verificar CI/CD pipeline
2. Monitorar logs em produção
3. Executar testes de smoke pós-deploy
EOF
    
    log_info "📄 Relatório gerado: $report_file"
}

# =============================================================================
# Função Principal
# =============================================================================

main() {
    print_banner
    
    # Parse de argumentos adicionais
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --run-atena)
                RUN_ATENA=true
                shift
                ;;
            --run-code-scan)
                RUN_CODE_SCAN=true
                shift
                ;;
            --no-tests)
                RUN_TESTS=false
                shift
                ;;
            --no-lint)
                RUN_LINT=false
                shift
                ;;
            --security-scan)
                RUN_SECURITY_SCAN=true
                shift
                ;;
            --tenant)
                TENANT="$2"
                shift 2
                ;;
            --goal)
                GOAL="$2"
                shift 2
                ;;
            --remote)
                REMOTE="$2"
                shift 2
                ;;
            --commit-message)
                COMMIT_MESSAGE="$2"
                shift 2
                ;;
            --branch)
                BRANCH_NAME="$2"
                shift 2
                ;;
            --max-retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Opção inválida: $1" >&2
                usage
                exit 1
                ;;
        esac
    done
    
    # Validações iniciais
    check_git_repo
    save_pre_push_state
    
    # Criar backup antes de qualquer operação
    create_backup_branch
    
    # Executar missões ATENA (se solicitado)
    if [[ "$RUN_ATENA" == true ]]; then
        if ! run_atena_mission; then
            log_error "Missão ATENA falhou"
            restore_from_backup
            exit 1
        fi
    fi
    
    # Executar validações de código
    if [[ "$RUN_CODE_SCAN" == true ]]; then
        if ! run_code_scan; then
            log_error "Varredura de código falhou"
            restore_from_backup
            exit 1
        fi
    fi
    
    if [[ "$RUN_TESTS" == true ]]; then
        if ! run_tests; then
            log_error "Testes falharam"
            restore_from_backup
            exit 1
        fi
    fi
    
    if [[ "$RUN_LINT" == true ]]; then
        if ! run_lint; then
            log_error "Linting falhou"
            restore_from_backup
            exit 1
        fi
    fi
    
    if [[ "$RUN_SECURITY_SCAN" == true ]]; then
        if ! run_security_scan; then
            log_error "Scan de segurança falhou"
            restore_from_backup
            exit 1
        fi
    fi
    
    # Preparar para push
    ensure_main_branch "$BRANCH_NAME"
    sync_with_remote "$REMOTE" "$BRANCH_NAME"
    commit_changes "$COMMIT_MESSAGE"
    
    # Executar push (ou dry-run)
    if [[ "$DRY_RUN" == true ]]; then
        log_info "DRY RUN: Push seria executado para $REMOTE/$BRANCH_NAME"
        log_info "Commits a serem enviados:"
        git log --oneline "$REMOTE/$BRANCH_NAME..HEAD" 2>/dev/null || git log --oneline -3
        generate_push_report "dry-run"
        log_success "Dry run concluído"
    else
        if push_with_retry "$REMOTE" "$BRANCH_NAME" "$MAX_RETRIES" "$RETRY_DELAY"; then
            generate_push_report "success"
            log_success "✅ Push concluído para $REMOTE/$BRANCH_NAME"
            
            # Limpeza de branches de backup antigos
            if [[ "$FORCE" != "true" ]]; then
                git branch | grep "backup/pre_push_" | head -n -5 | xargs -r git branch -D
            fi
        else
            generate_push_report "failed"
            log_error "❌ Push falhou"
            restore_from_backup
            exit 1
        fi
    fi
    
    # Executar missão enterprise pós-push (opcional)
    if [[ "$RUN_ATENA" == true ]]; then
        run_enterprise_mission
    fi
    
    print_separator
    log_success "Operação concluída com sucesso!"
}

# =============================================================================
# Tratamento de Interrupção
# =============================================================================

cleanup() {
    log_warn "Interrupção detectada. Realizando limpeza..."
    restore_from_backup
    exit 1
}

trap cleanup SIGINT SIGTERM

# =============================================================================
= Execução
# =============================================================================

usage() {
    cat <<'USAGE'
🔱 ATENA Ω - Push to Main Script v3.0

Uso:
  scripts/push_main.sh [opções]

Opções:
  --run-atena                 Executa missão enterprise-advanced antes do push
  --run-code-scan             Executa varredura de código
  --no-tests                  Pula execução de testes
  --no-lint                   Pula linting
  --security-scan             Executa scan de segurança
  --tenant <nome>             Tenant usado com --run-atena (default: empresa-alpha)
  --goal <texto>              Goal usado com --run-atena
  --remote <nome>             Nome do remoto git (default: origin)
  --branch <nome>             Branch alvo (default: main)
  --commit-message <msg>      Mensagem de commit automática
  --max-retries <n>           Número máximo de tentativas de push (default: 3)
  --verbose                   Modo verboso
  --dry-run                   Simula push sem executar
  --force                     Força execução mesmo com avisos
  -h, --help                  Mostra esta ajuda

Exemplos:
  # Push simples
  scripts/push_main.sh

  # Push com validações completas
  scripts/push_main.sh --run-code-scan --security-scan --run-atena

  # Push com tenant específico
  scripts/push_main.sh --run-atena --tenant "acme-corp" --goal "release v3.2"

  # Dry run para verificar o que seria enviado
  scripts/push_main.sh --dry-run --verbose

  # Forçar push mesmo com avisos
  scripts/push_main.sh --force --no-tests

  # Push para branch específica
  scripts/push_main.sh --branch develop --remote upstream

Variáveis de Ambiente:
  ATENA_API_KEY       Chave de API para autenticação
  ATENA_LOG_LEVEL     Nível de log (DEBUG, INFO, WARN, ERROR)

Artefatos Gerados:
  - Relatórios em analysis_reports/push_reports/
  - Backups em atena_evolution/backups/pre_push/
  - Branches de backup: backup/pre_push_*

USAGE
}

# Executar main com todos os argumentos
main "$@"
