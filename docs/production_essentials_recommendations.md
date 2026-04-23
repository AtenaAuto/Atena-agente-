# Essentials recomendados para ATENA em produção

Este documento prioriza o que ainda vale criar para transformar o `production-center` em uma base robusta de operação real.

## 1) Observabilidade + SLO (prioridade máxima)

- Definir SLOs por fluxo crítico (latência p95/p99, taxa de erro e disponibilidade).
- Criar budget de erro e alertas (warning/critical) por tenant e por comando.
- Expor métricas em endpoint único (ex.: `/metrics`) e padronizar eventos de auditoria.

**Entregável mínimo:** dashboard com 3 painéis (saúde, custo, incidentes) e alertas automáticos.

## 2) Segurança e governança enterprise

- RBAC evoluído para ABAC (atributos de tenant, ambiente, risco e horário).
- Secrets management com rotação automática e trilha de auditoria.
- Políticas de aprovação por risco (low/medium/high) para ações destrutivas.

**Entregável mínimo:** política de acesso versionada + trilha de auditoria imutável.

## 3) Resiliência operacional

- Retry com backoff e circuit breaker para chamadas externas.
- Idempotência para comandos críticos (evitar execução duplicada).
- Dead-letter queue para jobs falhos e reprocessamento seguro.

**Entregável mínimo:** runbook de incidentes + testes de falha de provider.

## 4) Qualidade contínua (CI/CD)

- Gate de release com E2E reais (`onboarding-run` e `quality-score`).
- Contratos de JSON (schema validation) para saída dos comandos CLI.
- Testes de regressão para guardrails e políticas de acesso.

**Entregável mínimo:** pipeline com estágio `production-center-smoke` bloqueando merge em falha.

## 5) Multi-tenant completo

- Quotas por tenant (requests/minuto, jobs concorrentes, armazenamento).
- Isolamento lógico/físico de dados por organização.
- Relatórios por tenant (uso, custo, incidentes, ações negadas).

**Entregável mínimo:** enforcement central de quota + relatório mensal por tenant.

## 6) Catálogo de skills com ciclo de vida

- Versionamento semântico de skills e compatibilidade declarada.
- Fluxo de aprovação/publicação/rollback de skill.
- Assinatura e validação de integridade antes da instalação.

**Entregável mínimo:** `skill promote` + `skill rollback` com auditoria.

## 7) Custos e FinOps

- Metadados de custo por execução e por perfil.
- Alertas de anomalia de custo.
- Política de fallback (heavy -> light) quando estourar budget.

**Entregável mínimo:** painel de custo diário por tenant e por comando.

## Roadmap sugerido (30/60/90 dias)

### 30 dias
- SLO + alertas básicos.
- Gate E2E no CI.
- Auditoria imutável para ações críticas.

### 60 dias
- ABAC + quotas por tenant.
- Runbooks + drill de incidente.
- Contratos JSON para todos os comandos do `production-center`.

### 90 dias
- Marketplace de skills com assinatura e rollback.
- FinOps automatizado com alertas de anomalia.
- Relatórios executivos mensais de confiabilidade e custo.

## Próximos incrementos técnicos sugeridos

1. Subcomando `slo-check` no `production-center`.
2. Subcomando `incident-drill` para simulação de falhas.
3. Subcomando `tenant-report --month YYYY-MM`.
4. Subcomando `skill-rollback --name X --to-version Y`.
5. `quality-score` com baseline histórico e tendência.
