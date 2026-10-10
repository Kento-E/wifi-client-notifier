#!/usr/bin/env bash

set -euo pipefail

# ローカルの config.yaml とGoogleサービスアカウント鍵を Raspberry Pi へ配置し、
# wifi-notifier を再起動するスクリプト（ローカルPCから実行）
# 想定: raspberrypi-image で作成したイメージ（/home/pi/wifi-client-notifier）を書き込んだPi
#
# 環境変数で上書き可能:
#   PI_HOST            SSH接続先（デフォルト: raspberrypi）
#   LOCAL_CONFIG       配置する設定ファイル（デフォルト: リポジトリ直下の config.yaml）
#   LOCAL_CREDENTIALS  サービスアカウントJSON（デフォルト: ~/.google/wifi-notifier-*.json）
#   SKIP_RESTART=1     配置のみ行い、再起動しない

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PI_HOST="${PI_HOST:-raspberrypi}"
LOCAL_CONFIG="${LOCAL_CONFIG:-${ROOT_DIR}/config.yaml}"
if [[ -z "${LOCAL_CREDENTIALS:-}" ]]; then
  credentials_candidates=("${HOME}"/.google/wifi-notifier-*.json)
  if [[ ${#credentials_candidates[@]} -ne 1 || ! -f "${credentials_candidates[0]}" ]]; then
    echo "エラー: ~/.google/wifi-notifier-*.json が1つに定まりません。LOCAL_CREDENTIALS で指定してください" >&2
    exit 1
  fi
  LOCAL_CREDENTIALS="${credentials_candidates[0]}"
fi
SKIP_RESTART="${SKIP_RESTART:-0}"

# Pi側のパスはイメージ（raspberrypi-image の wifi-notifier.service）に合わせる
REMOTE_PROJECT="/home/pi/wifi-client-notifier"
REMOTE_CREDENTIALS="/home/pi/secrets/google-service-account.json"
REMOTE_STAGING=".deploy-staging"

for f in "${LOCAL_CONFIG}" "${LOCAL_CREDENTIALS}"; do
  if [[ ! -f "${f}" ]]; then
    echo "エラー: ファイルが見つかりません: ${f}" >&2
    exit 1
  fi
done

echo "=== Piへ設定と認証情報を配置 ==="
echo "接続先: ${PI_HOST}"
echo "設定ファイル: ${LOCAL_CONFIG}"
echo "認証情報: ${LOCAL_CREDENTIALS}"

echo "[1/3] ファイル転送"
ssh -o BatchMode=yes -o ConnectTimeout=8 "${PI_HOST}" "umask 077; rm -rf ${REMOTE_STAGING}; mkdir ${REMOTE_STAGING}"
scp -q "${LOCAL_CONFIG}" "${PI_HOST}:${REMOTE_STAGING}/config.yaml"
scp -q "${LOCAL_CREDENTIALS}" "${PI_HOST}:${REMOTE_STAGING}/google-service-account.json"

echo "[2/3] 検証して配置"
# 検証に失敗した場合は既存のファイルを変更しない
ssh -o BatchMode=yes "${PI_HOST}" bash -s -- "${REMOTE_PROJECT}" "${REMOTE_CREDENTIALS}" "${REMOTE_STAGING}" <<'EOF'
set -euo pipefail
remote_project="$1"
remote_credentials="$2"
staging="$HOME/$3"
trap 'rm -rf "${staging}"' EXIT

"${remote_project}/.venv/bin/python" -I - "${staging}/config.yaml" "${staging}/google-service-account.json" <<'PY'
import json
import sys

import yaml

config = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
for section, key in (("google_calendar", "calendar_id"), ("firebase", "project_id")):
    if config.get(section, {}).get("enabled") and not config[section].get(key):
        sys.exit(f"エラー: {section}.enabled が true ですが {section}.{key} が空です")

credentials = json.load(open(sys.argv[2], encoding="utf-8"))
if credentials.get("type") != "service_account" or not credentials.get("private_key"):
    sys.exit("エラー: 認証情報がサービスアカウントJSONではありません")
print(f"  設定OK / サービスアカウント: {credentials.get('client_email')}")
PY

if [[ -f "${remote_project}/config/config.yaml" ]]; then
  cp -p "${remote_project}/config/config.yaml" "${remote_project}/config/config.yaml.prev"
fi
install -m 600 "${staging}/config.yaml" "${remote_project}/config/config.yaml"
install -D -m 600 "${staging}/google-service-account.json" "${remote_credentials}"
echo "  配置完了（直前の設定は config/config.yaml.prev に保存）"
EOF

if [[ "${SKIP_RESTART}" == "1" ]]; then
  echo "[3/3] 再起動をスキップ（SKIP_RESTART=1）"
  exit 0
fi

echo "[3/3] wifi-notifier を再起動"
ssh -t "${PI_HOST}" '
set -e
since="$(date "+%Y-%m-%d %H:%M:%S")"
sudo systemctl restart wifi-notifier
sleep 6
echo "状態: $(systemctl is-active wifi-notifier)"
journalctl -u wifi-notifier --no-pager -o cat --since "${since}" \
  | grep -E "通知: |初期化|ERROR|WARNING" | grep -v -E "^\s*$" || true
'
