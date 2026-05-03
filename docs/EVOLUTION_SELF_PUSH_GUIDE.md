# ATENA Evolution Self-Push Guide

## Objetivo
Permitir que a ATENA rode gate de evolução e tente `push` da branch atual de forma segura.

## Script
- `scripts/evolution_self_push.sh`

## Fluxo
1. (Opcional) roda `scripts/evolution_go_no_go.sh`.
2. Verifica branch atual.
3. Verifica se remote existe.
4. Executa `git push` (ou `--dry-run`).

## Variáveis
- `ATENA_PUSH_DRY_RUN=1` (default): não faz push real.
- `ATENA_RUN_GO_NO_GO=1` (default): executa gate antes do push.
- `ATENA_PUSH_REMOTE=origin` (default): remote alvo.

## Exemplos
```bash
# Simular push
ATENA_PUSH_DRY_RUN=1 bash scripts/evolution_self_push.sh

# Push real (somente quando credenciais e remote estiverem configurados)
ATENA_PUSH_DRY_RUN=0 ATENA_RUN_GO_NO_GO=1 bash scripts/evolution_self_push.sh
```
