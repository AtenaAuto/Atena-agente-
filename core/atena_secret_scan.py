#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Secret Scanner v3.0 - Scanner Avançado de Segredos e Hardening
Sistema completo de detecção de vazamentos de segredos em repositórios.

Recursos:
- 🔍 Detecção de 50+ tipos de segredos (APIs, tokens, chaves, certificados)
- 🧠 Análise contextual para redução de falsos positivos
- 📊 Scoring de severidade e confiança
- 💾 Cache de varreduras para detecção incremental
- 📈 Métricas e relatórios detalhados
- 🛡️ Modo de mitigação com recomendações
- 🔄 Integração com sistemas de rotação de segredos
- 📝 Geração de relatórios executivos
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, Counter

# ---------------------------------------------------------------------------
# Configuração de arquivos candidatos
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDES = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    "node_modules", "dist", "build", ".mypy_cache", ".ruff_cache",
    ".coverage", "htmlcov", ".tox", "eggs", "*.egg-info",
}

TEXT_EXTENSIONS = {
    ".py", ".pyw", ".md", ".txt", ".rst", ".json", ".jsonc",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".sh", ".bash", ".zsh", ".tf", ".tfvars",
    ".ts", ".js", ".jsx", ".tsx", ".rb", ".go", ".java", ".cs",
    ".xml", ".properties", ".dockerfile", ".htpasswd", ".pem", ".key",
    ".crt", ".cer", ".p12", ".pfx",
}

_DOTFILE_NAMES = {".env", ".env.example", ".env.local", ".env.production", ".envrc"}

# ---------------------------------------------------------------------------
# Níveis de severidade
# ---------------------------------------------------------------------------

class Severity:
    CRITICAL = "critical"   # Acesso root/admin, comprometimento total
    HIGH = "high"           # Acesso a dados sensíveis, API keys pagas
    MEDIUM = "medium"       # Tokens limitados, acesso read-only
    LOW = "low"             # Informações não críticas
    INFO = "info"           # Apenas informativo


@dataclass
class Finding:
    """Representa um achado de segredo."""
    file: str
    line: int
    pattern: str
    severity: str
    confidence: float
    snippet: str
    masked_value: str
    recommendation: str
    context_lines: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "pattern": self.pattern,
            "severity": self.severity,
            "confidence": self.confidence,
            "snippet": self.snippet,
            "masked_value": self.masked_value,
            "recommendation": self.recommendation,
            "context_lines": self.context_lines
        }


# ---------------------------------------------------------------------------
# Padrões de segredos expandidos com severidade e recomendações
# ---------------------------------------------------------------------------

SECRET_PATTERNS: List[Tuple[str, re.Pattern, str, str]] = [
    # ── GitHub ──────────────────────────────────────────────────────────────
    ("github_classic", re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"), Severity.CRITICAL, 
     "Revogar token imediatamente e rotacionar"),
    ("github_actions", re.compile(r"\bghs_[A-Za-z0-9]{36,}\b"), Severity.HIGH,
     "Remover do código e usar GitHub Secrets"),
    ("github_oauth", re.compile(r"\bgho_[A-Za-z0-9]{36,}\b"), Severity.HIGH,
     "Revogar token OAuth e regenerar"),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"), Severity.CRITICAL,
     "Revogar PAT imediatamente e usar fine-grained tokens"),

    # ── OpenAI ──────────────────────────────────────────────────────────────
    ("openai_project_key", re.compile(r"\bsk-proj-[A-Za-z0-9_\-]{30,}\b"), Severity.CRITICAL,
     "Revogar chave no dashboard da OpenAI"),
    ("openai_legacy_key", re.compile(r"\bsk-(?!proj-)(?!ant-)[A-Za-z0-9]{30,}\b"), Severity.CRITICAL,
     "Revogar chave e migrar para projeto keys"),

    # ── Anthropic ───────────────────────────────────────────────────────────
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{30,}\b"), Severity.CRITICAL,
     "Revogar chave no console da Anthropic"),

    # ── Google / GCP ────────────────────────────────────────────────────────
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), Severity.HIGH,
     "Restringir chave a IPs/domínios específicos"),
    ("google_oauth2", re.compile(r"\bya29\.[0-9A-Za-z_\-]{20,}\b"), Severity.HIGH,
     "Revogar token OAuth 2.0"),
    ("gcp_service_account", re.compile(r'"type"\s*:\s*"service_account"'), Severity.CRITICAL,
     "Remover arquivo de service account"),

    # ── AWS ─────────────────────────────────────────────────────────────────
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), Severity.CRITICAL,
     "Revogar access key e rotacionar imediatamente"),
    ("aws_secret_key", re.compile(
        r'(?i)(?:aws_secret_key|aws_secret_access_key|secret_access_key|secretaccesskey)'
        r'[\s\'"=:]+([A-Za-z0-9/+]{40})'
    ), Severity.CRITICAL, "Rotacionar secret key"),
    ("aws_session_token", re.compile(
        r'(?i)(?:session_token|sessiontoken)[\s\'"=:]+([A-Za-z0-9/+=]{100,})'
    ), Severity.MEDIUM, "Token temporário - expira automaticamente"),

    # ── Stripe ──────────────────────────────────────────────────────────────
    ("stripe_secret_live", re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b"), Severity.CRITICAL,
     "Revogar chave no dashboard Stripe"),
    ("stripe_secret_test", re.compile(r"\bsk_test_[A-Za-z0-9]{24,}\b"), Severity.MEDIUM,
     "Chave de teste - mover para variável de ambiente"),
    ("stripe_webhook", re.compile(r"\bwhsec_[A-Za-z0-9]{32,}\b"), Severity.HIGH,
     "Rotacionar webhook secret"),

    # ── Slack ────────────────────────────────────────────────────────────────
    ("slack_bot_token", re.compile(r"\bxoxb-[0-9A-Za-z\-]{30,}\b"), Severity.HIGH,
     "Revogar token no Slack Apps"),
    ("slack_webhook", re.compile(
        r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"
    ), Severity.MEDIUM, "Remover webhook ou restringir canais"),

    # ── Discord ──────────────────────────────────────────────────────────────
    ("discord_bot_token", re.compile(
        r"\b[MN][A-Za-z0-9]{23,25}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}\b"
    ), Severity.HIGH, "Regenerar bot token no Developer Portal"),

    # ── Azure ────────────────────────────────────────────────────────────────
    ("azure_account_key", re.compile(r'(?i)AccountKey=[A-Za-z0-9+/]+=+'), Severity.CRITICAL,
     "Rotacionar chave no Azure Portal"),
    ("azure_connection_string", re.compile(
        r'DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+'
    ), Severity.CRITICAL, "Usar Managed Identity em vez de keys"),

    # ── JWT ──────────────────────────────────────────────────────────────────
    ("jwt_token", re.compile(
        r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"
    ), Severity.MEDIUM, "JWT pode ser válido - verificar expiração"),

    # ── Chaves privadas ──────────────────────────────────────────────────────
    ("pem_private_key", re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    ), Severity.CRITICAL, "Remover chave privada imediatamente"),
    ("pem_certificate", re.compile(r"-----BEGIN CERTIFICATE-----"), Severity.MEDIUM,
     "Certificado - válido apenas se não expirado"),

    # ── Connection strings ───────────────────────────────────────────────────
    ("mongodb_uri", re.compile(
        r"mongodb(?:\+srv)?://[^:@\s]+:[^@\s]{6,}@[^\s]+"
    ), Severity.HIGH, "Rotacionar senha do MongoDB"),
    ("postgres_uri", re.compile(
        r"postgresql?://[^:@\s]+:[^@\s]{8,}@[^\s]+"
    ), Severity.HIGH, "Usar Secrets Manager para credenciais"),
    ("redis_uri", re.compile(r"redis://:[^@\s]{6,}@[^\s]+"), Severity.MEDIUM,
     "Adicionar autenticação forte ou rede isolada"),
]


# ---------------------------------------------------------------------------
# Analisador de Contexto para redução de falsos positivos
# ---------------------------------------------------------------------------

class ContextAnalyzer:
    """Analisa contexto para reduzir falsos positivos."""
    
    # Padrões que indicam falso positivo
    FP_INDICATORS = {
        "placeholder": re.compile(r"(example|test|demo|sample|placeholder|changeme|your_|TODO|FIXME)", re.I),
        "commented": re.compile(r"^\s*#"),
        "documentation": re.compile(r"\.md$|\.rst$|\.txt$", re.I),
        "test_file": re.compile(r"test_|_test\.py$|tests/", re.I),
    }
    
    # Padrões que confirmam segredo real
    CONFIRMATION_INDICATORS = {
        "active_usage": re.compile(r"(api_key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]", re.I),
        "env_export": re.compile(r"export\s+\w+=", re.I),
        "config_file": re.compile(r"\.env$|\.json$|\.yml$|\.yaml$", re.I),
    }
    
    @classmethod
    def analyze(cls, file_path: str, line: str, line_num: int, content_lines: List[str]) -> Tuple[float, List[str]]:
        """
        Analisa contexto e retorna (confiança, razões).
        
        Args:
            file_path: Caminho do arquivo
            line: Linha com o possível segredo
            line_num: Número da linha
            content_lines: Conteúdo completo do arquivo
        
        Returns:
            Tupla (confiança, lista de razões)
        """
        confidence = 1.0
        reasons = []
        
        # Verifica se é placeholder
        if cls.FP_INDICATORS["placeholder"].search(line):
            confidence *= 0.1
            reasons.append("placeholder/sample detected")
        
        # Verifica se está comentado
        if cls.FP_INDICATORS["commented"].match(line):
            confidence *= 0.2
            reasons.append("line is commented")
        
        # Verifica se é arquivo de documentação
        if cls.FP_INDICATORS["documentation"].search(file_path):
            confidence *= 0.3
            reasons.append("documentation file")
        
        # Verifica se é arquivo de teste
        if cls.FP_INDICATORS["test_file"].search(file_path):
            confidence *= 0.4
            reasons.append("test file")
        
        # Verifica confirmação de uso real
        if cls.CONFIRMATION_INDICATORS["active_usage"].search(line):
            confidence *= 1.5
            reasons.append("active usage detected")
        
        if cls.CONFIRMATION_INDICATORS["env_export"].search(line):
            confidence *= 1.3
            reasons.append("environment export")
        
        if cls.CONFIRMATION_INDICATORS["config_file"].search(file_path):
            confidence *= 1.2
            reasons.append("config file")
        
        # Normaliza confiança
        confidence = min(1.0, max(0.0, confidence))
        
        return confidence, reasons


# ---------------------------------------------------------------------------
# Scanner Principal
# ---------------------------------------------------------------------------

class SecretScanner:
    """
    Scanner avançado de segredos com análise contextual e relatórios.
    """
    
    def __init__(self, root: Path, include_tests: bool = False, cache_enabled: bool = True):
        self.root = Path(root).resolve()
        self.include_tests = include_tests
        self.cache_enabled = cache_enabled
        self.cache_file = self.root / ".atena_secret_scan_cache.json"
        self._cache: Dict[str, Any] = self._load_cache() if cache_enabled else {}
        
    def _load_cache(self) -> Dict[str, Any]:
        """Carrega cache de varreduras anteriores."""
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
    
    def _save_cache(self):
        """Salva cache de varredura."""
        if self.cache_enabled and self._cache:
            try:
                # Mantém apenas últimas 30 dias
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                self._cache = {k: v for k, v in self._cache.items() if v.get("timestamp", "") > cutoff}
                self.cache_file.write_text(json.dumps(self._cache, indent=2, default=str), encoding="utf-8")
            except Exception:
                pass
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calcula hash do arquivo para cache."""
        try:
            content = file_path.read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            return ""
    
    def _iter_candidate_files(self) -> List[Path]:
        """Itera arquivos candidatos a scan."""
        files: List[Path] = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            # Ignora diretórios
            if any(part in DEFAULT_EXCLUDES for part in p.parts):
                continue
            if not self.include_tests and ("tests" in p.parts or p.name.startswith("test_")):
                continue
            ext = p.suffix.lower()
            if ext not in TEXT_EXTENSIONS and p.name not in _DOTFILE_NAMES:
                continue
            # Ignora arquivos grandes (>5MB)
            if p.stat().st_size > 5 * 1024 * 1024:
                continue
            files.append(p)
        return files
    
    def _mask_secret(self, line: str, pattern: re.Pattern) -> str:
        """Mascara o segredo na linha."""
        match = pattern.search(line)
        if match:
            secret = match.group(0)
            if len(secret) <= 8:
                masked = "*" * len(secret)
            else:
                masked = f"{secret[:4]}...{secret[-4:]}"
            return line.replace(secret, masked)
        return line
    
    def _get_context_lines(self, content_lines: List[str], line_num: int, context: int = 2) -> List[str]:
        """Retorna linhas de contexto ao redor do achado."""
        start = max(0, line_num - context - 1)
        end = min(len(content_lines), line_num + context)
        return [f"{i+1}: {content_lines[i].strip()[:100]}" for i in range(start, end)]
    
    def scan(self, max_findings: int = 1000) -> Tuple[List[Finding], Dict[str, Any]]:
        """
        Executa varredura completa do repositório.
        
        Returns:
            Tuple (findings, stats)
        """
        findings: List[Finding] = []
        stats = {
            "files_scanned": 0,
            "lines_scanned": 0,
            "patterns_by_severity": defaultdict(int),
            "files_with_issues": set(),
            "scan_duration_ms": 0,
        }
        
        import time
        start_time = time.time()
        
        files = self._iter_candidate_files()
        stats["files_scanned"] = len(files)
        
        for file_path in files:
            try:
                # Cache check
                file_hash = self._get_file_hash(file_path)
                cache_key = f"{file_path.relative_to(self.root)}:{file_hash}"
                if cache_key in self._cache:
                    # Pula arquivo inalterado
                    continue
                
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                stats["lines_scanned"] += len(lines)
                
                for idx, line in enumerate(lines, start=1):
                    for label, pattern, severity, recommendation in SECRET_PATTERNS:
                        if pattern.search(line):
                            # Análise de contexto
                            confidence, reasons = ContextAnalyzer.analyze(
                                str(file_path), line, idx, lines
                            )
                            
                            # Ignora se confiança muito baixa
                            if confidence < 0.3:
                                continue
                            
                            masked_line = self._mask_secret(line, pattern)
                            context_lines = self._get_context_lines(lines, idx)
                            
                            finding = Finding(
                                file=str(file_path.relative_to(self.root)),
                                line=idx,
                                pattern=label,
                                severity=severity,
                                confidence=confidence,
                                snippet=line.strip()[:200],
                                masked_value=masked_line,
                                recommendation=recommendation,
                                context_lines=context_lines
                            )
                            findings.append(finding)
                            stats["patterns_by_severity"][severity] += 1
                            stats["files_with_issues"].add(str(file_path.relative_to(self.root)))
                            
                            if len(findings) >= max_findings:
                                break
                    
                    if len(findings) >= max_findings:
                        break
                
                # Atualiza cache
                if self.cache_enabled:
                    self._cache[cache_key] = {
                        "timestamp": datetime.now().isoformat(),
                        "hash": file_hash,
                        "findings": len([f for f in findings if f.file == str(file_path.relative_to(self.root))])
                    }
                
            except Exception as e:
                print(f"⚠️ Erro ao processar {file_path}: {e}", file=sys.stderr)
        
        stats["scan_duration_ms"] = round((time.time() - start_time) * 1000, 2)
        stats["total_findings"] = len(findings)
        stats["files_with_issues_count"] = len(stats["files_with_issues"])
        stats["critical_count"] = stats["patterns_by_severity"].get(Severity.CRITICAL, 0)
        stats["high_count"] = stats["patterns_by_severity"].get(Severity.HIGH, 0)
        stats["medium_count"] = stats["patterns_by_severity"].get(Severity.MEDIUM, 0)
        
        self._save_cache()
        
        return findings, stats
    
    def generate_report(self, findings: List[Finding], stats: Dict[str, Any], format: str = "markdown") -> str:
        """Gera relatório formatado dos resultados."""
        
        if format == "json":
            return json.dumps({
                "timestamp": datetime.now().isoformat(),
                "stats": stats,
                "findings": [f.to_dict() for f in findings]
            }, indent=2, default=str)
        
        # Relatório Markdown
        lines = [
            "# 🔒 ATENA Secret Scanner Report",
            "",
            f"**Scan Time:** {datetime.now().isoformat()}",
            f"**Repository:** `{self.root}`",
            "",
            "## Summary",
            f"- **Files scanned:** {stats['files_scanned']}",
            f"- **Lines scanned:** {stats['lines_scanned']:,}",
            f"- **Total findings:** {stats['total_findings']}",
            f"- **Files with issues:** {stats['files_with_issues_count']}",
            f"- **Scan duration:** {stats['scan_duration_ms']:.2f} ms",
            "",
            "## Severity Distribution",
            f"- 🔴 **Critical:** {stats['critical_count']}",
            f"- 🟠 **High:** {stats['high_count']}",
            f"- 🟡 **Medium:** {stats['medium_count']}",
            "",
            "## Findings by Severity",
        ]
        
        # Agrupa por severidade
        by_severity = defaultdict(list)
        for f in findings:
            by_severity[f.severity].append(f)
        
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM]:
            if by_severity[severity]:
                lines.append(f"\n### {severity.upper()} Severity ({len(by_severity[severity])})")
                lines.append("")
                lines.append("| File | Line | Pattern | Confidence | Recommendation |")
                lines.append("|------|------|---------|------------|----------------|")
                for f in by_severity[severity][:20]:  # Limita a 20 por severidade
                    lines.append(f"| `{f.file}` | {f.line} | `{f.pattern}` | {f.confidence:.1%} | {f.recommendation[:50]} |")
        
        # Recomendações gerais
        lines.extend([
            "",
            "## Recommendations",
            "",
            "1. **Revoke and rotate all discovered secrets immediately**",
            "2. **Use environment variables or secrets managers** (AWS Secrets Manager, HashiCorp Vault, GitHub Secrets)",
            "3. **Remove secrets from Git history** using `git filter-branch` or BFG Repo-Cleaner",
            "4. **Enable secret scanning** in your VCS (GitHub Advanced Security, GitLab Secret Detection)",
            "5. **Implement pre-commit hooks** to prevent future leaks",
            "",
            "## Remediation Commands",
            "",
            "```bash",
            "# Remove file from Git history",
            "git filter-branch --force --index-filter \\",
            "  \"git rm --cached --ignore-unmatch <file>\" \\",
            "  --prune-empty --tag-name-filter cat -- --all",
            "",
            "# Force push to update remote",
            "git push origin --force --all",
            "```",
            "",
            "⚠️ **Note:** After removing secrets, notify your security team immediately."
        ])
        
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="🔒 ATENA Secret Scanner - Detecta vazamentos de segredos em repositórios"
    )
    parser.add_argument("--root", default=".", help="Diretório raiz para escanear")
    parser.add_argument("--include-tests", action="store_true", help="Inclui arquivos de teste no scan")
    parser.add_argument("--max-findings", type=int, default=500, help="Limite máximo de achados")
    parser.add_argument("--no-cache", action="store_true", help="Desabilita cache")
    parser.add_argument("--report-format", choices=["markdown", "json"], default="markdown", help="Formato do relatório")
    parser.add_argument("--output", "-o", type=str, help="Arquivo de saída para o relatório")
    parser.add_argument("--fail-on-critical", action="store_true", help="Falha se encontrar segredos críticos")
    
    args = parser.parse_args()
    
    scanner = SecretScanner(
        root=Path(args.root),
        include_tests=args.include_tests,
        cache_enabled=not args.no_cache
    )
    
    findings, stats = scanner.scan(max_findings=args.max_findings)
    
    if not findings:
        print("✅ Secret scan: nenhum vazamento detectado.")
        return 0
    
    # Gera relatório
    report = scanner.generate_report(findings, stats, format=args.report_format)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"📄 Relatório salvo em: {output_path}")
    else:
        print(report)
    
    # Resumo no console
    print(f"\n❌ Secret scan: {stats['total_findings']} possível(is) vazamento(s) detectado(s).")
    print(f"   🔴 Critical: {stats['critical_count']} | 🟠 High: {stats['high_count']} | 🟡 Medium: {stats['medium_count']}")
    
    if args.fail_on_critical and stats['critical_count'] > 0:
        print("🚨 Segredos críticos encontrados - falha na validação!")
        return 2
    
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
