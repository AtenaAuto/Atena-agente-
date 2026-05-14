import json
import subprocess
import sys
from pathlib import Path

from modules.atena_code_module import AtenaCodeModule


ROOT = Path(__file__).resolve().parents[2]


def test_build_microservice_project_self_test():
    result = AtenaCodeModule(ROOT).build("microservice", "unit_microservice_delivery")

    try:
        assert result.ok is True
        main_py = Path(result.output_dir) / "main.py"
        assert main_py.exists()

        proc = subprocess.run(
            [sys.executable, str(main_py), "--self-test"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        assert payload["passed"] is True
        assert payload["health"]["status"] == "ok"
        assert payload["metrics"]["jobs_total"] == 1
    finally:
        subprocess.run(["rm", "-rf", result.output_dir], check=False)


def test_build_library_project_demo():
    result = AtenaCodeModule(ROOT).build("library", "unit_library_delivery")

    try:
        assert result.ok is True
        main_py = Path(result.output_dir) / "main.py"
        package_dir = Path(result.output_dir) / "unit_library_delivery"
        assert main_py.exists()
        assert (package_dir / "__init__.py").exists()

        proc = subprocess.run(
            [sys.executable, str(main_py)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        assert payload == {"average_ratio": 1.0, "count": 3, "perfect": 3}
    finally:
        subprocess.run(["rm", "-rf", result.output_dir], check=False)
