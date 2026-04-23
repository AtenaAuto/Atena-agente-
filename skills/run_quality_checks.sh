#!/usr/bin/env bash
# scripts/run_quality_checks.sh
# Script para executar todas as verificações de qualidade

set -e  # Parar em caso de erro

echo "🔍 Iniciando verificações de qualidade ATENA..."
echo "================================================"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contador de falhas
FAILURES=0

# Função para printar status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        ((FAILURES++))
    fi
}

# 1. Verificar formatação com Black
echo ""
echo "📝 Verificando formatação com Black..."
if black --check core/ modules/ protocols/ 2>/dev/null; then
    print_status 0 "Black: Código formatado corretamente"
else
    print_status 1 "Black: Código precisa formatação"
    echo "   Execute: black core/ modules/ protocols/"
fi

# 2. Verificar imports com isort
echo ""
echo "📦 Verificando imports com isort..."
if isort --check-only core/ modules/ protocols/ 2>/dev/null; then
    print_status 0 "isort: Imports organizados"
else
    print_status 1 "isort: Imports precisam organização"
    echo "   Execute: isort core/ modules/ protocols/"
fi

# 3. Linting com flake8
echo ""
echo "🔎 Executando linting com flake8..."
if flake8 core/ modules/ protocols/ --count --max-line-length=100 --ignore=E203,W503 2>/dev/null; then
    print_status 0 "flake8: Sem problemas detectados"
else
    print_status 1 "flake8: Problemas detectados"
fi

# 4. Linting com pylint
echo ""
echo "🔍 Executando linting com pylint..."
if pylint core/ modules/ --fail-under=6.0 --disable=C0111,C0103 2>/dev/null; then
    print_status 0 "pylint: Score aceitável (>6.0)"
else
    print_status 1 "pylint: Score baixo (<6.0)"
fi

# 5. Type checking com mypy
echo ""
echo "🔤 Verificando tipos com mypy..."
if mypy core/ modules/ --ignore-missing-imports --no-error-summary 2>/dev/null; then
    print_status 0 "mypy: Tipos corretos"
else
    print_status 1 "mypy: Problemas de tipo detectados"
fi

# 6. Security scan com bandit
echo ""
echo "🔐 Executando scan de segurança com bandit..."
if bandit -r core/ modules/ protocols/ -ll 2>/dev/null; then
    print_status 0 "bandit: Sem problemas de segurança"
else
    print_status 1 "bandit: Problemas de segurança detectados"
fi

# 7. Executar testes
echo ""
echo "🧪 Executando testes..."
if pytest tests/ -v --tb=short 2>/dev/null; then
    print_status 0 "pytest: Todos os testes passaram"
else
    print_status 1 "pytest: Alguns testes falharam"
fi

# 8. Verificar cobertura de código
echo ""
echo "📊 Verificando cobertura de código..."
if pytest tests/ --cov=core --cov=modules --cov-report=term-missing --cov-fail-under=60 2>/dev/null; then
    print_status 0 "coverage: Cobertura >60%"
else
    print_status 1 "coverage: Cobertura <60%"
fi

# Resumo final
echo ""
echo "================================================"
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ Todas as verificações passaram!${NC}"
    echo "🚀 Código pronto para commit/push"
    exit 0
else
    echo -e "${RED}❌ $FAILURES verificação(ões) falharam${NC}"
    echo "⚠️  Corrija os problemas antes de fazer commit"
    exit 1
fi
