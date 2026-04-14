#!/usr/bin/env bash

set -euo pipefail

# Raspberry Pi 自動セットアップスクリプト
# ローカルPCから実行し、SSH経由で Raspberry Pi のセットアップを行う。

PI_HOST="${PI_HOST:-}"
WORK_DIR="~/work"
REPO_URL="https://github.com/Kento-E/wifi-client-notifier.git"
LOCAL_CONFIG="config/config.yaml"
COPY_CONFIG=1
RUN_TEST=1
RUN_SINGLE=1

if command -v git >/dev/null 2>&1; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ -z "${BRANCH}" ]]; then
    BRANCH="main"
  fi
else
  BRANCH="main"
fi

usage() {
  cat <<'USAGE'
使用方法:
  ./deployment/setup_raspberrypi.sh [オプション]

オプション:
  --host <user@host>       SSH接続先（環境変数 PI_HOST より優先）
  --branch <branch>        チェックアウトするブランチ（デフォルト: 現在のローカルブランチ）
  --repo <url>             クローンするリポジトリURL
  --workdir <path>         Raspberry Pi側の作業ディレクトリ（デフォルト: ~/work）
  --config <path>          ローカル設定ファイルのパス（デフォルト: config/config.yaml）
  --no-config-copy         設定ファイル転送をスキップ
  --skip-test              test_config.py の実行をスキップ
  --skip-single-run        wifi_notifier.py --single-run の実行をスキップ
  -h, --help               ヘルプを表示

例:
  PI_HOST=user@hostname.local ./deployment/setup_raspberrypi.sh
  ./deployment/setup_raspberrypi.sh --host pi@192.168.10.50 --branch main
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      PI_HOST="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --workdir)
      WORK_DIR="$2"
      shift 2
      ;;
    --config)
      LOCAL_CONFIG="$2"
      shift 2
      ;;
    --no-config-copy)
      COPY_CONFIG=0
      shift
      ;;
    --skip-test)
      RUN_TEST=0
      shift
      ;;
    --skip-single-run)
      RUN_SINGLE=0
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

if [[ -z "${PI_HOST}" ]]; then
  echo "エラー: SSH接続先が未指定です。--host または環境変数 PI_HOST を指定してください。" >&2
  echo "例: PI_HOST=user@hostname.local ./deployment/setup_raspberrypi.sh" >&2
  exit 1
fi

REMOTE_PROJECT="${WORK_DIR}/wifi-client-notifier"

echo "=== Raspberry Pi セットアップ開始 ==="
echo "接続先: ${PI_HOST}"
echo "ブランチ: ${BRANCH}"
echo "作業ディレクトリ: ${WORK_DIR}"

echo "[1/5] SSH接続確認"
ssh -o BatchMode=yes -o ConnectTimeout=8 "${PI_HOST}" "echo 'SSH接続OK'"

echo "[2/5] 必要パッケージ導入・リポジトリ準備・Python環境構築"
ssh "${PI_HOST}" "bash -lc '
set -e
mkdir -p ${WORK_DIR}
sudo apt-get update
sudo apt-get install -y git python3-venv
cd ${WORK_DIR}
if [ -d wifi-client-notifier/.git ]; then
  cd wifi-client-notifier
  git fetch origin
  git checkout ${BRANCH}
  git pull --ff-only origin ${BRANCH}
else
  git clone --branch ${BRANCH} ${REPO_URL}
  cd wifi-client-notifier
fi
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
'"

if [[ ${COPY_CONFIG} -eq 1 ]]; then
  if [[ ! -f "${LOCAL_CONFIG}" ]]; then
    echo "設定ファイルが見つかりません: ${LOCAL_CONFIG}" >&2
    exit 1
  fi

  echo "[3/5] 設定ファイル転送"
  cat "${LOCAL_CONFIG}" | ssh "${PI_HOST}" "cat > ${REMOTE_PROJECT}/config/config.yaml"

  echo "[4/5] Raspberry Pi向け ARP 設定を補完"
  ssh "${PI_HOST}" "bash -lc '
set -e
cd ${REMOTE_PROJECT}
. .venv/bin/activate
python - <<\"PY\"
import yaml
from pathlib import Path

p = Path(\"config/config.yaml\")
cfg = yaml.safe_load(p.read_text(encoding=\"utf-8\"))
cfg[\"detection_method\"] = \"arp\"
cfg.setdefault(\"arp\", {})
cfg[\"arp\"].setdefault(\"interface\", \"wlan0\")
cfg[\"arp\"].setdefault(\"timeout\", 2)
p.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding=\"utf-8\")
print(\"設定更新完了\")
PY
'"
else
  echo "[3/5] 設定ファイル転送をスキップ"
fi

if [[ ${RUN_TEST} -eq 1 ]]; then
  echo "[5/5] 設定テスト実行"
  ssh "${PI_HOST}" "bash -lc '
set -e
cd ${REMOTE_PROJECT}
printf \"n\\n\" | sudo .venv/bin/python src/test_config.py config/config.yaml
'"
else
  echo "[5/5] 設定テストをスキップ"
fi

if [[ ${RUN_SINGLE} -eq 1 ]]; then
  echo "[追加確認] single-run 実行"
  ssh "${PI_HOST}" "bash -lc '
set -e
cd ${REMOTE_PROJECT}
sudo .venv/bin/python src/wifi_notifier.py config/config.yaml --single-run
'"
fi

echo ""
echo "=== セットアップ完了 ==="
echo "常時実行する場合:"
echo "  ssh ${PI_HOST}"
echo "  cd ${REMOTE_PROJECT}"
echo "  sudo .venv/bin/python src/wifi_notifier.py config/config.yaml"
