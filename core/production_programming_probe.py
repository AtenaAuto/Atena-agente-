#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔱 ATENA Programming Smoke Test v3.0 - Validação Avançada de Geração de Código
Sistema completo de teste de capacidade de programação da ATENA.

Recursos:
- ✅ Geração e validação de múltiplos tipos de projeto (site, api, cli, microservice)
- 🔧 Compilação e análise estática de código gerado
- 📊 Métricas de qualidade de código (complexidade, linhas, imports)
- 🧪 Execução de smoke tests nos artefatos gerados
- 📈 Scoring multidimensional de capacidade de programação
- 🔄 Validação de boas práticas (type hints, docstrings, estrutura)
- 🎯 Detecção de padrões de código seguro
- 📝 Geração de relatório detalhado com recomendações
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import importlib.util
import py_compile
import hashlib
import re

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


@dataclass
class CodeQualityMetrics:
    """Métricas de qualidade de código."""
    lines: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0
    avg_complexity: float = 0.0
    maintainability_index: float = 0.0
    has_docstrings: bool = False
    has_type_hints: bool = False
    security_score: float = 1.0
    best_practices_score: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "lines": self.lines,
            "functions": self.functions,
            "classes": self.classes,
            "imports": self.imports,
            "avg_complexity": round(self.avg_complexity, 2),
            "maintainability_index": round(self.maintainability_index, 2),
            "has_docstrings": self.has_docstrings,
            "has_type_hints": self.has_type_hints,
            "security_score": round(self.security_score, 2),
            "best_practices_score": round(self.best_practices_score, 2)
        }


@dataclass
class ValidationResult:
    """Resultado da validação de um projeto."""
    project_type: str
    project_name: str
    build_ok: bool
    compile_ok: bool
    run_ok: bool
    quality_metrics: CodeQualityMetrics
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    output_preview: str = ""
    execution_time_ms: float = 0.0


class AtenaProgrammingValidator:
    """
    Validador completo da capacidade de programação da ATENA.
    Testa geração, compilação, execução e qualidade do código gerado.
    """
    
    def __init__(self, root: Path):
        self.root = Path(root)
        self.results: List[ValidationResult] = []
        self._temp_dir: Optional[Path] = None
        self._setup_environment()
    
    def _setup_environment(self):
        """Configura ambiente de teste."""
        self._temp_dir = Path(tempfile.mkdtemp(prefix="atena_smoke_"))
        # Adiciona ao path para importação de módulos gerados
        if str(self._temp_dir) not in sys.path:
            sys.path.insert(0, str(self._temp_dir))
        print(f"🔧 Ambiente de teste: {self._temp_dir}")
    
    def _cleanup(self):
        """Limpa ambiente de teste."""
        if self._temp_dir and self._temp_dir.exists():
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
    
    def _analyze_code_quality(self, code: str, file_path: Optional[Path] = None) -> CodeQualityMetrics:
        """
        Analisa qualidade do código gerado.
        """
        metrics = CodeQualityMetrics()
        
        try:
            tree = ast.parse(code)
            
            # Contagem básica
            metrics.lines = len(code.splitlines())
            metrics.functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            metrics.classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            metrics.imports = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
            
            # Verifica docstrings
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    if ast.get_docstring(node):
                        metrics.has_docstrings = True
                        break
            
            # Verifica type hints
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.returns or any(arg.annotation for arg in node.args.args):
                        metrics.has_type_hints = True
                        break
            
            # Complexidade ciclomática
            if HAS_RADON:
                try:
                    blocks = radon_cc.cc_visit(code)
                    if blocks:
                        metrics.avg_complexity = sum(b.complexity for b in blocks) / len(blocks)
                except Exception:
                    pass
            
            # Análise de segurança (padrões perigosos)
            dangerous_patterns = [
                (r'eval\s*\(', 0.3, "uso de eval()"),
                (r'exec\s*\(', 0.3, "uso de exec()"),
                (r'__import__\s*\(', 0.2, "import dinâmico"),
                (r'os\.system\s*\(', 0.4, "chamada de sistema"),
                (r'subprocess\.call', 0.2, "subprocess sem validação"),
                (r'password\s*=\s*[\'"][^\'"]+[\'"]', 0.5, "hardcoded password"),
                (r'token\s*=\s*[\'"][^\'"]+[\'"]', 0.5, "hardcoded token"),
            ]
            
            security_issues = 0
            for pattern, penalty, _ in dangerous_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    security_issues += penalty
            metrics.security_score = max(0.0, 1.0 - security_issues)
            
            # Boas práticas
            best_practices_count = 0
            total_checks = 6
            
            if metrics.has_docstrings:
                best_practices_count += 1
            if metrics.has_type_hints:
                best_practices_count += 1
            if metrics.functions > 0:
                best_practices_count += 1
            if metrics.lines > 10:
                best_practices_count += 1
            if metrics.classes > 0:
                best_practices_count += 1
            if metrics.imports > 0:
                best_practices_count += 1
            
            metrics.best_practices_score = best_practices_count / total_checks
            
            # Índice de manutenibilidade (simplificado)
            metrics.maintainability_index = (
                171 - 5.2 * math.log(metrics.lines) - 
                0.23 * metrics.avg_complexity - 
                16.2 * math.log(max(1, metrics.functions))
            ) / 171
            metrics.maintainability_index = max(0.0, min(1.0, metrics.maintainability_index))
            
        except SyntaxError as e:
            metrics.security_score = 0.0
            print(f"❌ Erro de sintaxe na análise: {e}")
        
        return metrics
    
    def _run_pylint_analysis(self, file_path: Path) -> Tuple[float, List[str], List[str]]:
        """Executa análise pylint no arquivo gerado."""
        if not HAS_PYLINT or not file_path.exists():
            return 0.8, [], ["Pylint não disponível"]
        
        class CapturingReporter(BaseReporter):
            def __init__(self):
                super().__init__()
                self.messages = []
            
            def handle_message(self, msg):
                self.messages.append(f"{msg.msg_id}: {msg.msg}")
        
        try:
            reporter = CapturingReporter()
            lint.Run([str(file_path)], reporter=reporter, exit=False)
            
            errors = [m for m in reporter.messages if "error" in m.lower()]
            warnings = [m for m in reporter.messages if "warning" in m.lower()]
            
            # Score baseado em número de problemas
            total_issues = len(errors) + len(warnings) * 0.5
            score = max(0.0, 1.0 - (total_issues / 50))
            
            return score, errors[:10], warnings[:10]
        except Exception as e:
            return 0.5, [str(e)], []
    
    def _try_execute_safe(self, file_path: Path, timeout: int = 5) -> Tuple[bool, str, float]:
        """Tenta executar o código de forma segura em subprocesso."""
        import time
        
        start = time.time()
        try:
            # Executa em subprocesso isolado
            result = subprocess.run(
                [sys.executable, str(file_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._temp_dir)
            )
            elapsed = (time.time() - start) * 1000
            
            if result.returncode == 0:
                output = result.stdout.strip()
                return True, output[:500], elapsed
            else:
                error = result.stderr.strip()
                return False, error[:500], elapsed
        except subprocess.TimeoutExpired:
            return False, f"Timeout após {timeout}s", timeout * 1000
        except Exception as e:
            return False, str(e), (time.time() - start) * 1000
    
    def _extract_project_files(self, project_dir: Path) -> Dict[str, str]:
        """Extrai conteúdo dos arquivos do projeto."""
        files = {}
        for py_file in project_dir.rglob("*.py"):
            try:
                rel_path = py_file.relative_to(project_dir)
                files[str(rel_path)] = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        return files
    
    def validate_project(
        self,
        code_module: Any,
        project_type: str,
        project_name: str,
        template: Optional[str] = None,
        run_tests: bool = True
    ) -> ValidationResult:
        """
        Valida um projeto gerado pela ATENA.
        """
        print(f"\n📦 Validando projeto: {project_type}/{project_name}")
        
        errors = []
        warnings = []
        
        # 1. Geração do projeto
        try:
            if project_type == "site" and template:
                result = code_module.build(project_type, project_name, template=template)
            else:
                result = code_module.build(project_type, project_name)
            
            build_ok = result.ok
            if not build_ok:
                errors.append(f"Falha na geração: {result.message}")
                warnings.append("Não foi possível gerar o projeto")
            
            project_dir = Path(result.output_dir) if result.ok else None
            
        except Exception as e:
            build_ok = False
            errors.append(f"Exceção na geração: {e}")
            project_dir = None
        
        # Se não gerou, retorna resultado parcial
        if not build_ok or not project_dir or not project_dir.exists():
            return ValidationResult(
                project_type=project_type,
                project_name=project_name,
                build_ok=False,
                compile_ok=False,
                run_ok=False,
                quality_metrics=CodeQualityMetrics(),
                errors=errors,
                warnings=warnings
            )
        
        # Copia para o diretório temporário
        dest_dir = self._temp_dir / project_name
        import shutil
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(project_dir, dest_dir)
        
        # 2. Verificação de arquivos
        files = self._extract_project_files(dest_dir)
        if not files:
            warnings.append("Nenhum arquivo Python encontrado no projeto")
            
        # 3. Compilação e análise de qualidade
        quality_metrics = CodeQualityMetrics()
        compile_ok = True
        main_file = dest_dir / "main.py"
        
        for file_path, file_content in files.items():
            # Compilação
            full_path = dest_dir / file_path
            try:
                py_compile.compile(str(full_path), doraise=True)
            except py_compile.PyCompileError as e:
                compile_ok = False
                errors.append(f"Erro de compilação em {file_path}: {e}")
            
            # Análise de qualidade (apenas para main.py ou arquivos principais)
            if "main" in file_path.lower() or "app" in file_path.lower():
                metrics = self._analyze_code_quality(file_content, full_path)
                quality_metrics = metrics  # Usa métricas do arquivo principal
        
        # 4. Análise com pylint
        if main_file.exists():
            pylint_score, pylint_errors, pylint_warnings = self._run_pylint_analysis(main_file)
            quality_metrics.best_practices_score = (quality_metrics.best_practices_score + pylint_score) / 2
            errors.extend(pylint_errors[:5])
            warnings.extend(pylint_warnings[:5])
        
        # 5. Execução do código (se possível)
        run_ok = False
        output_preview = ""
        execution_time_ms = 0.0
        
        if run_tests and main_file.exists() and compile_ok:
            print(f"  🚀 Executando {main_file.name}...")
            run_ok, output_preview, execution_time_ms = self._try_execute_safe(main_file, timeout=10)
            if not run_ok:
                warnings.append(f"Execução falhou: {output_preview[:100]}")
        
        return ValidationResult(
            project_type=project_type,
            project_name=project_name,
            build_ok=build_ok,
            compile_ok=compile_ok,
            run_ok=run_ok,
            quality_metrics=quality_metrics,
            errors=errors,
            warnings=warnings,
            output_preview=output_preview,
            execution_time_ms=execution_time_ms
        )


def has_non_empty_files(project_dir: Path) -> Tuple[bool, int, Dict[str, int]]:
    """
    Verifica se o projeto tem arquivos não vazios e retorna estatísticas.
    
    Returns:
        Tuple[has_content, file_count, stats_by_extension]
    """
    text_files = [p for p in project_dir.rglob("*") if p.is_file()]
    
    if not text_files:
        return False, 0, {}
    
    stats = {}
    total_size = 0
    
    for file_path in text_files:
        ext = file_path.suffix or "no_ext"
        try:
            size = file_path.stat().st_size
            total_size += size
            stats[ext] = stats.get(ext, 0) + 1
            
            if size > 0 and file_path.read_text(encoding="utf-8", errors="ignore").strip():
                pass  # tem conteúdo
        except (UnicodeDecodeError, OSError):
            continue
    
    has_content = total_size > 0
    return has_content, len(text_files), stats


def run_programming_probe(
    root: Path,
    prefix: str = "probe",
    site_template: str = "dashboard",
    run_tests: bool = True,
    validate_all: bool = True
) -> Dict[str, Any]:
    """
    Executa sonda completa de capacidade de programação da ATENA.
    
    Args:
        root: Diretório raiz do projeto
        prefix: Prefixo para nomes de projeto
        site_template: Template para projetos site
        run_tests: Se deve executar os códigos gerados
        validate_all: Se deve validar todos os tipos de projeto
    
    Returns:
        Dicionário com resultados completos da validação
    """
    from modules.atena_code_module import AtenaCodeModule
    
    module = AtenaCodeModule(root)
    validator = AtenaProgrammingValidator(root)
    results = []
    
    # Projetos a gerar
    projects = [
        ("site", f"{prefix}_site", site_template),
        ("api", f"{prefix}_api", None),
        ("cli", f"{prefix}_cli", None),
    ]
    
    if validate_all:
        projects.extend([
            ("microservice", f"{prefix}_microservice", None),
            ("library", f"{prefix}_lib", None),
        ])
    
    print("\n" + "=" * 60)
    print("🔱 ATENA Programming Smoke Test v3.0")
    print("=" * 60)
    print(f"📁 Root: {root}")
    print(f"🏷️  Prefixo: {prefix}")
    print(f"🧪 Executar testes: {run_tests}")
    print(f"📊 Tipos de projeto: {len(projects)}")
    print("=" * 60)
    
    for project_type, name, template in projects:
        result = validator.validate_project(
            code_module=module,
            project_type=project_type,
            project_name=name,
            template=template,
            run_tests=run_tests
        )
        results.append(result)
        
        # Status do projeto
        status_icon = "✅" if (result.build_ok and result.compile_ok) else "❌"
        print(f"\n{status_icon} {project_type.upper()}: {name}")
        print(f"   Build: {'✅' if result.build_ok else '❌'} | Compile: {'✅' if result.compile_ok else '❌'} | Run: {'✅' if result.run_ok else '❌'}")
        print("   Qualidade: avaliação automática registrada")
        if result.errors:
            print(f"   ⚠️ Erros: {len(result.errors)}")
        if result.warnings:
            print(f"   ⚠️ Avisos: {len(result.warnings)}")
    
    # Agregação de resultados
    checks = []
    generated_projects = {}
    quality_scores = []
    
    for r in results:
        # Verificações básicas
        checks.append({
            "name": f"build_{r.project_type}",
            "ok": r.build_ok,
            "details": f"Projeto {r.project_name} gerado"
        })
        checks.append({
            "name": f"compile_{r.project_type}",
            "ok": r.compile_ok,
            "details": f"Compilação de {r.project_name}"
        })
        checks.append({
            "name": f"quality_{r.project_type}",
            "ok": r.quality_metrics.best_practices_score > 0.6,
            "details": f"Score de qualidade: {r.quality_metrics.best_practices_score:.2f}"
        })
        
        # Métricas de qualidade
        quality_scores.append(r.quality_metrics.best_practices_score)
        
        # Projetos gerados
        generated_projects[r.project_type] = {
            "ok": r.build_ok,
            "project_name": r.project_name,
            "output_dir": str(validator._temp_dir / r.project_name) if r.build_ok else None,
            "compile_ok": r.compile_ok,
            "run_ok": r.run_ok,
            "quality_score": r.quality_metrics.best_practices_score,
            "errors": r.errors[:5],
            "warnings": r.warnings[:5]
        }
    
    # Estatísticas finais
    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    score = round(passed / total, 4) if total else 0.0
    avg_quality = round(sum(quality_scores) / max(1, len(quality_scores)), 4)
    
    # Status final
    if passed == total and total > 0:
        status = "ok"
        recommendation = "✅ ATENA consegue programar com excelência! Todos os projetos passaram nos testes."
    elif passed >= total * 0.7:
        status = "partial"
        recommendation = "⚠️ ATENA programa bem, mas alguns ajustes são necessários. Revise os warnings."
    else:
        status = "warn"
        recommendation = "❌ ATENA encontrou dificuldades na geração de código. Verifique dependências e templates."
    
    # Dica adicional baseada em qualidade
    if avg_quality > 0.8:
        recommendation += " Código de alta qualidade, com boas práticas e documentação."
    elif avg_quality > 0.6:
        recommendation += " Código funcional, recomenda-se adicionar docstrings e type hints."
    else:
        recommendation += " Sugere-se revisar padrões de código e adicionar mais documentação."
    
    # Limpeza (opcional - comentar para inspecionar)
    # validator._cleanup()
    
    return {
        "status": status,
        "score": score,
        "passed": passed,
        "total": total,
        "avg_quality_score": avg_quality,
        "checks": checks,
        "generated_projects": generated_projects,
        "recommendation": recommendation,
        "timestamp": datetime.now().isoformat(),
        "details": {
            "projects_tested": len(results),
            "compile_success_rate": sum(1 for r in results if r.compile_ok) / len(results),
            "run_success_rate": sum(1 for r in results if r.run_ok) / len(results),
            "avg_maintainability": round(sum(r.quality_metrics.maintainability_index for r in results) / len(results), 3),
            "has_type_hints": any(r.quality_metrics.has_type_hints for r in results),
            "has_docstrings": any(r.quality_metrics.has_docstrings for r in results),
        }
    }


def print_summary_report(result: Dict[str, Any]):
    """Imprime relatório resumido formatado."""
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO DO SMOKE TEST")
    print("=" * 60)
    
    status_icon = "✅" if result["status"] == "ok" else "⚠️" if result["status"] == "partial" else "❌"
    print(f"{status_icon} Status: {result['status'].upper()}")
    print(f"📈 Score: {result['score']:.2%} ({result['passed']}/{result['total']} verificações)")
    print(f"🎯 Qualidade média: {result['avg_quality_score']:.2%}")
    
    print("\n📁 Projetos Gerados:")
    for proj_type, details in result["generated_projects"].items():
        icon = "✅" if details["ok"] else "❌"
        compile_icon = "✅" if details.get("compile_ok") else "❌"
        run_icon = "✅" if details.get("run_ok") else "❌"
        quality = details.get("quality_score", 0)
        print(f"  {icon} {proj_type.upper()}: {compile_icon} {run_icon} | Qualidade: {quality:.0%}")
    
    print(f"\n💡 Recomendação: {result['recommendation']}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ATENA Programming Smoke Test")
    parser.add_argument("--root", type=str, default=".", help="Diretório raiz do projeto")
    parser.add_argument("--prefix", type=str, default="smoke_test", help="Prefixo para projetos")
    parser.add_argument("--template", type=str, default="dashboard", help="Template para site")
    parser.add_argument("--no-run", action="store_true", help="Não executar códigos gerados")
    parser.add_argument("--full", action="store_true", help="Validar todos os tipos de projeto")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    
    args = parser.parse_args()
    
    result = run_programming_probe(
        root=Path(args.root),
        prefix=args.prefix,
        site_template=args.template,
        run_tests=not args.no_run,
        validate_all=args.full
    )
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_summary_report(result)
    
    # Exit code para CI
    sys.exit(0 if result["status"] == "ok" else 1)
