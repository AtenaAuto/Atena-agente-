#!/usr/bin/env python3
"""Gera um micro-SaaS starter local para demonstração rápida."""

from pathlib import Path

ROOT = Path("generated/saas_starter")

APP_PY = '''from fastapi import FastAPI

app = FastAPI(title="Atena SaaS Starter")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
'''

README = '''# Atena SaaS Starter

Projeto mínimo gerado automaticamente.

## Como rodar

```bash
uvicorn app:app --reload
```

## Endpoint
- `GET /health`
'''


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "app.py").write_text(APP_PY)
    (ROOT / "README.md").write_text(README)
    print(f"SaaS criado em: {ROOT}")


if __name__ == "__main__":
    main()
