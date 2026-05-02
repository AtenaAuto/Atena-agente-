#!/usr/bin/env bash
set -euo pipefail

echo "[ATENA] Repo Connectivity Audit"

python3 - <<'PY'
import py_compile
from pathlib import Path

root = Path('.')
py_files = [p for p in root.rglob('*.py') if '.venv' not in p.parts and '__pycache__' not in p.parts]
errors=[]
for p in py_files:
    try:
        py_compile.compile(str(p), doraise=True)
    except Exception as e:
        errors.append((str(p), str(e)))
if errors:
    print('SYNTAX_STATUS=FAIL')
    for f,e in errors[:20]:
        print(f' - {f}: {e}')
    raise SystemExit(2)
print(f'SYNTAX_STATUS=OK files={len(py_files)}')
PY

python3 - <<'PY'
from pathlib import Path
from core.atena_module_preloader import AtenaModulePreloader, SKIP_PRELOAD_MODULES

modules_dir = Path('modules')
preloader = AtenaModulePreloader(modules_dir)
preloader.max_workers = 1
preloader.recursive_preload = False
result = preloader.preload_all(recursive=False, analyze_first=False)

all_mods = {p.name for p in modules_dir.glob('*.py') if p.name != '__init__.py'}
expected = sorted(m for m in all_mods if m not in SKIP_PRELOAD_MODULES)
loaded = set(result.get('loaded', []))
missing = [m for m in expected if m not in loaded]

print(f"PRELOAD loaded={result.get('loaded_count')} total={result.get('total')} failed={result.get('failed_count')}")
if missing:
    print('PRELOAD_STATUS=PARTIAL')
    print('MISSING_FROM_PRELOAD=' + ','.join(missing[:30]))
    raise SystemExit(3)
print('PRELOAD_STATUS=OK')
PY

echo "REPO_CONNECTIVITY_STATUS=OK"
