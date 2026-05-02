# ATENA Endpoint Readiness (Computadores de Usuários)

## Resultado
- **Status geral:** `NOT_READY` para operação completa de atuadores de computador em ambientes sem dependências desktop.
- **Data:** 2026-05-02 (UTC)

## Checklist de dependências críticas
- `pyautogui` (automação mouse/teclado): **faltando**
- `pynput` (hooks de input): **faltando**
- `PIL` / Pillow (captura/processamento de imagem): **faltando**
- `pytesseract` (OCR): **faltando**
- `psutil` (telemetria): **ok**

## Testes de regressão de agentes
- `tests/unit/test_computer_actuator.py`: **passou**
- `tests/unit/test_terminal_assistant_internet_flow.py`: **passou**

## Conclusão prática
Atena está funcional para fluxos de terminal e internet, porém para trabalhar no computador de usuários (automação real de UI/OCR) é necessário instalar dependências desktop no host-alvo.

## Script de auditoria
Use:

```bash
./scripts/audit_agent_endpoint_readiness.sh
```

O script valida módulos críticos e roda testes-chave de agentes antes de marcar `READY`.

## Instalador de prontidão (novo)
Para preparar um endpoint automaticamente:

```bash
./setup/install_endpoint_readiness.sh --apply
```

Para apenas verificar dependências sem instalar:

```bash
./setup/install_endpoint_readiness.sh --check
```
