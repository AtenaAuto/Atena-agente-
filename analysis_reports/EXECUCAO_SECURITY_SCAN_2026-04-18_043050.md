# Execução Security Scan (scanner ajustado para achar vulnerabilidades)

Data: 2026-04-18 (UTC)

## Resultado
- Status final: `warn`
- Escopo: `system`

## O que o scanner achou
- `secret_scan`: `clean` (nenhum vazamento explícito detectado)
- `world_writable_count`: `0`
- `suid_count`: `12`
- `code_marker_count`: `190`
- `high_risk_marker_count`: `32`

## Finding principal
- Severidade: `medium`
- Categoria: `code_pattern`
- Mensagem: foram encontrados 32 marcadores de alto risco (`eval/exec/os.system/subprocess`) em arquivos de código.
- Artefato de evidência: `SCAN_SECURITY_CODE_MARKERS_2026-04-18_043050.txt`

## Conclusão
O scanner agora não só executa os comandos de coleta, como também classifica achados e retorna `warn/fail` quando encontra sinais reais de risco.
