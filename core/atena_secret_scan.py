#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanner de segredos para hardening de segurança da ATENA.

Cobertura:
  GitHub     — ghp_, ghs_, gho_, ghu_, ghr_, github_pat_
  OpenAI     — sk-proj-*, sk-*  (formato legado e novo)
  Anthropic  — sk-ant-*
  AWS        — Access Key (AKIA*/ASIA*), Secret Key, Session Token
  Google     — AIza*, ya29.*, service_account JSON
  Stripe     — sk_live_*, sk_test_*, pk_live_*, pk_test_*, rk_live_*, whsec_*
  Slack      — xoxb-*, xoxp-*, xoxa-*, webhook URL
  Discord    — bot token, webhook URL
  Twilio     — AC* SID, SK* token
  SendGrid   — SG.*
  JWT        — eyJ* (header base64)
  Chaves PEM — BEGIN * PRIVATE KEY / CERTIFICATE
  npm        — npm_*
  Docker Hub — dckr_pat_*
  Heroku     — HRKU-*
  Azure      — AccountKey=*, SAS sig=*
  MongoDB    — mongodb+srv://* com senha
  PostgreSQL/MySQL — uri com senha
  Redis      — redis://:senha@*
  URLs HTTP  — http(s)://:senha@host genérico
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuração de arquivos candidatos
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDES = {
    ".git", ".venv", "venv", "__pycache__",
    ".pytest_cache", "node_modules", "dist", "build",
}

TEXT_EXTENSIONS = {
    ".py", ".pyw",
    ".md", ".txt", ".rst",
    ".json", ".jsonc",
    ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf",
    ".env", ".sh", ".bash", ".zsh",
    ".tf", ".tfvars",
    ".ts", ".js", ".jsx", ".tsx",
    ".rb", ".go", ".java", ".cs",
    ".xml", ".properties",
    ".dockerfile",
    ".htpasswd",
}

_DOTFILE_NAMES = {".env", ".env.example", ".env.local", ".env.production", ".envrc"}

# ---------------------------------------------------------------------------
# Padrões de segredos
# ---------------------------------------------------------------------------

SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [

    # ── GitHub ──────────────────────────────────────────────────────────────
    ("github_classic",      re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_actions",      re.compile(r"\bghs_[A-Za-z0-9]{20,}\b")),
    ("github_oauth",        re.compile(r"\bgho_[A-Za-z0-9]{20,}\b")),
    ("github_user",         re.compile(r"\bghu_[A-Za-z0-9]{20,}\b")),
    ("github_refresh",      re.compile(r"\bghr_[A-Za-z0-9]{20,}\b")),
    ("github_pat",          re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),

    # ── OpenAI ──────────────────────────────────────────────────────────────
    ("openai_project_key",  re.compile(r"\bsk-proj-[A-Za-z0-9_\-]{20,}\b")),
    ("openai_key",          re.compile(r"\bsk-(?!proj-)(?!ant-)[A-Za-z0-9]{20,}\b")),

    # ── Anthropic ───────────────────────────────────────────────────────────
    ("anthropic_key",       re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),

    # ── AWS ─────────────────────────────────────────────────────────────────
    ("aws_access_key",      re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("aws_secret_key",      re.compile(
        r'(?i)(?:aws_secret_key|aws_secret_access_key|secret_access_key|secretaccesskey)'
        r'[\s\'"=:]+([A-Za-z0-9/+]{40})'
    )),
    ("aws_session_token",   re.compile(
        r'(?i)(?:session_token|sessiontoken)[\s\'"=:]+([A-Za-z0-9/+=]{100,})'
    )),

    # ── Google ──────────────────────────────────────────────────────────────
    ("google_api_key",      re.compile(r"\bAIza[A-Za-z0-9_\-]{35}\b")),
    ("google_oauth2",       re.compile(r"\bya29\.[A-Za-z0-9_\-]{20,}\b")),
    ("gcp_service_account", re.compile(r'"type"\s*:\s*"service_account"')),

    # ── Stripe ──────────────────────────────────────────────────────────────
    ("stripe_secret_live",  re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b")),
    ("stripe_secret_test",  re.compile(r"\bsk_test_[A-Za-z0-9]{24,}\b")),
    ("stripe_pub_live",     re.compile(r"\bpk_live_[A-Za-z0-9]{24,}\b")),
    ("stripe_pub_test",     re.compile(r"\bpk_test_[A-Za-z0-9]{24,}\b")),
    ("stripe_restricted",   re.compile(r"\brk_live_[A-Za-z0-9]{24,}\b")),
    ("stripe_webhook",      re.compile(r"\bwhsec_[A-Za-z0-9]{32,}\b")),

    # ── Slack ────────────────────────────────────────────────────────────────
    ("slack_bot_token",     re.compile(r"\bxoxb-[0-9A-Za-z\-]{24,}\b")),
    ("slack_user_token",    re.compile(r"\bxoxp-[0-9A-Za-z\-]{24,}\b")),
    ("slack_app_token",     re.compile(r"\bxoxa-[0-9A-Za-z\-]{24,}\b")),
    ("slack_webhook",       re.compile(
        r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"
    )),

    # ── Discord ──────────────────────────────────────────────────────────────
    ("discord_bot_token",   re.compile(
        r"\b[MN][A-Za-z0-9]{23,25}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}\b"
    )),
    ("discord_webhook",     re.compile(
        r"https://discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_\-]+"
    )),

    # ── Twilio ───────────────────────────────────────────────────────────────
    ("twilio_account_sid",  re.compile(r"\bAC[a-f0-9]{32}\b")),
    ("twilio_auth_token",   re.compile(r"\bSK[a-f0-9]{32}\b")),

    # ── SendGrid ─────────────────────────────────────────────────────────────
    ("sendgrid_key",        re.compile(r"\bSG\.[A-Za-z0-9_\-]{22,}\.[A-Za-z0-9_\-]{43,}\b")),

    # ── npm / Docker / Heroku ────────────────────────────────────────────────
    ("npm_token",           re.compile(r"\bnpm_[A-Za-z0-9]{36,}\b")),
    ("docker_pat",          re.compile(r"\bdckr_pat_[A-Za-z0-9_\-]{20,}\b")),
    ("heroku_api_key",      re.compile(r"\bHRKU-[a-f0-9\-]{36}\b")),

    # ── Azure ────────────────────────────────────────────────────────────────
    ("azure_account_key",   re.compile(r'(?i)AccountKey=[A-Za-z0-9+/]+=+')),
    ("azure_sas_token",     re.compile(r'(?i)\bsig=[A-Za-z0-9%+/]{20,}')),

    # ── Chaves PEM ───────────────────────────────────────────────────────────
    ("pem_private_key",     re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    )),
    ("pem_certificate",     re.compile(r"-----BEGIN CERTIFICATE-----")),

    # ── JWT ──────────────────────────────────────────────────────────────────
    ("jwt_token",           re.compile(
        r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"
    )),

    # ── Connection strings com senha embutida ────────────────────────────────
    ("mongodb_uri",         re.compile(
        r"mongodb(?:\+srv)?://[^:@\s]+:[^@\s]{6,}@[^\s]+"
    )),
    ("postgres_uri",        re.compile(
        r"postgresql?://[^:@\s]+:[^@\s]{6,}@[^\s]+"
    )),
    ("mysql_uri",           re.compile(
        r"mysql(?:2)?://[^:@\s]+:[^@\s]{6,}@[^\s]+"
    )),
    ("redis_uri",           re.compile(r"redis://:[^@\s]{6,}@[^\s]+")),
    ("generic_url_creds",   re.compile(
        r"https?://[^:@\s/]+:[^@\s]{8,}@[^\s]+"
    )),
]

# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def _iter_candidate_files(root: Path, include_tests: bool = False) -> list[Path]:
    """Itera todos os arquivos de texto candidatos ao scan dentro de root."""
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in DEFAULT_EXCLUDES for part in p.parts):
            continue
        if not include_tests and ("tests" in p.parts or p.name.startswith("test_")):
            continue
        ext = p.suffix.lower()
        if ext not in TEXT_EXTENSIONS and p.name not in _DOTFILE_NAMES:
            continue
        files.append(p)
    return files


def scan_repo(
    root: Path,
    include_tests: bool = False,
    max_findings: int = 500,
) -> list[dict[str, object]]:
    """
    Varre root em busca de segredos e retorna lista de achados.

    Cada achado é um dict com:
      file    — caminho relativo a root
      line    — número de linha (1-based)
      pattern — label do padrão que casou
      snippet — fragmento da linha (primeiros 120 chars)
    """
    findings: list[dict[str, object]] = []
    for file_path in _iter_candidate_files(root, include_tests=include_tests):
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "file":    str(file_path.relative_to(root)),
                        "line":    idx,
                        "pattern": label,
                        "snippet": line.strip()[:120],
                    })
                    if len(findings) >= max_findings:
                        return findings
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Escaneia repositório em busca de segredos vazados."
    )
    parser.add_argument("--root", default=".", help="Diretório raiz para escanear")
    parser.add_argument(
        "--include-tests", action="store_true",
        help="Inclui arquivos de teste no scan"
    )
    parser.add_argument(
        "--max-findings", type=int, default=500,
        help="Limite máximo de achados retornados (padrão: 500)"
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings = scan_repo(root, include_tests=args.include_tests,
                         max_findings=args.max_findings)

    if not findings:
        print("✅ Secret scan: nenhum vazamento detectado.")
        return 0

    print(f"❌ Secret scan: {len(findings)} possível(is) vazamento(s) detectado(s).\n")
    for item in findings:
        print(f"  {item['file']}:{item['line']}  [{item['pattern']}]")
        print(f"    {item['snippet']}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
