#!/usr/bin/env python3
"""Gera e executa scripts Python locais no terminal da ATENA.

Este módulo existe para o operador poder pedir explicitamente:
"ATENA, faça um script Python no terminal" sem depender de LLM ou de
execução arbitrária de código recebido do usuário.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "atena_evolution" / "terminal_scripts"


@dataclass(frozen=True)
class TerminalPythonScriptResult:
    """Resultado da criação e execução de um script Python local."""

    status: str
    script_path: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "script_path": self.script_path,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _slugify(text: str, fallback: str = "atena_terminal_script") -> str:
    """Cria um nome de arquivo portátil e previsível para o objetivo."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").strip().lower()).strip("_")
    return (slug or fallback)[:60]


def _select_script_kind(goal: str) -> str:
    """Classifica o tipo de script determinístico que melhor atende ao pedido."""
    lower_goal = goal.lower()
    dashboard_terms = (
        "app",
        "dashboard",
        "html",
        "interface",
        "pagina",
        "página",
        "relatorio",
        "relatório",
        "site",
        "web",
    )
    if any(term in lower_goal for term in dashboard_terms):
        return "dashboard_app"
    return "json_report"


def build_python_script_source(goal: str) -> str:
    """Retorna código Python seguro e determinístico para o script solicitado."""
    clean_goal = (goal or "criar script Python no terminal").strip()
    generated_at = datetime.now(timezone.utc).isoformat()
    script_kind = _select_script_kind(clean_goal)
    template = '''#!/usr/bin/env python3
"""Script Python gerado pela ATENA para execução no terminal."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


GOAL = __GOAL_REPR__
GENERATED_AT_UTC = __GENERATED_AT_REPR__
SCRIPT_KIND = __SCRIPT_KIND_REPR__


def _write_dashboard_app() -> list[str]:
    """Cria um mini dashboard estático e retorna os arquivos criados."""
    artifact_dir = Path(__file__).with_suffix("")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    data = {
        "goal": GOAL,
        "status": "ready",
        "created_at_utc": created_at,
        "cards": [
            {"title": "Plano", "value": "Objetivo normalizado e pronto para evoluir"},
            {"title": "Artefatos", "value": "HTML, CSS, JS, JSON e README"},
            {"title": "Execução", "value": "Tudo criado localmente pelo terminal"},
        ],
        "next_steps": [
            "abrir index.html no navegador",
            "editar data.json com métricas reais",
            "versionar o artefato se ele virar produto",
        ],
    }
    html = f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>ATENA Terminal App</title>
  <link rel=\"stylesheet\" href=\"style.css\" />
</head>
<body>
  <main class=\"shell\">
    <section class=\"hero\">
      <p class=\"eyebrow\">Criado pela ATENA no terminal</p>
      <h1>{data['goal']}</h1>
      <p>Mini aplicação estática gerada e executada por um script Python local.</p>
    </section>
    <section class=\"grid\" id=\"cards\"></section>
    <section class=\"panel\">
      <h2>Próximos passos</h2>
      <ol id=\"steps\"></ol>
    </section>
  </main>
  <script src=\"app.js\"></script>
</body>
</html>
"""
    css = """:root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top, #214, #07111f 55%); color: #f8fbff; }
.shell { width: min(980px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0; }
.hero, .panel, .card { border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.08); border-radius: 24px; padding: 24px; box-shadow: 0 24px 80px rgba(0,0,0,.28); }
.eyebrow { color: #7ee7ff; text-transform: uppercase; letter-spacing: .16em; font-size: .8rem; font-weight: 800; }
h1 { font-size: clamp(2rem, 6vw, 4.5rem); line-height: .95; margin: 0 0 16px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 16px 0; }
.card h2 { margin: 0 0 8px; color: #ffe082; }
li { margin: 8px 0; }
"""
    js = """async function main() {
  const response = await fetch('./data.json');
  const data = await response.json();
  document.querySelector('#cards').innerHTML = data.cards.map(card => `
    <article class=\"card\"><h2>${card.title}</h2><p>${card.value}</p></article>
  `).join('');
  document.querySelector('#steps').innerHTML = data.next_steps.map(step => `<li>${step}</li>`).join('');
}
main().catch(error => console.error('ATENA app error', error));
"""
    readme = f"""# ATENA Terminal App

Objetivo: {GOAL}

Arquivos criados automaticamente pelo script Python local:

- `index.html`: interface estática.
- `style.css`: visual responsivo.
- `app.js`: carregamento de dados.
- `data.json`: conteúdo estruturado.

Abra `index.html` para visualizar a entrega.
"""
    files = {
        "index.html": html,
        "style.css": css,
        "app.js": js,
        "data.json": json.dumps(data, ensure_ascii=False, indent=2) + "\\n",
        "README.md": readme,
    }
    created_files = []
    for filename, content in files.items():
        path = artifact_dir / filename
        path.write_text(content, encoding="utf-8")
        created_files.append(str(path))
    return created_files


def main() -> int:
    created_files: list[str] = []
    next_step = "Edite este arquivo para transformar o exemplo em automação real."
    if SCRIPT_KIND == "dashboard_app":
        created_files = _write_dashboard_app()
        next_step = "Abra o index.html gerado para visualizar a aplicação criada pela ATENA."

    payload = {
        "status": "ok",
        "message": "ATENA executou um script Python no terminal com sucesso.",
        "goal": GOAL,
        "script_kind": SCRIPT_KIND,
        "generated_at_utc": GENERATED_AT_UTC,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "created_files": created_files,
        "next_step": next_step,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
    return (
        template.replace("__GOAL_REPR__", repr(clean_goal))
        .replace("__GENERATED_AT_REPR__", repr(generated_at))
        .replace("__SCRIPT_KIND_REPR__", repr(script_kind))
    )


def create_and_run_terminal_python_script(
    goal: str = "criar script Python no terminal",
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    *,
    run: bool = True,
) -> TerminalPythonScriptResult:
    """Cria um script Python em disco e, por padrão, executa no terminal."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = out_dir / f"{_slugify(goal)}.py"
    script_path.write_text(build_python_script_source(goal), encoding="utf-8")
    script_path.chmod(0o755)

    command = [sys.executable, str(script_path)]
    if not run:
        return TerminalPythonScriptResult(
            status="created",
            script_path=str(script_path),
            command=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return TerminalPythonScriptResult(
        status="ok" if completed.returncode == 0 else "error",
        script_path=str(script_path),
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cria e executa um script Python simples da ATENA")
    parser.add_argument("goal", nargs="*", help="Objetivo do script Python a ser criado")
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Diretório onde o script será salvo"
    )
    parser.add_argument("--no-run", action="store_true", help="Apenas cria o arquivo, sem executar")
    args = parser.parse_args(argv)

    goal = " ".join(args.goal).strip() or "criar script Python no terminal"
    result = create_and_run_terminal_python_script(goal, args.output_dir, run=not args.no_run)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.returncode == 0 else result.returncode


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
