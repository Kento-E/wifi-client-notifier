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
      *) PATH="$PATH:$candidate_dir" ;;
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

declare -a pre_commit_cmd=()

if command -v pre-commit >/dev/null 2>&1 && pre-commit --version >/dev/null 2>&1; then
  pre_commit_cmd=(pre-commit)
elif command -v python3 >/dev/null 2>&1 && python3 -m pre_commit --version >/dev/null 2>&1; then
  # 壊れたグローバルpre-commitを避け、Python環境のpre_commitモジュールを利用する。
  pre_commit_cmd=(python3 -m pre_commit)
elif command -v python >/dev/null 2>&1 && python -m pre_commit --version >/dev/null 2>&1; then
  pre_commit_cmd=(python -m pre_commit)
else
  echo "pre-commit の実行環境が見つかりません。" >&2
  echo "推奨: pip install -r requirements.txt を実行して pre-commit を再セットアップしてください。" >&2
  echo "Homebrew版が壊れている場合は brew reinstall python@3.14 pre-commit で復旧できます。" >&2
  exit 1
fi

if [[ "${1:-}" == "--hook" ]]; then
  "${pre_commit_cmd[@]}" run --hook-stage pre-commit --show-diff-on-failure
  exit 0
fi

if [[ $# -eq 2 ]]; then
  "${pre_commit_cmd[@]}" run \
    --from-ref "$1" \
    --to-ref "$2" \
    --show-diff-on-failure
  exit 0
fi

"${pre_commit_cmd[@]}" run --all-files --show-diff-on-failure
