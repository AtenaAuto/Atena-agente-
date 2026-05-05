<<<<<<< ours
"""Vercel FastAPI entrypoint for ATENA."""

from core.atena_production_api import app
=======
"""Minimal FastAPI app for Vercel runtime stability."""

from fastapi import FastAPI

app = FastAPI(title="ATENA API", version="1.0.0")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "atena", "status": "ok"}
>>>>>>> theirs


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
