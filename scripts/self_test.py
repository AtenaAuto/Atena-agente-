from __future__ import annotations

import sys

from core.atena_self_test import main as self_test_main


def main() -> int:
    return self_test_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
