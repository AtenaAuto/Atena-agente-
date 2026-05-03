import subprocess
from pathlib import Path


def test_atena_perfeita_script_output() -> None:
    script = Path('examples/atena_perfeita.py')
    result = subprocess.run(
        ['python3', str(script)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert 'Atena perfeita: criando algo no terminal com sucesso!' in result.stdout
