# Modo Kyros da Atena

## O que é
O **Kyros** é um modo operacional da Atena focado em **prontidão rápida**, com checagens executáveis no terminal e retorno previsível para automação.

Em vez de rodar toda a stack de evolução, ele atua como uma camada de validação/operacional:
- mostra status imediato do modo;
- roda smoke checks essenciais;
- controla timeout por comando;
- expõe capacidades via CLI.

## O que ele faz (na prática)
Comando base:

```bash
./atena kyros
```

Fluxos principais:

1. **Status operacional**
   - `./atena kyros --status`
   - mostra timestamp UTC e perfis ativos.

2. **Smoke operacional**
   - `./atena kyros --smoke`
   - executa:
     - `./atena doctor`
     - `./atena modules-smoke`

3. **Timeout controlado**
   - `./atena kyros --smoke --timeout 120`
   - define limite por comando no smoke.

4. **Lista de capacidades**
   - `./atena kyros --capabilities`
   - imprime as capacidades operacionais disponíveis do Kyros.

## Códigos de retorno (importante para CI/CD)
- `0`: sucesso
- `2`: smoke incompleto (um ou mais checks falharam)
- `124`: timeout de execução
- `127`: comando não encontrado

## Para que serve no dia a dia
- Pré-check rápido antes de rodar missões pesadas.
- Verificação de saúde em pipelines.
- Diagnóstico operacional com feedback curto e direto.
- Teste de resiliência com timeout controlado.

## Limites do Kyros
- Não substitui as missões profundas de evolução/codex.
- Não é um benchmark de qualidade final do sistema inteiro.
- É uma camada rápida de operação/triagem (gate inicial).
