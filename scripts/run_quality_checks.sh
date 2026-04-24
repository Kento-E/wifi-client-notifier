#!/usr/bin/env bash

set -euo pipefail

if ! command -v pre-commit >/dev/null 2>&1; then
  echo "pre-commit が見つかりません。README の開発者向けセットアップを実行してください。" >&2
  exit 1
fi

if [[ "${1:-}" == "--hook" ]]; then
  pre-commit run --hook-stage pre-commit --show-diff-on-failure
  exit 0
fi

if [[ $# -eq 2 ]]; then
  pre-commit run \
    --from-ref "$1" \
    --to-ref "$2" \
    --show-diff-on-failure
  exit 0
fi

pre-commit run --all-files --show-diff-on-failure