from __future__ import annotations

import sys

from core.atena_terminal_assistant import main as assistant_main


def main() -> int:
    return int(assistant_main())


if __name__ == "__main__":
    raise SystemExit(main())
