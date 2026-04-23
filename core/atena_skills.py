#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Skills: descoberta e validação das skills locais e referência Claude."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SkillResult:
    skill_file: str
    scripts_checked: int
    ok: bool
    errors: list[str]


def find_skill_files() -> list[Path]:
    patterns = [
        ROOT / "skills",
        ROOT / "evolution" / "reference_dna" / "claude_code" / "plugins",
    ]
    found: list[Path] = []
    for base in patterns:
        if not base.exists():
            continue
        found.extend(base.rglob("SKILL.md"))
    return sorted(set(found))


def validate_script(path: Path) -> tuple[bool, str]:
    if path.suffix == ".py":
        cmd = [sys.executable, "-m", "py_compile", str(path)]
    elif path.suffix == ".sh":
        cmd = ["bash", "-n", str(path)]
    else:
        return True, ""
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode == 0:
        return True, ""
    return False, (proc.stderr or proc.stdout).strip()[:300]


def validate_skill(skill_file: Path) -> SkillResult:
    skill_dir = skill_file.parent
    scripts = []
    script_dir = skill_dir / "scripts"
    if script_dir.exists():
        scripts.extend([p for p in script_dir.iterdir() if p.is_file() and p.suffix in {".py", ".sh"}])

    errors: list[str] = []
    for script in scripts:
        ok, err = validate_script(script)
        if not ok:
            errors.append(f"{script.relative_to(ROOT)} :: {err}")

    return SkillResult(
        skill_file=str(skill_file.relative_to(ROOT)),
        scripts_checked=len(scripts),
        ok=len(errors) == 0,
        errors=errors,
    )


def main() -> int:
    skills = find_skill_files()
    if not skills:
        print("⚠️ Nenhuma skill encontrada.")
        return 1

    results = [validate_skill(s) for s in skills]
    ok_count = sum(1 for r in results if r.ok)
    print(f"🧩 Skills descobertas: {len(results)} | válidas: {ok_count} | com erro: {len(results)-ok_count}")
    for r in results:
        icon = "✅" if r.ok else "❌"
        print(f"{icon} {r.skill_file} (scripts verificados: {r.scripts_checked})")
        for err in r.errors:
            print(f"   - {err}")

    out = ROOT / "atena_evolution" / "skills_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
