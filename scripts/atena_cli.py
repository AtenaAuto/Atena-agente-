from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    launcher = Path(__file__).resolve().parents[1] / "atena"
    return subprocess.call(["bash", str(launcher), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
