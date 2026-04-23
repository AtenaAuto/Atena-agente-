#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de programação: ATENA constrói app/site/software automaticamente."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_code_module import AtenaCodeModule
from core.atena_mission_runner import run_mission
from core.atena_runtime_contracts import MissionOutcome
from core.atena_telemetry import emit_event


def iter_project_files(output_dir: Path) -> Iterable[Path]:
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            yield path


def print_generated_code(output_dir: Path) -> None:
    print("\n📦 Código completo gerado pela ATENA:")
    printed = 0
    for file_path in iter_project_files(output_dir):
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = file_path.relative_to(output_dir)
        print("\n" + "=" * 78)
        print(f"📄 {rel}")
        print("=" * 78)
        print(content.rstrip())
        printed += 1
    if printed == 0:
        print("- (nenhum arquivo textual encontrado para exibir)")


def snapshot_text_files(output_dir: Path) -> dict[str, str]:
    snap: dict[str, str] = {}
    if not output_dir.exists():
        return snap
    for file_path in iter_project_files(output_dir):
        try:
            rel = str(file_path.relative_to(output_dir))
            snap[rel] = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return snap


def print_unified_diff(before: dict[str, str], after: dict[str, str]) -> None:
    print("\n🧩 Diff dos arquivos gerados:")
    all_files = sorted(set(before) | set(after))
    any_diff = False
    for rel in all_files:
        if before.get(rel, "") == after.get(rel, ""):
            continue
        any_diff = True
        old = before.get(rel, "").splitlines(keepends=True)
        new = after.get(rel, "").splitlines(keepends=True)
        diff = difflib.unified_diff(old, new, fromfile=f"a/{rel}", tofile=f"b/{rel}")
        print("".join(diff).rstrip() or f"(arquivo alterado: {rel})")
    if not any_diff:
        print("- sem alterações de conteúdo")


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Code Build Mission")
    parser.add_argument("--type", dest="project_type", choices=["site", "api", "cli"], default="site")
    parser.add_argument("--name", dest="project_name", default="atena_app")
    parser.add_argument(
        "--template",
        choices=["basic", "landing-page", "portfolio", "dashboard", "blog"],
        default="basic",
        help="Template visual para tipo site",
    )
    parser.add_argument("--show-diff", action="store_true", help="Exibe diff textual dos arquivos gerados.")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Executa validação mínima (arquivos não vazios) antes de concluir.",
    )
    args = parser.parse_args()

    builder = AtenaCodeModule(ROOT)
    mission_id = f"code-build:{args.project_name}"

    def _execute() -> MissionOutcome:
        out_dir = builder.generated_root / "".join(
            ch for ch in args.project_name if ch.isalnum() or ch in ("-", "_")
        ).strip("-_")
        before = snapshot_text_files(out_dir)
        emit_event(
            "code_build_start",
            mission_id,
            "started",
            project_type=args.project_type,
            template=args.template,
        )
        result = builder.build(args.project_type, args.project_name, template=args.template)

        if not result.ok:
            emit_event("code_build_finish", mission_id, "failed", reason=result.message)
            print(f"❌ Falha: {result.message}")
            return MissionOutcome(mission_id=mission_id, status="failed", score=0.0, details=result.message)

        after = snapshot_text_files(Path(result.output_dir))
        if args.validate:
            empty_files = [name for name, content in after.items() if not content.strip()]
            if empty_files:
                emit_event("code_build_finish", mission_id, "failed", reason="empty_files", files=empty_files)
                print(f"❌ Falha de validação: arquivos vazios detectados: {empty_files}")
                return MissionOutcome(mission_id=mission_id, status="failed", score=0.0, details="validation_failed")

        print("🧠💻 ATENA Code Module")
        print(f"Projeto: {result.project_name}")
        print(f"Tipo: {result.project_type}")
        print(f"Template: {result.template}")
        print(f"Saída: {result.output_dir}")
        print("Status: sucesso")
        if args.show_diff:
            print_unified_diff(before, after)
        print_generated_code(Path(result.output_dir))
        emit_event(
            "code_build_finish",
            mission_id,
            "ok",
            output_dir=result.output_dir,
            files_generated=len(after),
        )
        return MissionOutcome(mission_id=mission_id, status="ok", score=1.0, details=result.output_dir)

    outcome = run_mission(mission_id, _execute)
    return 0 if outcome.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
