#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test do módulo de programação da ATENA."""

from __future__ import annotations

import py_compile
from pathlib import Path

from modules.atena_code_module import AtenaCodeModule


def _has_non_empty_files(project_dir: Path) -> bool:
    text_files = [p for p in project_dir.rglob("*") if p.is_file()]
    if not text_files:
        return False
    for file_path in text_files:
        try:
            if file_path.read_text(encoding="utf-8").strip():
                return True
        except UnicodeDecodeError:
            continue
    return False


def run_programming_probe(root: Path, prefix: str = "probe", site_template: str = "dashboard") -> dict[str, object]:
    module = AtenaCodeModule(root)
    checks: list[dict[str, object]] = []
    generated: dict[str, dict[str, object]] = {}

    for project_type in ("site", "api", "cli"):
        project_name = f"{prefix}_{project_type}"
        if project_type == "site":
            result = module.build(project_type, project_name, template=site_template)  # type: ignore[arg-type]
        else:
            result = module.build(project_type, project_name)
        project_payload = {
            "ok": result.ok,
            "project_name": result.project_name,
            "output_dir": result.output_dir,
            "message": result.message,
        }
        generated[project_type] = project_payload
        checks.append({"name": f"build_{project_type}", "ok": result.ok, "details": result.message})

        if not result.ok:
            continue

        project_dir = Path(result.output_dir)
        has_content = _has_non_empty_files(project_dir)
        checks.append(
            {
                "name": f"non_empty_files_{project_type}",
                "ok": has_content,
                "details": "files found" if has_content else "no text files with content",
            }
        )

        if project_type in {"api", "cli"}:
            main_py = project_dir / "main.py"
            try:
                py_compile.compile(str(main_py), doraise=True)
            except py_compile.PyCompileError as exc:
                checks.append({"name": f"compile_{project_type}", "ok": False, "details": str(exc)})
            else:
                checks.append({"name": f"compile_{project_type}", "ok": True, "details": str(main_py)})

    passed = sum(1 for item in checks if item["ok"] is True)
    total = len(checks)
    score = round(passed / total, 4) if total else 0.0
    status = "ok" if passed == total and total > 0 else "warn"
    recommendation = "ATENA consegue programar e os artefatos base passaram no smoke test." if status == "ok" else "ATENA programou parcialmente; revisar checks com falha."

    return {
        "status": status,
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "generated_projects": generated,
        "recommendation": recommendation,
    }
