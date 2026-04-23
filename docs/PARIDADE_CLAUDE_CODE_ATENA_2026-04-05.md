# Paridade Atena vs Claude Code — 2026-04-05

## Atena já faz
- Assistente terminal com comandos operacionais (`/task`, `/plan`, `/run`, `/review`, `/commit`).
- Modo Kyros para prontidão rápida e smoke controlado.
- Evolução autônoma com telemetria e recomendações.

## O que faltava para ficar mais próxima do Claude Code
- Saída **estruturada por padrão de execução técnica** (objetivo, plano, comandos, validação e rollback) no fluxo de tarefa e planejamento.

## O que foi adicionado nesta rodada
- Novo comando no assistant: `/claude-mode [on|off|status]`.
- Quando ativado, `/task` e `/plan` passam a usar prompt estruturado estilo Claude Code com seções obrigatórias:
  1. Objetivo
  2. Plano técnico
  3. Comandos exatos
  4. Código
  5. Validação
  6. Riscos e rollback

## Como usar
```bash
./atena assistant
/claude-mode on
/task implemente um scanner de segurança para secrets no repositório
/plan entregar versão 1 com testes e relatório
```

## Conclusão
Atena ainda não é 100% igual ao Claude Code, mas agora ficou **mais próxima em UX de execução técnica guiada**, com respostas mais acionáveis e operacionais no assistant.
