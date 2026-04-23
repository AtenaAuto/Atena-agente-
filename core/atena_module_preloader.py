#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pré-carregador de módulos da ATENA para prontidão imediata."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


def _safe_module_name(path: Path) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", path.stem)
    return f"atena_preload_{slug}"


def preload_all_modules(modules_dir: Path) -> dict[str, object]:
    loaded: list[str] = []
    failed: list[dict[str, str]] = []
    if not modules_dir.exists():
        return {"loaded": loaded, "failed": failed, "total": 0}

    candidates = sorted(p for p in modules_dir.glob("*.py") if p.name != "__init__.py")
    for path in candidates:
        module_name = _safe_module_name(path)
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError("spec inválida")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            loaded.append(path.name)
        except Exception as exc:  # noqa: BLE001
            failed.append({"module": path.name, "error": str(exc)[:200]})

    return {
        "loaded": loaded,
        "failed": failed,
        "total": len(candidates),
        "loaded_count": len(loaded),
        "failed_count": len(failed),
    }
