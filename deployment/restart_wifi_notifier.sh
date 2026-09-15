#!/usr/bin/env bash

set -euo pipefail

# WiFi Client Notifierをsystemd経由で再起動する。
# --recover-unmanaged指定時だけ、systemd管理外の同一アプリを整理する。

SERVICE_NAME="wifi-notifier.service"
RECOVER_UNMANAGED=0
DAEMON_RELOAD=0

usage() {
  cat <<'USAGE'
使用方法:
  ./deployment/restart_wifi_notifier.sh [オプション]

オプション:
  --recover-unmanaged  systemd管理外のwifi_notifier.pyを停止してから再起動
  --daemon-reload      再起動前にsystemd定義を再読み込み
  -h, --help           ヘルプを表示

通常運用ではオプションなしで実行してください。
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recover-unmanaged)
      RECOVER_UNMANAGED=1
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
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "エラー: systemctlが見つかりません。systemd環境で実行してください。" >&2
  exit 1
fi

if ! "${SUDO[@]}" systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  echo "エラー: systemdサービスが見つかりません: ${SERVICE_NAME}" >&2
  echo "先にdeployment/setup_raspberrypi.shでサービスをインストールしてください。" >&2
  exit 1
fi

if [[ ${DAEMON_RELOAD} -eq 1 ]]; then
  echo "systemd定義を再読み込みします"
  "${SUDO[@]}" systemctl daemon-reload
fi

if [[ ${RECOVER_UNMANAGED} -eq 1 ]]; then
  echo "${SERVICE_NAME}を一時停止します"
  "${SUDO[@]}" systemctl stop "${SERVICE_NAME}"
  echo "systemd管理外のWiFi Notifierプロセスを確認します"
  unmanaged_pids=()
  while read -r pid command_line; do
    [[ -n "${pid}" ]] || continue
    case "${command_line}" in
      */src/wifi_notifier.py\ config/config.yaml*|*/src/wifi_notifier.py\ */config/config.yaml*)
        unmanaged_pids+=("${pid}")
        ;;
    esac
  done < <(ps -eo pid=,args=)

  if [[ ${#unmanaged_pids[@]} -gt 0 ]]; then
    echo "対象プロセスを停止します: ${unmanaged_pids[*]}"
    "${SUDO[@]}" kill "${unmanaged_pids[@]}" 2>/dev/null || true
    remaining=()
    for _ in {1..10}; do
      remaining=()
      for pid in "${unmanaged_pids[@]}"; do
        if kill -0 "${pid}" 2>/dev/null; then
          remaining+=("${pid}")
        fi
      done
      [[ ${#remaining[@]} -eq 0 ]] && break
      sleep 1
    done
    if [[ ${#remaining[@]} -gt 0 ]]; then
      echo "TERMで終了しなかったプロセスを強制終了します: ${remaining[*]}"
      "${SUDO[@]}" kill -KILL "${remaining[@]}" 2>/dev/null || true
    fi
  else
    echo "systemd管理外の対象プロセスはありません"
  fi
fi

echo "${SERVICE_NAME}を再起動します"
"${SUDO[@]}" systemctl restart "${SERVICE_NAME}"
"${SUDO[@]}" systemctl is-active --quiet "${SERVICE_NAME}"
echo "再起動しました: ${SERVICE_NAME}（active）"
