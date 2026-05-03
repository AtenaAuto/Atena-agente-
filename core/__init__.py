"""
🔱 ATENA Ω — Core Package
Sistema de IA Autônomo com Auto-Evolução v4.0
"""

from __future__ import annotations

__version__      = "4.0.0"
__author__       = "ATENA Auto Team & Danilo"
__email__        = "core@atena.ai"
__license__      = "MIT"
__description__  = "Sistema de IA Autônomo com Auto-Evolução"

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy public API — imports só acontecem quando o atributo é acessado,
# evitando importar torch/transformers no cold-start do launcher.
# ---------------------------------------------------------------------------

_LAZY: dict[str, str] = {
    "AtenaCore":       "core.main",
    "AtenaApp":        "core.main",
    "Config":          "core.main",
    "Problem":         "core.main",
    "KnowledgeBase":   "core.main",
    "Sandbox":         "core.main",
    "GrokGenerator":   "core.main",
    "MutationEngine":  "core.main",
    "CodeEvaluator":   "core.main",
    "AutoDeploy":      "core.main",
    # Launcher / terminal
    "AtenaLauncher":   "core.atena_launcher",
    # Doctor / diagnostics
    "AtenaDoctor":     "core.atena_doctor",
}

def __getattr__(name: str):
    if name in _LAZY:
        import importlib
        module = importlib.import_module(_LAZY[name])
        obj = getattr(module, name)
        globals()[name] = obj          # cache so next access is free
        return obj
    raise AttributeError(f"module 'core' has no attribute '{name}'")

def __dir__():
    return sorted(list(_LAZY.keys()) + [
        "__version__", "__author__", "__license__",
        "__description__", "__email__",
    ])

__all__ = list(_LAZY.keys())

