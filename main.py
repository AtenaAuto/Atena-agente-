"""Vercel FastAPI entrypoint for ATENA."""

from core.atena_production_api import app


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
