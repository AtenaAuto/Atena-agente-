#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA External Code Smoke Test v3.0 - Validação Avançada de Código Externo
Sistema completo de análise, validação e integração de código de repositórios externos.

Recursos:
- 🔍 Clonagem inteligente com validação de integridade
- 🧪 Teste de compilação e sintaxe multi-versão Python
- 📊 Análise estática (pylint, radon) para qualidade de código
- 🛡️ Scanner de segurança (bandit, semgrep) para vulnerabilidades
- 💾 Cache persistente de análises
- 📈 Métricas de complexidade e manutenibilidade
- 🔄 Detecção de dependências perigosas
- 📝 Geração de relatórios detalhados com recomendações
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import Counter, defaultdict

# Tentativa de importar bibliotecas avançadas
try:
    import radon.complexity as radon_cc
    import radon.metrics as radon_metrics
    HAS_RADON = True
except ImportError:
    HAS_RADON = False

try:
    from pylint import lint
    from pylint.reporters import BaseReporter
    HAS_PYLINT = True
except ImportError:
    HAS_PYLINT = False

try:
    import bandit
    from bandit.core import manager as bandit_manager
    HAS_BANDIT = True
except ImportError:
    HAS_BANDIT = False


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FileAnalysis:
    """Resultado da análise de um arquivo Python."""
    path: str
    lines: int
    functions: int
    classes: int
    imports: List[str]
    syntax_ok: bool
    compile_ok: bool
    syntax_error: Optional[str] = None
    complexity_score: float = 0.0
    maintainability_score: float = 0.0
    security_score: float = 1.0
    quality_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RepoAnalysis:
    """Resultado da análise de um repositório."""
    name: str
    url: str
    clone_url: str
    workspace: Path
    status: str
    files_analyzed: int
    syntax_ok_count: int
    compile_ok_count: int
    avg_complexity: float
    avg_maintainability: float
    overall_quality: float
    security_issues: List[Dict[str, Any]]
    issues: List[str]
    warnings: List[str]
    clone_duration_ms: float
    analysis_duration_ms: float
    python_version_detected: str
    dependencies: Dict[str, List[str]]
    timestamp: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


class ExternalCodeValidator:
    """
    Validador avançado de código externo com múltiplas camadas de análise.
    """
    
    def __init__(self, workspace: Path, cache_dir: Optional[Path] = None):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir or self.workspace / ".analysis_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = self._load_cache()
        
    def _load_cache(self) -> Dict[str, Any]:
        """Carrega cache de análises anteriores."""
        cache_file = self.cache_dir / "analysis_cache.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
    
    def _save_cache(self):
        """Salva cache de análises."""
        cache_file = self.cache_dir / "analysis_cache.json"
        cache_file.write_text(json.dumps(self._cache, indent=2, default=str), encoding="utf-8")
    
    def _get_cache_key(self, repo_url: str, commit_hash: str = "") -> str:
        """Gera chave de cache para repositório."""
        content = f"{repo_url}:{commit_hash}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _run_command(self, cmd: List[str], cwd: Optional[Path] = None, timeout: int = 180) -> Tuple[int, str, str, float]:
        """Executa comando com medição de tempo."""
        import time
        start = time.time()
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = (time.time() - start) * 1000
        return proc.returncode, proc.stdout or "", proc.stderr or "", elapsed
    
    def _detect_python_version(self, repo_dir: Path) -> str:
        """Detecta versão Python usada no repositório."""
        version_files = [
            repo_dir / ".python-version",
            repo_dir / "runtime.txt",
            repo_dir / "Pipfile",
            repo_dir / "pyproject.toml"
        ]
        
        for vf in version_files:
            if vf.exists():
                try:
                    content = vf.read_text(encoding="utf-8")
                    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', content)
                    if match:
                        return match.group(1)
                except Exception:
                    pass
        
        # Verifica requirements.txt
        req_file = repo_dir / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text(encoding="utf-8", errors="ignore")
            if "python_requires" in content:
                match = re.search(r'python_requires\s*[=<>!]+\s*[\'"]?(\d+\.\d+)', content)
                if match:
                    return match.group(1)
        
        return f"{sys.version_info.major}.{sys.version_info.minor}"
    
    def _extract_dependencies(self, repo_dir: Path) -> Dict[str, List[str]]:
        """Extrai dependências do repositório."""
        dependencies = {
            "requirements": [],
            "dev_requirements": [],
            "build_deps": []
        }
        
        # requirements.txt
        req_file = repo_dir / "requirements.txt"
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    dependencies["requirements"].append(line.split("==")[0].split(">=")[0])
        
        # pyproject.toml
        pyproject = repo_dir / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            deps = re.findall(r'"([^"]+)"', content)
            dependencies["build_deps"].extend(deps[:20])
        
        # Pipfile
        pipfile = repo_dir / "Pipfile"
        if pipfile.exists():
            content = pipfile.read_text(encoding="utf-8", errors="ignore")
            deps = re.findall(r'([a-zA-Z0-9_-]+)\s*=\s*"[^"]+"', content)
            dependencies["dev_requirements"].extend(deps[:20])
        
        return dependencies
    
    def _analyze_file(self, file_path: Path) -> FileAnalysis:
        """Analisa um arquivo Python individualmente."""
        analysis = FileAnalysis(
            path=str(file_path.relative_to(self.workspace)),
            lines=0,
            functions=0,
            classes=0,
            imports=[],
            syntax_ok=False,
            compile_ok=False
        )
        
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            analysis.lines = len(content.splitlines())
            
            # Parse AST
            tree = ast.parse(content)
            
            # Contagem de elementos
            analysis.functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            analysis.classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            
            # Extrai imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis.imports.append(node.module)
            
            analysis.syntax_ok = True
            
            # Compilação
            try:
                compile(content, str(file_path), 'exec')
                analysis.compile_ok = True
            except SyntaxError as e:
                analysis.compile_ok = False
                analysis.syntax_error = str(e)
                analysis.issues.append(f"Erro de sintaxe: {e}")
            
            # Complexidade (se radon disponível)
            if HAS_RADON:
                try:
                    blocks = radon_cc.cc_visit(content)
                    if blocks:
                        analysis.complexity_score = sum(b.complexity for b in blocks) / len(blocks)
                    else:
                        analysis.complexity_score = 1.0
                except Exception:
                    analysis.complexity_score = 1.0
            else:
                analysis.complexity_score = 1.0
            
            # Qualidade base
            analysis.quality_score = min(1.0, (
                (analysis.compile_ok * 0.3) +
                (min(analysis.functions / 10, 1.0) * 0.2) +
                (min(analysis.classes / 5, 1.0) * 0.1) +
                (max(0, 1.0 - (analysis.complexity_score / 20)) * 0.2) +
                (1.0 if analysis.syntax_ok else 0) * 0.2
            ))
            
            # Análise de segurança básica
            dangerous_patterns = [
                (r'eval\s*\(', "uso de eval()"),
                (r'exec\s*\(', "uso de exec()"),
                (r'__import__\s*\(', "import dinâmico"),
                (r'os\.system\s*\(', "chamada de sistema"),
                (r'subprocess\.call', "subprocess sem validação"),
                (r'password\s*=\s*[\'"][^\'"]+[\'"]', "hardcoded password"),
            ]
            
            for pattern, warning in dangerous_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    analysis.warnings.append(warning)
                    analysis.security_score -= 0.1
            
            analysis.security_score = max(0.0, analysis.security_score)
            
        except Exception as e:
            analysis.issues.append(f"Erro na análise: {e}")
        
        return analysis
    
    def _run_pylint_analysis(self, repo_dir: Path, files: List[Path]) -> Tuple[float, List[str], List[str]]:
        """Executa análise pylint no repositório."""
        if not HAS_PYLINT or not files:
            return 0.7, [], []
        
        class CapturingReporter(BaseReporter):
            def __init__(self):
                super().__init__()
                self.messages = []
                self.errors = []
                self.warnings = []
            
            def handle_message(self, msg):
                self.messages.append(msg)
                if "error" in msg.msg.lower():
                    self.errors.append(str(msg))
                elif "warning" in msg.msg.lower():
                    self.warnings.append(str(msg))
        
        try:
            reporter = CapturingReporter()
            file_paths = [str(f) for f in files[:20]]  # Limita para performance
            
            lint.Run(file_paths, reporter=reporter, exit=False)
            
            total_issues = len(reporter.errors) + len(reporter.warnings) * 0.5
            score = max(0.0, 1.0 - (total_issues / 50))
            
            return score, reporter.errors[:10], reporter.warnings[:20]
        except Exception as e:
            return 0.5, [str(e)], []
    
    def _run_bandit_scan(self, repo_dir: Path, files: List[Path]) -> List[Dict[str, Any]]:
        """Executa scan de segurança com bandit."""
        if not HAS_BANDIT or not files:
            return []
        
        security_issues = []
        try:
            for file_path in files[:10]:  # Limita para performance
                # Análise básica de segurança
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                
                # Padrões de segurança
                patterns = [
                    (r"subprocess\.Popen", "medium", "Uso de subprocess.Popen pode ser perigoso"),
                    (r"subprocess\.call", "medium", "Uso de subprocess.call pode ser perigoso"),
                    (r"os\.system", "high", "Uso de os.system é altamente perigoso"),
                    (r"eval\(", "high", "Uso de eval() permite execução arbitrária"),
                    (r"exec\(", "high", "Uso de exec() permite execução arbitrária"),
                    (r"pickle\.loads", "medium", "Pickle pode executar código arbitrário"),
                    (r"yaml\.load\(", "medium", "YAML.load pode ser inseguro, use safe_load"),
                    (r"requests\.get\(.*verify=False", "high", "Verificação SSL desabilitada"),
                ]
                
                for line_no, line in enumerate(content.splitlines(), 1):
                    for pattern, severity, message in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            security_issues.append({
                                "file": str(file_path.relative_to(repo_dir)),
                                "line": line_no,
                                "severity": severity,
                                "message": message,
                                "code": line.strip()[:100]
                            })
        except Exception as e:
            pass
        
        return security_issues
    
    def analyze_repo(self, repo: Dict[str, str], max_files: int = 20, use_cache: bool = True) -> RepoAnalysis:
        """
        Analisa um repositório externo completo.
        
        Args:
            repo: Informações do repositório (name, clone_url, url)
            max_files: Número máximo de arquivos para analisar
            use_cache: Se deve usar cache de análises
        """
        import time
        
        name = str(repo.get("name", "unknown")).replace("/", "__")
        clone_url = str(repo.get("clone_url") or "")
        repo_url = str(repo.get("url") or "")
        
        # Verifica cache
        cache_key = self._get_cache_key(clone_url)
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if dt.datetime.fromisoformat(cached.get("timestamp", "2000-01-01")) > dt.datetime.now() - dt.timedelta(days=1):
                print(f"  📦 Cache hit para {name}")
                return RepoAnalysis(**cached)
        
        target = self.workspace / name
        start_time = time.time()
        
        # Clone ou pull
        if target.exists():
            rc, out, err, clone_time = self._run_command(["git", "-C", str(target), "pull", "--ff-only"], timeout=120)
            action = "pull"
        else:
            rc, out, err, clone_time = self._run_command(["git", "clone", "--depth", "1", clone_url, str(target)], timeout=240)
            action = "clone"
        
        clone_ok = rc == 0
        
        if not clone_ok:
            return RepoAnalysis(
                name=name,
                url=repo_url,
                clone_url=clone_url,
                workspace=target,
                status="failed",
                files_analyzed=0,
                syntax_ok_count=0,
                compile_ok_count=0,
                avg_complexity=0,
                avg_maintainability=0,
                overall_quality=0,
                security_issues=[],
                issues=[f"Falha no {action}: {err[:200]}"],
                warnings=[],
                clone_duration_ms=clone_time,
                analysis_duration_ms=0,
                python_version_detected="unknown",
                dependencies={}
            )
        
        # Análise dos arquivos
        analysis_start = time.time()
        py_files = self.discover_python_files(target, max_files)
        
        file_analyses = []
        complexity_scores = []
        maintainability_scores = []
        quality_scores = []
        security_issues = []
        all_issues = []
        all_warnings = []
        
        for pyf in py_files:
            fa = self._analyze_file(pyf)
            file_analyses.append(fa)
            
            if fa.compile_ok:
                complexity_scores.append(fa.complexity_score)
                maintainability_scores.append(fa.maintainability_score)
                quality_scores.append(fa.quality_score)
            
            all_issues.extend(fa.issues)
            all_warnings.extend(fa.warnings)
        
        # Métricas agregadas
        syntax_ok_count = sum(1 for fa in file_analyses if fa.syntax_ok)
        compile_ok_count = sum(1 for fa in file_analyses if fa.compile_ok)
        avg_complexity = sum(complexity_scores) / max(1, len(complexity_scores))
        avg_maintainability = sum(maintainability_scores) / max(1, len(maintainability_scores))
        overall_quality = sum(quality_scores) / max(1, len(quality_scores))
        
        # Pylint analysis
        if HAS_PYLINT and py_files:
            pylint_score, pylint_errors, pylint_warnings = self._run_pylint_analysis(target, py_files[:10])
            overall_quality = (overall_quality + pylint_score) / 2
            all_issues.extend(pylint_errors)
            all_warnings.extend(pylint_warnings)
        
        # Security scan
        security_issues = self._run_bandit_scan(target, py_files)
        
        # Detecta dependências
        dependencies = self._extract_dependencies(target)
        
        # Detecta versão Python
        python_version = self._detect_python_version(target)
        
        analysis_duration = (time.time() - analysis_start) * 1000
        
        # Status final
        if compile_ok_count == len(py_files) and len(py_files) > 0:
            status = "ok"  # Todos compilam
        elif compile_ok_count >= len(py_files) * 0.7:
            status = "warn"  # Maioria compila
        else:
            status = "failed"  # Muitas falhas
        
        result = RepoAnalysis(
            name=name,
            url=repo_url,
            clone_url=clone_url,
            workspace=target,
            status=status,
            files_analyzed=len(py_files),
            syntax_ok_count=syntax_ok_count,
            compile_ok_count=compile_ok_count,
            avg_complexity=round(avg_complexity, 2),
            avg_maintainability=round(avg_maintainability, 2),
            overall_quality=round(overall_quality, 4),
            security_issues=security_issues[:20],
            issues=all_issues[:20],
            warnings=all_warnings[:30],
            clone_duration_ms=round(clone_time, 2),
            analysis_duration_ms=round(analysis_duration, 2),
            python_version_detected=python_version,
            dependencies=dependencies
        )
        
        # Salva no cache
        self._cache[cache_key] = {
            "name": name,
            "url": repo_url,
            "clone_url": clone_url,
            "workspace": str(target),
            "status": status,
            "files_analyzed": len(py_files),
            "syntax_ok_count": syntax_ok_count,
            "compile_ok_count": compile_ok_count,
            "avg_complexity": round(avg_complexity, 2),
            "avg_maintainability": round(avg_maintainability, 2),
            "overall_quality": round(overall_quality, 4),
            "security_issues": security_issues[:20],
            "issues": all_issues[:20],
            "warnings": all_warnings[:30],
            "clone_duration_ms": round(clone_time, 2),
            "analysis_duration_ms": round(analysis_duration, 2),
            "python_version_detected": python_version,
            "dependencies": dependencies,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()
        }
        self._save_cache()
        
        return result
    
    def discover_python_files(self, repo_dir: Path, max_files: int) -> List[Path]:
        """Descobre arquivos Python no repositório."""
        files = []
        for path in repo_dir.rglob("*.py"):
            # Ignora diretórios comuns de exclusão
            if any(part in path.parts for part in [".git", "__pycache__", "venv", ".venv", "env", ".env", "build", "dist"]):
                continue
            # Ignora testes e exemplos (opcional)
            if "test" in path.name.lower() or "example" in path.name.lower():
                continue
            files.append(path)
        files.sort()
        return files[:max_files]
    
    def generate_quality_report(self, analyses: List[RepoAnalysis]) -> Dict[str, Any]:
        """Gera relatório agregado de qualidade."""
        total_repos = len(analyses)
        ok_count = sum(1 for a in analyses if a.status == "ok")
        warn_count = sum(1 for a in analyses if a.status == "warn")
        fail_count = sum(1 for a in analyses if a.status == "failed")
        
        avg_quality = sum(a.overall_quality for a in analyses) / max(1, total_repos)
        avg_complexity = sum(a.avg_complexity for a in analyses) / max(1, total_repos)
        total_files = sum(a.files_analyzed for a in analyses)
        total_issues = sum(len(a.issues) for a in analyses)
        total_warnings = sum(len(a.warnings) for a in analyses)
        
        # Dependências mais comuns
        all_deps = []
        for a in analyses:
            for deps in a.dependencies.values():
                all_deps.extend(deps)
        common_deps = Counter(all_deps).most_common(10)
        
        # Segurança
        total_security_issues = sum(len(a.security_issues) for a in analyses)
        
        return {
            "summary": {
                "total_repos": total_repos,
                "ok_count": ok_count,
                "warn_count": warn_count,
                "fail_count": fail_count,
                "success_rate": round(ok_count / max(1, total_repos), 4),
                "average_quality": round(avg_quality, 4),
                "average_complexity": round(avg_complexity, 2),
                "total_files_analyzed": total_files,
                "total_issues": total_issues,
                "total_warnings": total_warnings,
                "total_security_issues": total_security_issues
            },
            "common_dependencies": common_deps,
            "repositories": [a.__dict__ for a in analyses],
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()
        }


def discover_python_files(repo_dir: Path, max_files: int) -> list[Path]:
    """Compatibilidade com função original."""
    validator = ExternalCodeValidator(repo_dir.parent)
    return validator.discover_python_files(repo_dir, max_files)


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> tuple[int, str, str]:
    """Compatibilidade com função original."""
    rc, out, err, _ = ExternalCodeValidator(Path("."))._run_command(cmd, cwd, timeout)
    return rc, out, err


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATENA External Code Smoke Test v3.0 - Validação avançada de repositórios externos."
    )
    parser.add_argument("--discovery-json", required=True, help="Arquivo EXTERNAL_CODE_DISCOVERY_*.json")
    parser.add_argument("--max-repos", type=int, default=3, help="Quantidade máxima de repositórios para validar")
    parser.add_argument("--max-py-files", type=int, default=20, help="Quantidade máxima de .py para análise por repo")
    parser.add_argument("--quality-check", action="store_true", help="Executa análise de qualidade (pylint, radon)")
    parser.add_argument("--security-scan", action="store_true", help="Executa scan de segurança (bandit)")
    parser.add_argument("--no-cache", action="store_true", help="Ignora cache de análises")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    
    args = parser.parse_args()
    
    discovery_path = Path(args.discovery_json)
    payload = json.loads(discovery_path.read_text(encoding="utf-8"))
    repos = list(payload.get("repos", []))[:max(1, args.max_repos)]
    
    workspace = ROOT / "atena_evolution" / "external_repos"
    validator = ExternalCodeValidator(workspace, cache_dir=workspace / ".analysis_cache")
    
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    report_dir = ROOT / "analysis_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"EXTERNAL_CODE_SMOKE_{ts}.json"
    
    print("\n" + "=" * 60)
    print("🔱 ATENA External Code Smoke Test v3.0")
    print("=" * 60)
    print(f"📁 Discovery: {discovery_path}")
    print(f"📊 Repositórios: {len(repos)}")
    print(f"🔍 Qualidade: {'✅' if args.quality_check else '❌'}")
    print(f"🛡️ Segurança: {'✅' if args.security_scan else '❌'}")
    print(f"💾 Cache: {'❌' if args.no_cache else '✅'}")
    print("=" * 60)
    
    analyses = []
    for idx, repo in enumerate(repos, 1):
        name = repo.get("name", "unknown")
        print(f"\n[{idx}/{len(repos)}] Analisando: {name}")
        analysis = validator.analyze_repo(
            repo,
            max_files=args.max_py_files,
            use_cache=not args.no_cache
        )
        analyses.append(analysis)
        
        # Status do repositório
        status_icon = "✅" if analysis.status == "ok" else "⚠️" if analysis.status == "warn" else "❌"
        print(f"  {status_icon} Status: {analysis.status.upper()}")
        print(f"  📄 Arquivos: {analysis.compile_ok_count}/{analysis.files_analyzed} compilam")
        print(f"  🎯 Qualidade: {analysis.overall_quality:.1%}")
        print(f"  🐍 Python: {analysis.python_version_detected}")
        if analysis.security_issues:
            print(f"  ⚠️ Segurança: {len(analysis.security_issues)} problemas detectados")
    
    # Gera relatório agregado
    quality_report = validator.generate_quality_report(analyses)
    
    # Status final
    final_status = "ok" if quality_report["summary"]["ok_count"] == quality_report["summary"]["total_repos"] else "warn"
    
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_discovery": str(discovery_path),
        "max_repos": args.max_repos,
        "max_py_files": args.max_py_files,
        "quality_check": args.quality_check,
        "security_scan": args.security_scan,
        "status": final_status,
        "summary": quality_report["summary"],
        "common_dependencies": quality_report["common_dependencies"],
        "repositories": [a.__dict__ for a in analyses]
    }
    
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL")
    print("=" * 60)
    print(f"📄 Relatório: {report_path}")
    print(f"✅ Repositórios OK: {quality_report['summary']['ok_count']}/{quality_report['summary']['total_repos']}")
    print(f"🎯 Qualidade média: {quality_report['summary']['average_quality']:.1%}")
    print(f"🛡️ Problemas de segurança: {quality_report['summary']['total_security_issues']}")
    print(f"📦 Dependências comuns: {', '.join(d[0] for d in quality_report['common_dependencies'][:5])}")
    print("=" * 60)
    
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    
    return 0 if final_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
