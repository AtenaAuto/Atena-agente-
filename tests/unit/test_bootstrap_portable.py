import subprocess


def test_bootstrap_portable_dry_run() -> None:
    result = subprocess.run(
        [
            'python3',
            'setup/bootstrap_portable.py',
            '--with-dev',
            '--with-playwright',
            '--doctor',
            '--dry-run',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert 'chmod +x' in result.stdout
    assert 'requirements-pinned.txt' in result.stdout
    assert 'requirements-dev.txt' in result.stdout
    assert 'playwright install chromium' in result.stdout
    assert 'atena doctor' in result.stdout


def test_bootstrap_portable_full_auto_dry_run() -> None:
    result = subprocess.run(
        ['python3', 'setup/bootstrap_portable.py', '--full-auto', '--dry-run'],
        check=True,
        capture_output=True,
        text=True,
    )
    assert 'requirements-dev.txt' in result.stdout
    assert 'playwright install chromium' in result.stdout
    assert 'atena doctor' in result.stdout
