#!/usr/bin/env bash

set -euo pipefail

# Raspberry Pi 自動セットアップスクリプト
# ローカルPCから実行し、SSH経由で Raspberry Pi のセットアップを行う。

PI_HOST="${PI_HOST:-}"
WORK_DIR="~/work"
REPO_URL="https://github.com/Kento-E/wifi-client-notifier.git"
LOCAL_CONFIG="config/config.yaml"
FIREBASE_CREDENTIALS_REMOTE="${FIREBASE_CREDENTIALS_REMOTE:-}"
COPY_CONFIG=1
RUN_TEST=1
RUN_SINGLE=1
INSTALL_SERVICE=1

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
  --firebase-credentials <path>
                           Raspberry Pi上のFirebaseサービスアカウントJSONパス
  --no-config-copy         設定ファイル転送をスキップ
  --skip-test              test_config.py の実行をスキップ
  --skip-single-run        wifi_notifier.py --single-run の実行をスキップ
  --skip-service-install   systemdサービスのインストールをスキップ
  -h, --help               ヘルプを表示

例:
  PI_HOST=user@hostname.local ./deployment/setup_raspberrypi.sh
  ./deployment/setup_raspberrypi.sh --host pi@192.168.10.50 --branch main \
    --firebase-credentials /home/pi/secrets/firebase-service-account.json
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
    --firebase-credentials)
      FIREBASE_CREDENTIALS_REMOTE="$2"
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
    --skip-service-install)
      INSTALL_SERVICE=0
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
if [[ -n "${FIREBASE_CREDENTIALS_REMOTE}" ]]; then
  echo "Firebase認証情報: ${FIREBASE_CREDENTIALS_REMOTE}"
fi
if [[ ${INSTALL_SERVICE} -eq 1 ]]; then
  echo "systemdサービス: インストールする"
else
  echo "systemdサービス: インストールしない"
fi

echo "[1/6] SSH接続確認"
ssh -o BatchMode=yes -o ConnectTimeout=8 "${PI_HOST}" "echo 'SSH接続OK'"

echo "[2/6] 必要パッケージ導入・リポジトリ準備・Python環境構築"
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

  echo "[3/6] 設定ファイル転送"
  cat "${LOCAL_CONFIG}" | ssh "${PI_HOST}" "cat > ${REMOTE_PROJECT}/config/config.yaml"

  echo "[4/6] Raspberry Pi向け ARP 設定を補完"
  ssh "${PI_HOST}" bash -s -- "${REMOTE_PROJECT}" <<'EOF'
set -e
remote_project="$1"
cd "$remote_project"
. .venv/bin/activate
python - <<"PY"
import yaml
from pathlib import Path

p = Path("config/config.yaml")
cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
cfg["detection_method"] = "arp"
cfg.setdefault("arp", {})
cfg["arp"].setdefault("interface", "wlan0")
cfg["arp"].setdefault("timeout", 2)
cfg.setdefault("disconnect_grace_scans", 3)
if "notification_cool_down_minutes" not in cfg and "notification_cooldown_minutes" in cfg:
    cfg["notification_cool_down_minutes"] = cfg["notification_cooldown_minutes"]
cfg.setdefault("notification_cool_down_minutes", 1440)
cfg.setdefault("reconnect_notify_after_minutes", 60)
p.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("設定更新完了")
PY
EOF
else
  echo "[3/6] 設定ファイル転送をスキップ"
  echo "[4/6] Raspberry Pi向け ARP 設定補完をスキップ"
fi

if [[ ${RUN_TEST} -eq 1 ]]; then
  echo "[5/6] 設定テスト実行"
  ssh "${PI_HOST}" bash -s -- "${REMOTE_PROJECT}" "${FIREBASE_CREDENTIALS_REMOTE}" <<'EOF'
set -e
remote_project="$1"
firebase_credentials_remote="$2"
cd "$remote_project"

get_config_value() {
  python3 - "$1" "$2" <<'PY'
import sys
import yaml
from pathlib import Path

section = sys.argv[1]
key = sys.argv[2]
cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8")) or {}
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
gcal_env_value="$(get_config_value google_calendar credentials_file)"
firebase_enabled="$(get_config_value firebase enabled)"
firebase_env_name="$(get_config_value firebase credentials_file_env)"

env_args=()
if [[ -n "${gcal_env_name}" && -n "${gcal_env_value}" ]]; then
  env_args+=("${gcal_env_name}=${gcal_env_value}")
fi
if [[ -n "${firebase_enabled}" ]]; then
  if [[ -z "${firebase_env_name}" ]]; then
    echo "エラー: firebase.enabled=true ですが credentials_file_env が未設定です" >&2
    exit 1
  fi
  if [[ -z "${firebase_credentials_remote}" ]]; then
    echo "エラー: firebase.enabled=true ですが --firebase-credentials が未指定です" >&2
    exit 1
  fi
  env_args+=("${firebase_env_name}=${firebase_credentials_remote}")
fi

printf "n\n" | sudo env "${env_args[@]}" .venv/bin/python src/test_config.py config/config.yaml
EOF
else
  echo "[5/6] 設定テストをスキップ"
fi

if [[ ${RUN_SINGLE} -eq 1 ]]; then
  echo "[追加確認] single-run 実行"
  ssh "${PI_HOST}" bash -s -- "${REMOTE_PROJECT}" "${FIREBASE_CREDENTIALS_REMOTE}" <<'EOF'
set -e
remote_project="$1"
firebase_credentials_remote="$2"
cd "$remote_project"

get_config_value() {
  python3 - "$1" "$2" <<'PY'
import sys
import yaml
from pathlib import Path

section = sys.argv[1]
key = sys.argv[2]
cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8")) or {}
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
gcal_env_value="$(get_config_value google_calendar credentials_file)"
firebase_enabled="$(get_config_value firebase enabled)"
firebase_env_name="$(get_config_value firebase credentials_file_env)"

env_args=()
if [[ -n "${gcal_env_name}" && -n "${gcal_env_value}" ]]; then
  env_args+=("${gcal_env_name}=${gcal_env_value}")
fi
if [[ -n "${firebase_enabled}" ]]; then
  if [[ -z "${firebase_env_name}" ]]; then
    echo "エラー: firebase.enabled=true ですが credentials_file_env が未設定です" >&2
    exit 1
  fi
  if [[ -z "${firebase_credentials_remote}" ]]; then
    echo "エラー: firebase.enabled=true ですが --firebase-credentials が未指定です" >&2
    exit 1
  fi
  env_args+=("${firebase_env_name}=${firebase_credentials_remote}")
fi

sudo env "${env_args[@]}" .venv/bin/python src/wifi_notifier.py config/config.yaml --single-run
EOF
fi

if [[ ${INSTALL_SERVICE} -eq 1 ]]; then
  echo "[6/6] systemdサービスをインストールして起動"
  ssh "${PI_HOST}" bash -s -- "${REMOTE_PROJECT}" "${FIREBASE_CREDENTIALS_REMOTE}" <<'EOF'
set -e
remote_project="$1"
firebase_credentials_remote="$2"
cd "$remote_project"

get_config_value() {
  python3 - "$1" "$2" <<'PY'
import sys
import yaml
from pathlib import Path

section = sys.argv[1]
key = sys.argv[2]
cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8")) or {}
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

remote_project_path="$(pwd)"
service_user="$(id -un)"
service_group="$(id -gn)"
python_bin="${remote_project_path}/.venv/bin/python3"
gcal_env_name="$(get_config_value google_calendar credentials_file_env)"
gcal_env_value="$(get_config_value google_calendar credentials_file)"
firebase_enabled="$(get_config_value firebase enabled)"
firebase_env_name="$(get_config_value firebase credentials_file_env)"

service_env_lines=()
if [[ -n "${gcal_env_name}" && -n "${gcal_env_value}" ]]; then
  service_env_lines+=("Environment=${gcal_env_name}=${gcal_env_value}")
fi
if [[ -n "${firebase_enabled}" ]]; then
  if [[ -z "${firebase_env_name}" ]]; then
    echo "エラー: firebase.enabled=true ですが credentials_file_env が未設定です" >&2
    exit 1
  fi
  if [[ -z "${firebase_credentials_remote}" ]]; then
    echo "エラー: firebase.enabled=true ですが --firebase-credentials が未指定です" >&2
    exit 1
  fi
  service_env_lines+=("Environment=${firebase_env_name}=${firebase_credentials_remote}")
fi

if [[ -f "${remote_project_path}/wifi_notifier.log" ]]; then
  sudo chown "${service_user}:${service_group}" "${remote_project_path}/wifi_notifier.log"
fi

{
  cat <<EOF2
[Unit]
Description=WiFi Client Notifier
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${service_user}
Group=${service_group}
WorkingDirectory=${remote_project_path}
EOF2
  for service_env_line in "${service_env_lines[@]}"; do
    printf '%s\n' "${service_env_line}"
  done
  cat <<EOF2
ExecStart=${python_bin} ${remote_project_path}/src/wifi_notifier.py ${remote_project_path}/config/config.yaml
Restart=on-failure
RestartSec=30
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${remote_project_path}
AmbientCapabilities=CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_RAW
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wifi-notifier

[Install]
WantedBy=multi-user.target
EOF2
} | sudo tee /etc/systemd/system/wifi-notifier.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable wifi-notifier
sudo systemctl restart wifi-notifier
sleep 4
sudo systemctl --no-pager --lines=20 status wifi-notifier
EOF
else
  echo "[6/6] systemdサービスのインストールをスキップ"
fi

echo ""
echo "=== セットアップ完了 ==="
if [[ ${INSTALL_SERVICE} -eq 1 ]]; then
  echo "systemdサービスを有効化しました。状態確認:"
  echo "  ssh ${PI_HOST} sudo systemctl status wifi-notifier"
  echo "  ssh ${PI_HOST} sudo journalctl -u wifi-notifier -f"
else
  echo "常時実行する場合:"
  echo "  ssh ${PI_HOST}"
  echo "  cd ${REMOTE_PROJECT}"
  echo "  sudo .venv/bin/python src/wifi_notifier.py config/config.yaml"
fi
