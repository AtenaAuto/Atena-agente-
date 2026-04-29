from pathlib import Path

from core.production_programming_probe import run_programming_probe


ROOT = Path(__file__).resolve().parents[2]


def test_run_programming_probe():
    payload = run_programming_probe(ROOT, prefix="unit_probe", site_template="dashboard")
    assert payload["status"] in {"ok", "warn"}
    assert payload["total"] >= 3
    assert payload["passed"] <= payload["total"]
    assert set(payload["generated_projects"].keys()) == {"site", "api", "cli"}
