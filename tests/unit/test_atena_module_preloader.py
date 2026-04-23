from __future__ import annotations

from pathlib import Path

from core.atena_module_preloader import preload_all_modules


def test_preload_all_modules_loads_valid_files(tmp_path: Path) -> None:
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    (modules_dir / "ok_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (modules_dir / "bad-mod.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    result = preload_all_modules(modules_dir)

    assert result["total"] == 2
    assert result["loaded_count"] == 1
    assert result["failed_count"] == 1
    assert "ok_mod.py" in result["loaded"]
