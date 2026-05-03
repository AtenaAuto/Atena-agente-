import shutil
import subprocess
from pathlib import Path


def test_create_saas_stub_generates_project() -> None:
    target = Path('generated/saas_starter')
    if target.exists():
        shutil.rmtree(target)

    subprocess.run(['python3', 'examples/create_saas_stub.py'], check=True)

    assert (target / 'app.py').exists()
    assert (target / 'README.md').exists()
    assert 'FastAPI' in (target / 'app.py').read_text()
