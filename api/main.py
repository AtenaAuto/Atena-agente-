<<<<<<< ours
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="ATENA API", version="1.0.0")
STARTED_AT = datetime.now(timezone.utc).isoformat()
RELEASE = os.getenv("ATENA_RELEASE", "dev")
ENVIRONMENT = os.getenv("ATENA_ENV", "production")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Falha inesperada na ATENA API.",
            "request_id": request.headers.get("x-request-id", "n/a"),
        },
    )


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return """
    <!doctype html>
    <html lang="pt-BR">
      <head><meta charset="utf-8"><title>ATENA Dashboard</title></head>
      <body style="font-family:Arial,sans-serif;max-width:720px;margin:40px auto;">
        <h1>🔱 ATENA Dashboard</h1>
        <p>Deploy ativo na Vercel.</p>
        <ul>
          <li><a href="/healthz">/healthz</a></li>
          <li><a href="/status">/status</a></li>
        </ul>
      </body>
    </html>
    """


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def status() -> dict[str, str]:
    return {
        "service": "atena",
        "status": "ok",
        "release": RELEASE,
        "environment": ENVIRONMENT,
        "started_at": STARTED_AT,
    }
=======
"""Compatibility entrypoint for deployments that still route to api/main.py."""

from __future__ import annotations

from api import app as app

__all__ = ["app"]
>>>>>>> theirs
