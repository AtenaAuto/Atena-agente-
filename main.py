"""Minimal FastAPI app for Vercel runtime stability."""

from fastapi import FastAPI

app = FastAPI(title="ATENA API", version="1.0.0")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "atena", "status": "ok"}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
