#!/usr/bin/env bash

set -euo pipefail

# Raspberry Pi 内で config/config.yaml の変更を反映するためのスクリプト
# 想定: 既に ~/work/wifi-client-notifier に配置済み、.venv 作成済み

PROJECT_DIR="${PROJECT_DIR:-$HOME/work/wifi-client-notifier}"
CONFIG_PATH="config/config.yaml"
FIREBASE_CREDENTIALS_REMOTE="${FIREBASE_CREDENTIALS_REMOTE:-}"
GCAL_CREDENTIALS_REMOTE="${GCAL_CREDENTIALS_REMOTE:-}"
SKIP_TEST=0
DAEMON_RELOAD=0

usage() {
  cat <<'USAGE'
使用方法:
  ./deployment/apply_config_on_pi.sh [オプション]

オプション:
  --project-dir <path>            プロジェクトディレクトリ
                                  （デフォルト: ~/work/wifi-client-notifier）
  --config <path>                 プロジェクト配下の設定ファイル相対パス
                                  （デフォルト: config/config.yaml）
  --firebase-credentials <path>   Pi上の Firebase サービスアカウントJSONパス
  --gcal-credentials <path>       Pi上の Google Calendar サービスアカウントJSONパス
  --skip-test                     test_config.py の実行をスキップ
  --daemon-reload                 systemctl daemon-reload を実行してから再起動
  -h, --help                      ヘルプを表示

例:
  ./deployment/apply_config_on_pi.sh \
    --firebase-credentials /home/pi/secrets/firebase-service-account.json \
    --gcal-credentials /home/pi/secrets/google-service-account.json
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --firebase-credentials)
      FIREBASE_CREDENTIALS_REMOTE="$2"
      shift 2
      ;;
    --gcal-credentials)
      GCAL_CREDENTIALS_REMOTE="$2"
      shift 2
      ;;
    --skip-test)
      SKIP_TEST=1
      shift
      ;;
    --daemon-reload)
      DAEMON_RELOAD=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "不明なオプションです: $1" >&2
      usage
      exit 1
      ;;
  esac
done

cd "${PROJECT_DIR}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "エラー: 設定ファイルが見つかりません: ${PROJECT_DIR}/${CONFIG_PATH}" >&2
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "エラー: .venv/bin/python が見つかりません。先にセットアップを実行してください。" >&2
  exit 1
fi

echo "=== config反映開始（Piローカル） ==="
echo "プロジェクト: ${PROJECT_DIR}"
echo "設定ファイル: ${CONFIG_PATH}"

get_config_value() {
  .venv/bin/python - "$1" "$2" "$CONFIG_PATH" <<'PY'
import sys
import yaml
from pathlib import Path

section = sys.argv[1]
key = sys.argv[2]
config_path = Path(sys.argv[3])
cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
value = cfg.get(section, {})
if not isinstance(value, dict):
    value = {}
value = value.get(key, "")
if isinstance(value, bool):
    print("1" if value else "")
elif value is None:
    print("")
else:
    print(str(value).strip())
PY
}

gcal_env_name="$(get_config_value google_calendar credentials_file_env)"
gcal_enabled="$(get_config_value google_calendar enabled)"
firebase_enabled="$(get_config_value firebase enabled)"
firebase_env_name="$(get_config_value firebase credentials_file_env)"

env_args=()

if [[ -n "${gcal_enabled}" && -n "${gcal_env_name}" ]]; then
  if [[ -z "${GCAL_CREDENTIALS_REMOTE}" ]]; then
    # config内の後方互換キー（credentials_file）を読み取り、未指定時の補助として使う
    gcal_from_config="$(get_config_value google_calendar credentials_file)"
    if [[ -n "${gcal_from_config}" ]]; then
      GCAL_CREDENTIALS_REMOTE="${gcal_from_config}"
    fi
  fi
  if [[ -z "${GCAL_CREDENTIALS_REMOTE}" ]]; then
    echo "エラー: google_calendar.enabled=true ですが認証JSONパスが未指定です" >&2
    echo "  --gcal-credentials を指定するか、環境変数 GCAL_CREDENTIALS_REMOTE を設定してください" >&2
    exit 1
  fi
  env_args+=("${gcal_env_name}=${GCAL_CREDENTIALS_REMOTE}")
fi

if [[ -n "${firebase_enabled}" ]]; then
  if [[ -z "${firebase_env_name}" ]]; then
    echo "エラー: firebase.enabled=true ですが credentials_file_env が未設定です" >&2
    exit 1
  fi
  if [[ -z "${FIREBASE_CREDENTIALS_REMOTE}" ]]; then
    echo "エラー: firebase.enabled=true ですが認証JSONパスが未指定です" >&2
    echo "  --firebase-credentials を指定するか、環境変数 FIREBASE_CREDENTIALS_REMOTE を設定してください" >&2
    exit 1
  fi
  env_args+=("${firebase_env_name}=${FIREBASE_CREDENTIALS_REMOTE}")
fi

if [[ ${SKIP_TEST} -eq 0 ]]; then
  echo "[1/3] 設定テストを実行"
  printf "n\n" | sudo env "${env_args[@]}" .venv/bin/python src/test_config.py "${CONFIG_PATH}"
else
  echo "[1/3] 設定テストをスキップ"
fi

if [[ ${DAEMON_RELOAD} -eq 1 ]]; then
  echo "[2/3] systemd定義を再読み込み"
  sudo systemctl daemon-reload
else
  echo "[2/3] systemd定義の再読み込みをスキップ"
fi

echo "[3/3] サービス再起動と状態確認"
sudo systemctl restart wifi-notifier
sudo systemctl --no-pager --lines=20 status wifi-notifier

echo ""
echo "直近ログ（50行）"
sudo journalctl -u wifi-notifier -n 50 --no-pager

echo ""
echo "=== config反映完了 ==="
