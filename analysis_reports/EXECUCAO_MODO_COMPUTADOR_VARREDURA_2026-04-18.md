# Execução do modo computador — varredura de informações (2026-04-18)

## Objetivo
Executar novamente o modo computador da ATENA e solicitar varredura do computador em busca de informações úteis para evolução.

## Sessões realizadas no assistant

```bash
printf '/run uname -a\n/run python3 --version\n/run whoami\n/run pwd\n/run df -h\n/run free -h\n/run rg --files | wc -l\n/run ./atena doctor\n/run ./atena learn-status\n/exit\n' | ./atena assistant

printf '/task-exec Varra o computador em busca de informações úteis para evolução da ATENA (saúde do ambiente, estado de memória, qualidade e riscos) e gere relatório com prioridades.\n/exit\n' | ./atena assistant

printf '/device-control varra o computador e liste informações de sistema e arquivos relevantes para evolução --confirm\n/exit\n' | ./atena assistant
```

## Resultado da varredura

### 1) Limites de allowlist no `/run`
- A maior parte dos comandos de sistema foi bloqueada como `comando fora da allowlist` (`returncode=126`).
- Comandos ATENA permitidos e executados com sucesso:
  - `./atena doctor` → `Checks: 6/6 ok`
  - `./atena learn-status` → `Memórias persistidas: 3`

### 2) `task-exec`
- A execução retornou `Task exec: OK`, mas com fallback para plano mínimo.
- Relatório gerado em:
  - `atena_evolution/task_exec_reports/task_exec_20260418_024025.json`
- Comando efetivamente executado no fallback: `./atena doctor`.

### 3) `device-control`
- Execução concluída com `Device control: OK`.
- Relatório salvo em:
  - `atena_evolution/device_control/device_control_20260418_024047_576480.json`
- Ação registrada: `system_status`
- Evidência coletada de sistema: `Linux ... x86_64 GNU/Linux`.

## Utilidade prática para evolução
- **Útil para estado de saúde básico**: confirma ambiente operacional e checks essenciais sem falhas.
- **Útil para governança de segurança**: comprova que o assistant restringe comandos fora da allowlist.
- **Limitado para varredura profunda**: não houve inventário amplo de arquivos/recursos por bloqueios de execução e fallback automático.

## Próximo passo recomendado
Para uma varredura realmente profunda, usar uma missão dedicada com allowlist expandida (somente leitura), exportando inventário de arquivos/métricas em JSON para comparação temporal.
