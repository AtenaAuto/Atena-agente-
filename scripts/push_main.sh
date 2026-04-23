#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Uso:
  scripts/push_main.sh [opções]

Opções:
  --run-atena                 Executa missão enterprise-advanced antes do push.
  --tenant <nome>             Tenant usado com --run-atena (default: empresa-alpha).
  --goal <texto>              Goal usado com --run-atena.
  --remote <nome>             Nome do remoto git (default: origin).
  --commit-message <msg>      Mensagem de commit automática quando houver mudanças.
  -h, --help                  Mostra esta ajuda.

Exemplos:
  scripts/push_main.sh
  scripts/push_main.sh --run-atena --tenant empresa-alpha --goal "planejar rollout"
USAGE
}

RUN_ATENA=false
TENANT="empresa-alpha"
GOAL="planejar migração; validar risco; executar rollout"
REMOTE="origin"
COMMIT_MESSAGE="chore: atualizar Atena antes do push"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-atena)
      RUN_ATENA=true
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

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ "$RUN_ATENA" == true ]]; then
  ./atena enterprise-advanced --tenant "$TENANT" --goal "$GOAL"
fi

if git show-ref --verify --quiet refs/heads/main; then
  git checkout main
else
  git checkout -b main
fi

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "$COMMIT_MESSAGE"
fi

git push "$REMOTE" main

echo "✅ Push concluído para $REMOTE/main"
