#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
export ALLOW_DEEP_SELF_MOD=true
export SELF_MOD_INTERVAL=1
python3 core/main.py "$@"
