#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def discover_python_files(repo_dir: Path, max_files: int) -> list[Path]:
    files = [p for p in repo_dir.rglob("*.py") if ".git" not in p.parts]
    files.sort()
    return files[:max_files]


def main() -> int:
    parser = argparse.ArgumentParser(description="Clona repositórios externos e roda smoke test básico de sintaxe.")
    parser.add_argument("--discovery-json", required=True, help="Arquivo EXTERNAL_CODE_DISCOVERY_*.json")
    parser.add_argument("--max-repos", type=int, default=3, help="Quantidade máxima de repositórios para validar")
    parser.add_argument("--max-py-files", type=int, default=20, help="Quantidade máxima de .py para py_compile por repo")
    args = parser.parse_args()

    discovery_path = Path(args.discovery_json)
    payload = json.loads(discovery_path.read_text(encoding="utf-8"))
    repos = list(payload.get("repos", []))[: max(1, args.max_repos)]

    workspace = ROOT / "atena_evolution" / "external_repos"
    workspace.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    report_dir = ROOT / "analysis_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"EXTERNAL_CODE_SMOKE_{ts}.json"

    results: list[dict[str, object]] = []
    for repo in repos:
        name = str(repo.get("name", "unknown")).replace("/", "__")
        clone_url = str(repo.get("clone_url") or "")
        target = workspace / name
        if target.exists():
            rc, out, err = run(["git", "-C", str(target), "pull", "--ff-only"], timeout=120)
            clone_step = {"action": "pull", "returncode": rc, "stdout_tail": out[-800:], "stderr_tail": err[-800:]}
        else:
            rc, out, err = run(["git", "clone", "--depth", "1", clone_url, str(target)], timeout=240)
            clone_step = {"action": "clone", "returncode": rc, "stdout_tail": out[-800:], "stderr_tail": err[-800:]}

        item: dict[str, object] = {
            "repo": repo.get("name"),
            "url": repo.get("url"),
            "clone_url": clone_url,
            "workspace": str(target),
            "clone_step": clone_step,
            "status": "failed",
        }

        if clone_step["returncode"] != 0:
            results.append(item)
            continue

        py_files = discover_python_files(target, args.max_py_files)
        compile_results: list[dict[str, object]] = []
        compile_ok = True
        for pyf in py_files:
            rc2, out2, err2 = run(["python3", "-m", "py_compile", str(pyf)], timeout=120)
            compile_results.append(
                {
                    "file": str(pyf.relative_to(target)),
                    "returncode": rc2,
                    "stderr_tail": err2[-500:],
                }
            )
            if rc2 != 0:
                compile_ok = False

        item["python_files_checked"] = len(py_files)
        item["compile_results"] = compile_results
        item["status"] = "ok" if compile_ok else "warn"
        results.append(item)

    final_status = "ok" if results and all(r.get("status") == "ok" for r in results) else "warn"
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_discovery": str(discovery_path),
        "max_repos": args.max_repos,
        "max_py_files": args.max_py_files,
        "status": final_status,
        "results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"External code smoke report: {report_path}")
    print(f"status={final_status} repos={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
