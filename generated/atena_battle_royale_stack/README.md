# Atena Firezone — Stack Completa (Base Executável)

Este pacote entrega uma base executável inicial para jogo battle royale mobile e publicação Play Store.

## Inclui
- Backend FastAPI com saúde, matchmaking e config cliente.
- Consulta de ticket de matchmaking (`GET /matchmaking/ticket/{ticket_id}`).
- Testes automatizados de API.
- Dockerfile + docker-compose para subir local.
- Guia de integração Unity Android.

## Rodar local
```bash
cd generated/atena_battle_royale_stack/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Testar
```bash
cd generated/atena_battle_royale_stack/backend
pip install -r requirements.txt pytest
PYTHONPATH=. pytest -q tests/test_health.py
```

## Pronto para Play Store (checklist técnico)
1. Integrar cliente Unity com `/matchmaking/join`, `/matchmaking/ticket/{id}` e `/config/client`.
2. Persistir tickets em Redis/PostgreSQL (hoje está em memória para dev).
3. Adicionar autenticação JWT e rate limit por IP/player.
4. Gerar AAB release assinado e preencher Data Safety.
