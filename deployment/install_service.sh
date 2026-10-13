#!/usr/bin/env bash

set -euo pipefail

# wifi-notifier.service をテンプレートから生成し、systemd に登録する。
# Raspberry Pi 上（またはイメージビルド時）で実行する。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/wifi-notifier.service.template"
PROJECT_PATH="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_USER="$(id -un)"
SERVICE_GROUP="$(id -gn)"
# .venv/bin/python3 は 1 段リンクのため systemd でも解決できる（python は 2 段でNG）
PYTHON_BIN=""
CONFIG_FILE=""
FIREBASE_CREDENTIALS="${FIREBASE_CREDENTIALS_REMOTE:-}"
OUTPUT=""
INSTALL=1

usage() {
  cat <<'USAGE'
使用方法:
  ./deployment/install_service.sh [オプション]

オプション:
  --project-path <path>          プロジェクトのパス（デフォルト: このスクリプトの親ディレクトリ）
  --user <name>                  実行ユーザー（デフォルト: 現在のユーザー）
  --group <name>                 実行グループ（デフォルト: 現在のグループ）
  --python-bin <path>            Python実行ファイル（デフォルト: <project>/.venv/bin/python3）
  --config <path>                設定ファイル（デフォルト: <project>/config/config.yaml）
  --firebase-credentials <path>  Firebaseサービスアカウント JSON のパス
  --output <file>                指定先にサービスファイルを書き出すだけで、systemdへの登録は行わない
  -h, --help                     ヘルプを表示
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-path) PROJECT_PATH="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --group) SERVICE_GROUP="$2"; shift 2 ;;
    --python-bin) PYTHON_BIN="$2"; shift 2 ;;
    --config) CONFIG_FILE="$2"; shift 2 ;;
    --firebase-credentials) FIREBASE_CREDENTIALS="$2"; shift 2 ;;
    --output) OUTPUT="$2"; INSTALL=0; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "不明なオプションです: $1" >&2; usage; exit 1 ;;
  esac
done

PYTHON_BIN="${PYTHON_BIN:-${PROJECT_PATH}/.venv/bin/python3}"
CONFIG_FILE="${CONFIG_FILE:-${PROJECT_PATH}/config/config.yaml}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "エラー: 設定ファイルが見つかりません: ${CONFIG_FILE}" >&2
  exit 1
fi

# config.yaml から Environment 行を組み立ててテンプレートを置換し、標準出力へ書き出す
render() {
  python3 - "${TEMPLATE}" "${CONFIG_FILE}" "${SERVICE_USER}" "${SERVICE_GROUP}" \
    "${PROJECT_PATH}" "${PYTHON_BIN}" "${FIREBASE_CREDENTIALS}" <<'PY'
import sys
from pathlib import Path

import yaml

template, config, user, group, project, python_bin, firebase_credentials = sys.argv[1:]
cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8")) or {}


def section(name):
    value = cfg.get(name)
    return value if isinstance(value, dict) else {}


env_lines = []
gcal = section("google_calendar")
if gcal.get("credentials_file_env") and gcal.get("credentials_file"):
    env_lines.append(f"Environment={gcal['credentials_file_env']}={gcal['credentials_file']}")

firebase = section("firebase")
if firebase.get("enabled"):
    if not firebase.get("credentials_file_env"):
        sys.exit("エラー: firebase.enabled=true ですが credentials_file_env が未設定です")
    if not firebase_credentials:
        sys.exit("エラー: firebase.enabled=true ですが --firebase-credentials が未指定です")
    env_lines.append(f"Environment={firebase['credentials_file_env']}={firebase_credentials}")

text = Path(template).read_text(encoding="utf-8")
# Environment 行が無い場合は行ごと取り除く
env_block = "".join(f"{line}\n" for line in env_lines)
text = text.replace("@ENV_LINES@\n", env_block)
for key, value in {
    "@USER@": user,
    "@GROUP@": group,
    "@PROJECT_PATH@": project,
    "@PYTHON_BIN@": python_bin,
}.items():
    text = text.replace(key, value)
sys.stdout.write(text)
PY
}

rendered="$(render)"

if [[ ${INSTALL} -eq 0 ]]; then
  printf '%s\n' "${rendered}" > "${OUTPUT}"
  echo "サービスファイルを出力しました: ${OUTPUT}"
  exit 0
fi

# sudo で直接実行したことがある場合は root 所有になったログを修正
if [[ -f "${PROJECT_PATH}/wifi_notifier.log" ]]; then
  sudo chown "${SERVICE_USER}:${SERVICE_GROUP}" "${PROJECT_PATH}/wifi_notifier.log"
fi

printf '%s\n' "${rendered}" | sudo tee /etc/systemd/system/wifi-notifier.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable wifi-notifier
sudo systemctl restart wifi-notifier
sleep 4
sudo systemctl --no-pager --lines=20 status wifi-notifier
