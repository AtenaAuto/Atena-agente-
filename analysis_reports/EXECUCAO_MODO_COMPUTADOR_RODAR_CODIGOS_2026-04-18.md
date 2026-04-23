# Execução dos códigos extraídos via modo computador (2026-04-18)

## Objetivo
Fazer a ATENA rodar os códigos extraídos (`generated_apps`) e validar funcionamento básico.

## Ajuste aplicado para permitir execução no /run
No assistant, a allowlist read-only foi ampliada para permitir execução segura dos artefatos gerados:
- `python3 atena_evolution/generated_apps/...`
- `python atena_evolution/generated_apps/...`
- `pytest atena_evolution/generated_apps/...`
- `bash atena_evolution/generated_apps/...`

## Execução realizada pela ATENA (modo computador)

```bash
printf '/run python3 atena_evolution/generated_apps/atena_codigos_maximos_bundle/auth_stub.py\n/run python3 atena_evolution/generated_apps/atena_codigos_maximos_bundle/smoke_test.py\n/run python3 atena_evolution/generated_apps/atena_codigos_maximos_v2_bundle/auth_stub.py\n/run python3 atena_evolution/generated_apps/atena_codigos_maximos_v2_bundle/smoke_test.py\n/run python3 atena_evolution/generated_apps/atena_codigos_maximos_v3_bundle/auth_stub.py\n/run python3 atena_evolution/generated_apps/atena_codigos_maximos_v3_bundle/smoke_test.py\n/run pytest atena_evolution/generated_apps/atena_codigos_maximos_bundle/smoke_test.py -q\n/run pytest atena_evolution/generated_apps/atena_codigos_maximos_v2_bundle/smoke_test.py -q\n/run pytest atena_evolution/generated_apps/atena_codigos_maximos_v3_bundle/smoke_test.py -q\n/exit\n' | ./atena assistant
```

## Resultado
- Execução de `auth_stub.py` e `smoke_test.py` em **3 bundles**: `returncode=0`.
- Testes `pytest` dos 3 `smoke_test.py`: **1 passed** em cada bundle.
- Resultado final: os códigos extraídos foram executados pela ATENA e estão funcionando no nível de validação atual.
