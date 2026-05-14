from pathlib import Path

from core.production_programming_probe import run_programming_probe


ROOT = Path(__file__).resolve().parents[2]


def test_run_programming_probe():
    payload = run_programming_probe(ROOT, prefix="unit_probe", site_template="dashboard")
    assert payload["status"] in {"ok", "warn"}
    assert payload["total"] >= 3
    assert payload["passed"] <= payload["total"]
    assert set(payload["generated_projects"].keys()) == {"site", "api", "cli"}


def test_run_programming_probe_full_suite():
    payload = run_programming_probe(ROOT, prefix="unit_full_probe", site_template="dashboard", validate_all=True)
    assert payload["status"] == "ok"
    assert payload["score"] == 1.0
    assert payload["passed"] == payload["total"]
    assert set(payload["generated_projects"].keys()) == {"site", "api", "cli", "microservice", "library"}
    assert payload["generated_projects"]["microservice"]["compile_ok"] is True
    assert payload["generated_projects"]["library"]["compile_ok"] is True
