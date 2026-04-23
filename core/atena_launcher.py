#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launcher bonito da ATENA-Like (estilo CLI moderno)."""

from __future__ import annotations

import subprocess
import sys
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS = {
    "start": ROOT / "core" / "main.py",
    "invoke": ROOT / "protocols" / "atena_invoke.py",
    "dialog": ROOT / "protocols" / "atena_dialogue_session.py",
    "assistant": ROOT / "core" / "atena_terminal_assistant.py",
    "doctor": ROOT / "core" / "atena_doctor.py",
    "fix": ROOT / "core" / "atena_fix.py",
    "skills": ROOT / "core" / "atena_skills.py",
    "pipeline": ROOT / "core" / "atena_pipeline.py",
    "research-lab": ROOT / "protocols" / "atena_research_lab_mission.py",
    "future-ai": ROOT / "protocols" / "atena_future_ai_mission.py",
    "learn-status": ROOT / "core" / "atena_learning_status.py",
    "push-safe": ROOT / "core" / "atena_push_safe.py",
    "dashboard": ROOT / "core" / "atena_local_dashboard.py",
    "codex-advanced": ROOT / "protocols" / "atena_codex_advanced_mission.py",
    "modules-smoke": ROOT / "protocols" / "atena_module_smoke_mission.py",
    "genius": ROOT / "protocols" / "atena_genius_mission.py",
    "guardian": ROOT / "protocols" / "atena_guardian_mission.py",
    "production-ready": ROOT / "protocols" / "atena_production_mission.py",
    "code-build": ROOT / "protocols" / "atena_code_build_mission.py",
    "telemetry-report": ROOT / "protocols" / "atena_telemetry_report_mission.py",
    "evolution-scorecard": ROOT / "core" / "atena_evolution_scorecard.py",
    "memory-relevance-audit": ROOT / "core" / "atena_memory_relevance_audit.py",
    "memory-maintenance": ROOT / "core" / "atena_memory_maintenance.py",
    "weekly-evolution-loop": ROOT / "core" / "atena_weekly_evolution_loop.py",
    "professional-launch": ROOT / "protocols" / "atena_professional_launch_mission.py",
    "enterprise-readiness": ROOT / "protocols" / "atena_enterprise_readiness_mission.py",
    "enterprise-advanced": ROOT / "protocols" / "atena_enterprise_advanced_mission.py",
    "go-no-go": ROOT / "protocols" / "atena_go_no_go_mission.py",
    "kyros": ROOT / "core" / "atena_kyros_mode.py",
    "production-center": ROOT / "core" / "atena_production_center.py",
    "orchestrator-mission": ROOT / "protocols" / "atena_orchestrator_mission.py",
    "agi-uplift": ROOT / "protocols" / "atena_agi_uplift_mission.py",
    "agi-external-validation": ROOT / "protocols" / "atena_agi_external_validation_mission.py",
    "digital-organism-audit": ROOT / "protocols" / "atena_digital_organism_audit_mission.py",
    "digital-organism-live-cycle": ROOT / "protocols" / "atena_digital_organism_live_cycle_mission.py",
    "bootstrap": ROOT / "core" / "atena_env_bootstrap.py",
    "secret-scan": ROOT / "core" / "atena_secret_scan.py",
    "hacker-recon": ROOT / "core" / "atena_hacker_recon.py",
}

ALIASES = {
    "atena-like": "assistant",
    "like": "assistant",
    "hacker": "hacker-recon",
}

MODULE_NOT_FOUND_RE = re.compile(r"No module named ['\"]([A-Za-z0-9_.-]+)['\"]")
PIP_NAME_OVERRIDES = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
}


def render_help() -> None:
    banner = r"""
    █████╗ ████████╗███████╗███╗   ██╗ █████╗
   ██╔══██╗╚══██╔══╝██╔════╝████╗  ██║██╔══██╗
   ███████║   ██║   █████╗  ██╔██╗ ██║███████║
   ██╔══██║   ██║   ██╔══╝  ██║╚██╗██║██╔══██║
   ██║  ██║   ██║   ███████╗██║ ╚████║██║  ██║
   ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝
    """
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        console.print("\n[bold cyan]🔱 ATENA-Like CLI[/bold cyan]")
        console.print(f"[bold green]{banner}[/bold green]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Comando")
        table.add_column("Descrição")
        table.add_row("./atena", "Inicia o núcleo principal")
        table.add_row("./atena start", "Núcleo principal")
        table.add_row("./atena invoke", "Missão avançada de criação de script")
        table.add_row("./atena dialog", "Sessão de diálogo")
        table.add_row("./atena assistant", "Modo assistente com evolução em background")
        table.add_row("./atena doctor", "Diagnóstico rápido (estilo healthcheck)")
        table.add_row("./atena doctor --full", "Diagnóstico completo (runtime)")
        table.add_row("./atena fix", "Auto-correções básicas do ambiente")
        table.add_row("./atena skills", "Descoberta + validação das skills")
        table.add_row("./atena pipeline", "Pipeline: web -> análise -> relatório")
        table.add_row("./atena research-lab", "Gera proposta avançada para evolução da ATENA")
        table.add_row("./atena future-ai", "Cria blueprint prático de inovação para o futuro da IA")
        table.add_row("./atena learn-status", "Mostra memória de aprendizado persistida")
        table.add_row("./atena push-safe", "Push apenas após doctor --full aprovado")
        table.add_row("./atena dashboard", "Dashboard local com chat estilo assistant")
        table.add_row("./atena codex-advanced", "Missão avançada usando módulo AtenaCodex")
        table.add_row("./atena modules-smoke", "Executa smoke test módulo por módulo")
        table.add_row("./atena genius", "Executa missão genial multiobjetivo")
        table.add_row("./atena guardian", "Gate essencial: autopilot + smoke + blockers")
        table.add_row("./atena production-ready", "Gate final: doctor + guardian")
        table.add_row("./atena code-build", "Módulo programação: cria site/api/cli (templates para site)")
        table.add_row("./atena telemetry-report", "Consolida métricas das missões")
        table.add_row("./atena evolution-scorecard", "Gera scorecard contínuo (segurança, SRE, pesquisa, qualidade)")
        table.add_row("./atena memory-relevance-audit", "Audita relevância da memória de longo prazo")
        table.add_row("./atena memory-maintenance", "Executa pruning de memórias irrelevantes")
        table.add_row("./atena weekly-evolution-loop", "Executa ciclo semanal completo de evolução")
        table.add_row("./atena professional-launch", "Cria plano de lançamento profissional (GTM + operação)")
        table.add_row("./atena enterprise-readiness", "Trilha empresarial com score/threshold (doctor+gate+launch+code-build)")
        table.add_row("./atena enterprise-advanced", "Memória RAG + Planner/Executor/Critic + SRE hardening + skill validation")
        table.add_row("./atena go-no-go", "Executa checklist com 5 testes de prontidão para divulgação")
        table.add_row("./atena kyros", "Modo Kyros: prontidão operacional + execução guiada")
        table.add_row("./atena production-center", "CLI de integração dos módulos de produção (RBAC/telemetria/quality)")
        table.add_row("./atena orchestrator-mission", "Missão avançada com orquestrador (checkpoint+retry+fallback)")
        table.add_row("./atena agi-uplift", "Missão de elevação AGI-like (memória/avaliação/segurança)")
        table.add_row("./atena agi-external-validation", "Validação externa AGI-like com score independente")
        table.add_row("./atena digital-organism-audit", "Auditoria automática: score + estágio de organismo digital")
        table.add_row(
            "./atena digital-organism-live-cycle",
            "Aprende na internet, cria projeto, executa e testa (suporta --challenge-level agi-only)",
        )
        table.add_row("./atena bootstrap", "Instala dependências mínimas para guardian/produção")
        table.add_row("./atena secret-scan", "Escaneia o repositório por vazamento de segredos")
        table.add_row("./atena hacker-recon --topic <tópico>", "Hacker Recon avançado (batch/paralelo/retry/JSON/histórico)")
        table.add_row("./atena atena-like", "Alias do modo assistant")
        table.add_row("./atena help", "Exibe esta ajuda")
        console.print(table)
        console.print("\n[dim]Dica: use /help dentro do modo assistant.[/dim]\n")
    except Exception:
        print("🔱 ATENA-Like CLI\n")
        print(banner)
        print("Uso:")
        print("  ./atena                 # inicia o núcleo principal")
        print("  ./atena start           # núcleo principal")
        print("  ./atena invoke          # missão avançada")
        print("  ./atena dialog          # sessão de diálogo")
        print("  ./atena assistant       # assistente + evolução")
        print("  ./atena doctor          # diagnóstico rápido")
        print("  ./atena doctor --full   # diagnóstico completo")
        print("  ./atena fix             # auto-correções básicas")
        print("  ./atena skills          # descoberta/validação de skills")
        print("  ./atena pipeline        # web -> análise -> relatório")
        print("  ./atena research-lab    # proposta avançada de evolução")
        print("  ./atena future-ai       # blueprint prático para o futuro da IA")
        print("  ./atena learn-status    # status do aprendizado persistente")
        print("  ./atena push-safe       # push condicionado a aprovação")
        print("  ./atena dashboard       # dashboard local com chat")
        print("  ./atena codex-advanced  # missão avançada com AtenaCodex")
        print("  ./atena modules-smoke   # smoke test módulo por módulo")
        print("  ./atena genius          # missão genial multiobjetivo")
        print("  ./atena guardian        # gate essencial de prontidão")
        print("  ./atena production-ready # gate final de produção")
        print("  ./atena code-build       # gera app/site/software (site com templates)")
        print("  ./atena telemetry-report # relatório de telemetria")
        print("  ./atena evolution-scorecard # scorecard contínuo de evolução")
        print("  ./atena memory-relevance-audit # auditoria de relevância da memória")
        print("  ./atena memory-maintenance # pruning de memórias irrelevantes")
        print("  ./atena weekly-evolution-loop # ciclo semanal completo de evolução")
        print("  ./atena professional-launch # plano de lançamento profissional")
        print("  ./atena enterprise-readiness # trilha empresarial com score de aprovação")
        print("  ./atena enterprise-advanced # stack avançada enterprise (RAG/planner/SRE/skills)")
        print("  ./atena go-no-go         # checklist com 5 testes de prontidão")
        print("  ./atena kyros            # modo Kyros (prontidão + execução guiada)")
        print("  ./atena production-center # CLI de integração dos módulos de produção")
        print("  ./atena orchestrator-mission # missão avançada com orquestrador")
        print("  ./atena agi-uplift      # missão de elevação AGI-like")
        print("  ./atena agi-external-validation # validação externa AGI-like")
        print("  ./atena digital-organism-audit # auditoria automática de organismo digital")
        print("  ./atena digital-organism-live-cycle # aprende na internet, cria, executa e testa (use --challenge-level agi-only)")
        print("  ./atena bootstrap        # instala dependências mínimas de runtime")
        print("  ./atena secret-scan      # escaneia o repositório por vazamento de segredos")
        print("  ./atena hacker-recon --topic <tópico>|--batch-file arq [...flags...] [--parallel N] [--retries N]")
        print("  ./atena atena-like      # alias do assistant")
        print("  ./atena help            # ajuda")


def normalize_command(arg: str | None) -> str:
    if not arg:
        return "start"
    arg = arg.strip().lower()
    if arg in ("-h", "--help", "help"):
        return "help"
    return ALIASES.get(arg, arg)


def _extract_missing_module(stderr: str, stdout: str) -> str | None:
    combined = f"{stderr}\n{stdout}"
    match = MODULE_NOT_FOUND_RE.search(combined)
    if not match:
        return None
    return match.group(1)


def _module_to_pip_name(module_name: str) -> str:
    root = module_name.split(".")[0]
    return PIP_NAME_OVERRIDES.get(root, root)


def _run_with_auto_dep_repair(
    script: Path,
    script_args: list[str],
    env: dict[str, str],
    interactive: bool = False,
) -> int:
    auto_install = env.get("ATENA_AUTO_INSTALL_MISSING_DEPS", "1") == "1"
    if interactive:
        first = subprocess.run(
            [sys.executable, str(script), *script_args],
            cwd=str(ROOT),
            env=env,
            check=False,
        )
        return first.returncode

    first = subprocess.run(
        [sys.executable, str(script), *script_args],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    if first.stdout:
        print(first.stdout, end="")
    if first.stderr:
        print(first.stderr, end="", file=sys.stderr)

    if first.returncode == 0 or not auto_install:
        return first.returncode

    missing = _extract_missing_module(first.stderr or "", first.stdout or "")
    if not missing:
        return first.returncode

    pkg = _module_to_pip_name(missing)
    print(f"🔧 ATENA auto-deps: módulo ausente detectado ({missing}). Instalando `{pkg}`...")
    pip_proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg],
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    if pip_proc.returncode != 0:
        print(f"❌ Falha ao instalar dependência automática: {pkg}")
        return first.returncode

    print("✅ Dependência instalada. Reexecutando comando...")
    retry = subprocess.run([sys.executable, str(script), *script_args], cwd=str(ROOT), env=env)
    return retry.returncode


def main(argv: list[str]) -> int:
    command = normalize_command(argv[1] if len(argv) > 1 else None)
    if command == "help":
        render_help()
        return 0

    script = COMMANDS.get(command)
    if script is None:
        print(f"Comando inválido: {command}\n")
        render_help()
        return 2

    env = os.environ.copy()
    if env.get("ATENA_AUTO_BOOTSTRAP", "1") == "1" and command not in {"help", "bootstrap", "production-center"}:
        bootstrap_cmd = [sys.executable, str(ROOT / "core" / "atena_env_bootstrap.py")]
        print("🔧 ATENA bootstrap: verificando dependências mínimas...")
        bootstrap_timeout = int(env.get("ATENA_BOOTSTRAP_TIMEOUT_S", "180"))
        bootstrap_proc = subprocess.run(
            bootstrap_cmd,
            cwd=str(ROOT),
            check=False,
            timeout=bootstrap_timeout,
        )
        if bootstrap_proc.returncode != 0:
            if env.get("ATENA_STRICT_BOOTSTRAP", "0") == "1":
                print("❌ Bootstrap falhou e ATENA_STRICT_BOOTSTRAP=1: abortando execução.")
                return bootstrap_proc.returncode
            print("⚠️ Bootstrap retornou falha; continuando execução mesmo assim.")

    if command in {"start", "assistant"} and env.get("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1") == "1":
        print("🧠 ATENA: preparando LLM local padrão (download automático quando necessário)...")
        prep_cmd = [
            sys.executable,
            "-c",
            (
                "from core.atena_llm_router import AtenaLLMRouter;"
                "r=AtenaLLMRouter();"
                "ok,msg=(r.auto_prepare_result or r.prepare_free_local_model());"
                "print(msg);"
                "raise SystemExit(0 if ok else 0)"
            ),
        ]
        prepare_timeout = int(env.get("ATENA_MODEL_PREP_TIMEOUT_S", "300"))
        try:
            subprocess.run(prep_cmd, cwd=str(ROOT), check=False, timeout=prepare_timeout)
        except subprocess.TimeoutExpired:
            print(f"⚠️ Preparação do LLM local excedeu {prepare_timeout}s; seguindo com fallback.")
        # Evita repetir preparação pesada no processo filho do assistant/start.
        env["ATENA_AUTO_PREPARE_LOCAL_MODEL"] = "0"

    interactive = command in {"assistant", "dialog"}
    return _run_with_auto_dep_repair(script, argv[2:], env, interactive=interactive)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
