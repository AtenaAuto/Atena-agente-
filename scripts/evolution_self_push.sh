#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN="${ATENA_PUSH_DRY_RUN:-1}"
RUN_GATE="${ATENA_RUN_GO_NO_GO:-1}"

if [[ "$RUN_GATE" == "1" ]]; then
  echo "[ATENA] running evolution GO/NO-GO gate..."
  bash scripts/evolution_go_no_go.sh
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
REMOTE="${ATENA_PUSH_REMOTE:-origin}"

if [[ -n "$(git status --porcelain)" && "$DRY_RUN" != "1" ]]; then
  echo "[ATENA] working tree has uncommitted changes; aborting push"
  exit 2
fi

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "[ATENA] remote '$REMOTE' not configured; aborting push"
  exit 3
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[ATENA] DRY RUN enabled. Command to execute:"
  echo "git push $REMOTE $CURRENT_BRANCH"
  git push --dry-run "$REMOTE" "$CURRENT_BRANCH"
  echo "PUSH_STATUS=DRY_RUN_OK"
  exit 0
fi

echo "[ATENA] pushing branch '$CURRENT_BRANCH' to '$REMOTE'..."
git push "$REMOTE" "$CURRENT_BRANCH"
echo "PUSH_STATUS=OK"
