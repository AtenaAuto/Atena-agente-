# Melhorias de Evolução da ATENA — 2026-04-05

## Execução completa realizada
Comando executado para validar evolução orientada a problema:

```bash
python3 core/main.py --auto --cycles 1 --problem fibonacci
```

## Problema identificado
Na avaliação por problema (sorting/fibonacci), o score dependia estritamente da presença de funções com nomes fixos (`sort` e `fibonacci`).
Em cenários onde o código tinha aliases válidos (`util_fibonacci`, `fib`, `solve`, etc.), a avaliação podia penalizar mutações corretas por incompatibilidade de interface nominal.

## Melhoria aplicada (recomendada e implementada)
Foram adicionados **adapters de interface** no avaliador dos problemas:

- `create_fibonacci_problem()` agora aceita aliases:
  - `util_fibonacci`
  - `fib`
  - `solve`
- `create_sorting_problem()` agora aceita aliases:
  - `util_sort`
  - `sort_list`
  - `quicksort`
  - `solve`

Com isso, mutações semanticamente corretas deixam de receber score 0 apenas por nome de função.

## Resultado mensurável observado
No teste após a correção, o ciclo reportou:

- `Score atual: 70.00`
- `Candidato ... score 100.00`
- `Melhorou: 100.00 > 70.00`
- `Progresso mensurável: score_delta=30.0000`

Ou seja, houve **ganho real de +30 pontos** em um ciclo curto com `--problem fibonacci`.

## Próximas melhorias recomendadas
1. Persistir benchmark A/B por problema (`sorting` e `fibonacci`) com N ciclos fixos.
2. Expor em relatório automático a taxa de ciclos com melhoria (`improvement_rate`).
3. Criar suíte de regressão para validar adapters de interface em novos problemas.
