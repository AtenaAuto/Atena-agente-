#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atena Code Module: gera apps/sites/software iniciais de forma autônoma."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Literal

ProjectType = Literal["site", "api", "cli"]
SiteTemplate = Literal["basic", "landing-page", "portfolio", "dashboard", "blog"]


@dataclass
class BuildResult:
    ok: bool
    project_type: str
    project_name: str
    template: str
    output_dir: str
    message: str


class AtenaCodeModule:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.generated_root = self.root / "atena_evolution" / "generated_apps"
        self.generated_root.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        project_type: ProjectType,
        project_name: str,
        template: SiteTemplate = "basic",
    ) -> BuildResult:
        safe_name = "".join(ch for ch in project_name if ch.isalnum() or ch in ("-", "_")).strip("-_")
        if not safe_name:
            return BuildResult(False, project_type, project_name, template, "", "Nome de projeto inválido")

        out = self.generated_root / safe_name
        out.mkdir(parents=True, exist_ok=True)

        if project_type == "site":
            self._build_site(out, safe_name, template)
        elif project_type == "api":
            self._build_api(out, safe_name)
        elif project_type == "cli":
            self._build_cli(out, safe_name)
        else:
            return BuildResult(False, project_type, project_name, template, str(out), "Tipo de projeto inválido")

        return BuildResult(True, project_type, safe_name, template, str(out), "Projeto gerado com sucesso")

    def _build_site(self, out: Path, name: str, template: SiteTemplate) -> None:
        valid_templates: set[str] = {"basic", "landing-page", "portfolio", "dashboard", "blog"}
        chosen = template if template in valid_templates else "basic"

        if chosen == "basic":
            self._build_site_basic(out, name)
            return

        self._build_site_modern(out, name, chosen)

    def _build_site_basic(self, out: Path, name: str) -> None:
        (out / "index.html").write_text(
            dedent(
                f"""\
                <!doctype html>
                <html lang="pt-BR">
                <head>
                  <meta charset="utf-8" />
                  <meta name="viewport" content="width=device-width,initial-scale=1" />
                  <title>{name} — Site gerado pela ATENA</title>
                  <link rel="stylesheet" href="style.css" />
                </head>
                <body>
                  <main>
                    <h1>{name}</h1>
                    <p>Site inicial gerado automaticamente pelo módulo de programação da ATENA.</p>
                    <button id="helloBtn">Testar interação</button>
                    <p id="output"></p>
                  </main>
                  <script src="app.js"></script>
                </body>
                </html>
                """
            ),
            encoding="utf-8",
        )
        (out / "style.css").write_text(
            dedent(
                """\
                body {
                  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
                  background: #0f172a;
                  color: #e2e8f0;
                  display: grid;
                  place-items: center;
                  min-height: 100vh;
                }
                main {
                  max-width: 760px;
                  padding: 24px;
                  border: 1px solid #334155;
                  border-radius: 12px;
                }
                button {
                  padding: 10px 14px;
                  border-radius: 8px;
                  border: none;
                  cursor: pointer;
                }
                """
            ),
            encoding="utf-8",
        )
        (out / "app.js").write_text(
            dedent(
                """\
                const helloBtn = document.getElementById("helloBtn");
                const output = document.getElementById("output");

                helloBtn?.addEventListener("click", () => {
                  if (output) {
                    output.textContent = "✅ ATENA gerou e executou a base do site com sucesso!";
                  }
                });
                """
            ),
            encoding="utf-8",
        )
        self._write_project_readme(out, name, "basic")

    def _build_site_modern(self, out: Path, name: str, template: str) -> None:
        template_titles = {
            "landing-page": "Landing Page",
            "portfolio": "Portfólio",
            "dashboard": "Dashboard",
            "blog": "Blog",
        }
        template_title = template_titles.get(template, "Site Moderno")

        for file in ["index.html", "about.html", "contact.html", "style.css", "app.js"]:
            path = out / file
            if path.exists():
                path.unlink()

        (out / "index.html").write_text(
            dedent(
                f"""\
                <!doctype html>
                <html lang="pt-BR">
                <head>
                  <meta charset="utf-8" />
                  <meta name="viewport" content="width=device-width, initial-scale=1" />
                  <title>{name} • {template_title}</title>
                  <meta name="description" content="Projeto {template_title} gerado automaticamente pela ATENA." />
                  <link rel="stylesheet" href="style.css" />
                </head>
                <body>
                  <header class="topbar">
                    <strong>{name}</strong>
                    <nav>
                      <a href="index.html">Início</a>
                      <a href="about.html">Sobre</a>
                      <a href="contact.html">Contato</a>
                    </nav>
                  </header>

                  <main>
                    <section class="hero">
                      <p class="tag">Template: {template_title}</p>
                      <h1>{name}</h1>
                      <p>Projeto gerado pela ATENA com estrutura pronta para customização rápida.</p>
                      <button id="helloBtn">Testar interação</button>
                      <p id="output" class="output"></p>
                    </section>

                    <section class="cards">
                      <article class="card">
                        <h2>Rápido para iniciar</h2>
                        <p>Comece pelo conteúdo da seção principal e personalize cores e textos.</p>
                      </article>
                      <article class="card">
                        <h2>Estrutura multipágina</h2>
                        <p>Inclui páginas de início, sobre e contato já conectadas via navegação.</p>
                      </article>
                      <article class="card">
                        <h2>Pronto para evolução</h2>
                        <p>Use como base para acoplar API, analytics e deploy em produção.</p>
                      </article>
                    </section>
                  </main>

                  <footer>
                    <small>Gerado por ATENA Code Module · template {template_title}</small>
                  </footer>
                  <script src="app.js"></script>
                </body>
                </html>
                """
            ),
            encoding="utf-8",
        )
        (out / "about.html").write_text(
            dedent(
                f"""\
                <!doctype html>
                <html lang="pt-BR">
                <head>
                  <meta charset="utf-8" />
                  <meta name="viewport" content="width=device-width, initial-scale=1" />
                  <title>Sobre • {name}</title>
                  <link rel="stylesheet" href="style.css" />
                </head>
                <body>
                  <main class="simple-page">
                    <h1>Sobre o projeto</h1>
                    <p><strong>{name}</strong> foi criado automaticamente pelo módulo de programação da ATENA.</p>
                    <p>Template selecionado: <strong>{template_title}</strong>.</p>
                    <a href="index.html">← Voltar para início</a>
                  </main>
                </body>
                </html>
                """
            ),
            encoding="utf-8",
        )
        (out / "contact.html").write_text(
            dedent(
                f"""\
                <!doctype html>
                <html lang="pt-BR">
                <head>
                  <meta charset="utf-8" />
                  <meta name="viewport" content="width=device-width, initial-scale=1" />
                  <title>Contato • {name}</title>
                  <link rel="stylesheet" href="style.css" />
                </head>
                <body>
                  <main class="simple-page">
                    <h1>Contato</h1>
                    <form class="contact-form">
                      <label>Nome <input type="text" placeholder="Seu nome" /></label>
                      <label>Email <input type="email" placeholder="voce@email.com" /></label>
                      <label>Mensagem <textarea rows="4" placeholder="Como podemos ajudar?"></textarea></label>
                      <button type="button">Enviar</button>
                    </form>
                    <a href="index.html">← Voltar para início</a>
                  </main>
                </body>
                </html>
                """
            ),
            encoding="utf-8",
        )
        (out / "style.css").write_text(
            dedent(
                """\
                :root {
                  --bg: #0b1220;
                  --panel: #111a2d;
                  --text: #dbe6ff;
                  --muted: #9db0d8;
                  --brand: #5eead4;
                  --brand-strong: #2dd4bf;
                  --border: #243453;
                }

                * {
                  box-sizing: border-box;
                }

                body {
                  margin: 0;
                  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
                  background: radial-gradient(circle at top right, #13213f, var(--bg));
                  color: var(--text);
                }

                .topbar {
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                  padding: 18px 24px;
                  border-bottom: 1px solid var(--border);
                  background: rgba(9, 14, 26, 0.75);
                  position: sticky;
                  top: 0;
                  backdrop-filter: blur(6px);
                }

                .topbar nav a {
                  color: var(--muted);
                  text-decoration: none;
                  margin-left: 14px;
                }

                .topbar nav a:hover {
                  color: var(--brand);
                }

                main {
                  max-width: 1024px;
                  margin: 0 auto;
                  padding: 32px 20px 48px;
                }

                .hero {
                  background: var(--panel);
                  border: 1px solid var(--border);
                  border-radius: 16px;
                  padding: 28px;
                  margin-bottom: 26px;
                }

                .tag {
                  display: inline-block;
                  font-size: 12px;
                  font-weight: 700;
                  text-transform: uppercase;
                  letter-spacing: 0.06em;
                  color: #09211f;
                  background: var(--brand);
                  border-radius: 999px;
                  padding: 6px 12px;
                }

                h1 {
                  margin: 12px 0 10px;
                  font-size: clamp(2rem, 4vw, 2.8rem);
                }

                p {
                  color: var(--muted);
                  line-height: 1.6;
                }

                .cards {
                  display: grid;
                  gap: 16px;
                  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                }

                .card {
                  background: var(--panel);
                  border: 1px solid var(--border);
                  border-radius: 14px;
                  padding: 18px;
                }

                button {
                  border: none;
                  border-radius: 10px;
                  cursor: pointer;
                  background: var(--brand-strong);
                  color: #03201d;
                  font-weight: 700;
                  padding: 10px 16px;
                }

                .output {
                  min-height: 24px;
                }

                .simple-page {
                  max-width: 720px;
                  margin: 50px auto;
                  background: var(--panel);
                  border: 1px solid var(--border);
                  border-radius: 16px;
                  padding: 28px;
                }

                .contact-form {
                  display: grid;
                  gap: 12px;
                  margin: 18px 0;
                }

                .contact-form label {
                  display: grid;
                  gap: 6px;
                  color: var(--text);
                }

                input,
                textarea {
                  width: 100%;
                  border-radius: 10px;
                  border: 1px solid var(--border);
                  background: #0d1628;
                  color: var(--text);
                  padding: 10px;
                }

                footer {
                  border-top: 1px solid var(--border);
                  padding: 16px 24px 32px;
                  color: var(--muted);
                  text-align: center;
                }
                """
            ),
            encoding="utf-8",
        )
        (out / "app.js").write_text(
            dedent(
                f"""\
                const helloBtn = document.getElementById("helloBtn");
                const output = document.getElementById("output");

                helloBtn?.addEventListener("click", () => {{
                  if (!output) return;
                  output.textContent = "🚀 Projeto {name} ({template_title}) pronto para evoluir!";
                }});
                """
            ),
            encoding="utf-8",
        )
        self._write_project_readme(out, name, template)

    def _write_project_readme(self, out: Path, name: str, template: str) -> None:
        (out / "README.md").write_text(
            dedent(
                f"""\
                # {name}

                Projeto gerado automaticamente pela ATENA.

                - Tipo: site
                - Template: {template}

                ## Como rodar localmente

                Abra `index.html` no navegador.

                ## Próximos passos sugeridos

                1. Personalizar textos, branding e identidade visual.
                2. Integrar formulário com backend/API.
                3. Publicar em um provedor estático (Netlify, Vercel ou GitHub Pages).
                """
            ),
            encoding="utf-8",
        )

    def _build_api(self, out: Path, name: str) -> None:
        (out / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
        (out / "main.py").write_text(
            f"""from fastapi import FastAPI

app = FastAPI(title=\"{name}\")

@app.get('/health')
def health():
    return {{'status':'ok','service':'{name}'}}

@app.get('/idea')
def idea():
    return {{'idea':'ATENA recomenda adicionar fila assíncrona + observabilidade por traces'}}
""",
            encoding="utf-8",
        )

    def _build_cli(self, out: Path, name: str) -> None:
        (out / "main.py").write_text(
            f"""#!/usr/bin/env python3
import argparse


def main():
    parser = argparse.ArgumentParser(prog='{name}', description='CLI gerada pela ATENA')
    parser.add_argument('nome', nargs='?', default='mundo')
    args = parser.parse_args()
    print(f'Olá, {{args.nome}}! Software CLI {name} criado pela ATENA ✅')


if __name__ == '__main__':
    main()
""",
            encoding="utf-8",
        )
