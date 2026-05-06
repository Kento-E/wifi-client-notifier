#!/usr/bin/env bash

set -euo pipefail

# GUI経由のgit commitではPATHが最小化されることがあるため、
# pre-commitのNode系フックが同一世代のnode/npmを参照できるよう補正する。
for candidate_dir in \
  "$HOME/.nodebrew/current/bin" \
  "/opt/homebrew/bin" \
  "/usr/local/bin"
do
  if [[ -d "$candidate_dir" ]]; then
    case ":$PATH:" in
      *":$candidate_dir:"*) ;;
      *) PATH="$candidate_dir:$PATH" ;;
    esac
  fi
done

if ! command -v node >/dev/null 2>&1; then
  echo "node が見つかりません。Node.js をインストールし、PATHを確認してください。" >&2
  exit 1
fi

node_major="$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)"
if [[ "$node_major" -lt 16 ]]; then
  echo "node のバージョンが古すぎます（検出: $(node -v 2>/dev/null || echo unknown)）。16以上を使用してください。" >&2
  exit 1
fi

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
