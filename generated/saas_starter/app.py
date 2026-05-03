from fastapi import FastAPI

app = FastAPI(title="Atena SaaS Starter")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
