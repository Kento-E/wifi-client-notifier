#!/usr/bin/env bash

set -euo pipefail

# GUI経由のgit commitではPATHが最小化されることがあるため、
# PATH上のNodeが実行できない場合は既知のインストール先も確認する。
declare -a node_candidates=()
if command -v node >/dev/null 2>&1; then
  node_candidates+=("$(command -v node)")
fi
for candidate_dir in \
  "$HOME/.nodebrew/current/bin" \
  "/opt/homebrew/bin" \
  "/usr/local/bin"
do
  if [[ -x "$candidate_dir/node" ]]; then
    node_candidates+=("$candidate_dir/node")
  fi
done

node_bin=""
for candidate in "${node_candidates[@]}"; do
  node_major="$("$candidate" -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null)" || continue
  if [[ "$node_major" =~ ^[0-9]+$ ]] && [[ "$node_major" -ge 16 ]]; then
    node_bin="$candidate"
    break
  fi
done

if [[ -z "$node_bin" ]]; then
  echo "Node.js 16以上の実行可能なバイナリが見つかりません。Node.js をインストールし、PATHを確認してください。" >&2
  exit 1
fi
PATH="$(dirname "$node_bin"):$PATH"
export PATH

declare -a pre_commit_cmd=()

if command -v pre-commit >/dev/null 2>&1 && pre-commit --version >/dev/null 2>&1; then
  pre_commit_cmd=(pre-commit)
else
  declare -a python_candidates=()
  for python_command in python3 python; do
    if command -v "$python_command" >/dev/null 2>&1; then
      python_candidates+=("$(command -v "$python_command")")
    fi
  done
  for candidate in \
    "$PWD/.venv/bin/python" \
    "$HOME"/.pyenv/versions/*/bin/python
  do
    [[ -x "$candidate" ]] && python_candidates+=("$candidate")
  done

  for python_bin in "${python_candidates[@]}"; do
    if "$python_bin" -m pre_commit --version >/dev/null 2>&1; then
      pre_commit_cmd=("$python_bin" -m pre_commit)
      break
    fi
  done

  if [[ ${#pre_commit_cmd[@]} -eq 0 ]]; then
    echo "pre-commit の実行環境が見つかりません。" >&2
    echo "推奨: pip install -r requirements.txt を実行して pre-commit を再セットアップしてください。" >&2
    exit 1
  fi
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
