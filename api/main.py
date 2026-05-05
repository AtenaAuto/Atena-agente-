from fastapi import FastAPI
<<<<<<< ours
=======
from fastapi.responses import HTMLResponse
>>>>>>> theirs

app = FastAPI(title="ATENA API", version="1.0.0")


<<<<<<< ours
@app.get("/")
def root() -> dict[str, str]:
    return {"service": "atena", "status": "ok"}
=======
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
>>>>>>> theirs


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
<<<<<<< ours
=======


@app.get("/status")
def status() -> dict[str, str]:
    return {"service": "atena", "status": "ok"}
>>>>>>> theirs
