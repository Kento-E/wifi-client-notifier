#!/usr/bin/env bash
set -euo pipefail

# Raspberry Pi のハードウェア Watchdog を有効化し、
# 対象サービスの非稼働が継続した場合に自動再起動させるセットアップスクリプト。

SERVICE_NAME="wifi-notifier.service"
WATCHDOG_TIMEOUT="15"
CHECK_INTERVAL="5"
FAILURE_THRESHOLD="3"
CHECK_SCRIPT_PATH="/usr/local/sbin/check_wifi_notifier.sh"
WATCHDOG_CONF_PATH="/etc/watchdog.conf"
MODULES_LOAD_CONF="/etc/modules-load.d/bcm2835_wdt.conf"
MARKER_BEGIN="# BEGIN wifi-client-notifier-watchdog"
MARKER_END="# END wifi-client-notifier-watchdog"
WATCHDOG_RESTART_REQUIRED=0

usage() {
  cat <<'USAGE'
使用方法:
  ./deployment/setup_hardware_watchdog.sh [オプション]

オプション:
  --service <name>        監視対象の systemd サービス名
                          デフォルト: wifi-notifier.service
  --timeout <sec>         watchdog-timeout 秒数
                          デフォルト: 15
  --interval <sec>        チェック間隔秒数
                          デフォルト: 5
  --failure-threshold <n> 何回連続で非稼働なら再起動扱いにするか
                          デフォルト: 3
  -h, --help              このヘルプを表示

例:
  sudo ./deployment/setup_hardware_watchdog.sh
  sudo ./deployment/setup_hardware_watchdog.sh --service wifi-notifier.service --timeout 20 --interval 5 --failure-threshold 4
USAGE
}

is_positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

validate_positive_int() {
  local option_name="$1"
  local option_value="$2"
  if ! is_positive_int "${option_value}"; then
    echo "${option_name} は 1 以上の整数を指定してください" >&2
    exit 1
  fi
}

run_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --timeout)
      WATCHDOG_TIMEOUT="$2"
      shift 2
      ;;
    --interval)
      CHECK_INTERVAL="$2"
      shift 2
      ;;
    --failure-threshold)
      FAILURE_THRESHOLD="$2"
      shift 2
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

validate_positive_int "--timeout" "${WATCHDOG_TIMEOUT}"
validate_positive_int "--interval" "${CHECK_INTERVAL}"
validate_positive_int "--failure-threshold" "${FAILURE_THRESHOLD}"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl が見つかりません。systemd 環境で実行してください" >&2
  exit 1
fi

if [[ "${EUID}" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
  echo "root 権限が必要です。root で実行するか sudo をインストールしてください" >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get が見つかりません。Debian/Raspberry Pi OS 向けスクリプトです" >&2
  exit 1
fi

echo "=== Hardware Watchdog セットアップ開始 ==="
echo "監視サービス: ${SERVICE_NAME}"
echo "watchdog-timeout: ${WATCHDOG_TIMEOUT} 秒"
echo "チェック間隔: ${CHECK_INTERVAL} 秒"
echo "連続失敗閾値: ${FAILURE_THRESHOLD} 回"

echo "[1/7] watchdog パッケージをインストール"
run_root apt-get update
run_root apt-get install -y watchdog

echo "[2/7] dtparam=watchdog=on を有効化"
BOOT_CONFIG_PATH=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
  if run_root test -f "${candidate}"; then
    BOOT_CONFIG_PATH="${candidate}"
    break
  fi
done

if [[ -z "${BOOT_CONFIG_PATH}" ]]; then
  echo "boot config が見つかりませんでした (/boot/firmware/config.txt or /boot/config.txt)" >&2
  exit 1
fi

TMP_BOOT_CFG="$(mktemp)"
trap 'rm -f "${TMP_BOOT_CFG}" "${TMP_WATCHDOG_CFG:-}" "${TMP_CHECK_SCRIPT:-}"' EXIT

run_root cat "${BOOT_CONFIG_PATH}" > "${TMP_BOOT_CFG}"
if grep -Eq '^\s*dtparam=watchdog=on\s*$' "${TMP_BOOT_CFG}"; then
  echo "  既に有効化済みです: ${BOOT_CONFIG_PATH}"
else
  if grep -Eq '^\s*#?\s*dtparam=watchdog=' "${TMP_BOOT_CFG}"; then
    sed -E 's/^\s*#?\s*dtparam=watchdog=.*/dtparam=watchdog=on/' "${TMP_BOOT_CFG}" > "${TMP_BOOT_CFG}.new"
    mv "${TMP_BOOT_CFG}.new" "${TMP_BOOT_CFG}"
  else
    {
      echo ""
      echo "# wifi-client-notifier hardware watchdog"
      echo "dtparam=watchdog=on"
    } >> "${TMP_BOOT_CFG}"
  fi
  run_root cp "${BOOT_CONFIG_PATH}" "${BOOT_CONFIG_PATH}.bak.$(date +%Y%m%d%H%M%S)"
  run_root install -m 644 "${TMP_BOOT_CFG}" "${BOOT_CONFIG_PATH}"
  WATCHDOG_RESTART_REQUIRED=1
  echo "  反映しました: ${BOOT_CONFIG_PATH}"
fi

echo "[3/7] bcm2835_wdt モジュールをロード"
if ! lsmod | awk '{print $1}' | grep -qx 'bcm2835_wdt'; then
  run_root modprobe bcm2835_wdt
  echo "  モジュールをロードしました"
else
  echo "  モジュールは既にロード済みです"
fi

if run_root test -f "${MODULES_LOAD_CONF}" && run_root grep -qx 'bcm2835_wdt' "${MODULES_LOAD_CONF}"; then
  echo "  起動時ロード設定は既に反映済みです"
else
  printf '%s\n' "bcm2835_wdt" | run_root tee "${MODULES_LOAD_CONF}" >/dev/null
  echo "  起動時ロード設定を反映しました"
fi

echo "[4/7] サービス監視スクリプトを配置"
TMP_CHECK_SCRIPT="$(mktemp)"
cat > "${TMP_CHECK_SCRIPT}" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${1:-wifi-notifier.service}"
FAILURE_THRESHOLD="${2:-3}"
STATE_DIR="/run/wifi-notifier-watchdog"
STATE_FILE="${STATE_DIR}/fail-count"

mkdir -p "${STATE_DIR}"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
  echo "0" > "${STATE_FILE}"
  exit 0
fi

COUNT="0"
if [[ -f "${STATE_FILE}" ]]; then
  COUNT="$(cat "${STATE_FILE}" 2>/dev/null || echo "0")"
fi

if [[ ! "${COUNT}" =~ ^[0-9]+$ ]]; then
  COUNT="0"
fi

COUNT="$((COUNT + 1))"
echo "${COUNT}" > "${STATE_FILE}"

if (( COUNT < FAILURE_THRESHOLD )); then
  logger -t wifi-notifier-watchdog "${SERVICE_NAME} 非稼働を検出 (${COUNT}/${FAILURE_THRESHOLD})。まだ再起動はしません"
  exit 0
fi

logger -t wifi-notifier-watchdog "${SERVICE_NAME} が ${COUNT} 回連続で非稼働。Watchdog により再起動させます"
exit 1
EOS
if run_root test -f "${CHECK_SCRIPT_PATH}" && run_root cmp -s "${TMP_CHECK_SCRIPT}" "${CHECK_SCRIPT_PATH}"; then
  echo "  監視スクリプトは変更なしです"
else
  run_root install -m 755 "${TMP_CHECK_SCRIPT}" "${CHECK_SCRIPT_PATH}"
  WATCHDOG_RESTART_REQUIRED=1
  echo "  監視スクリプトを更新しました"
fi

echo "[5/7] /etc/watchdog.conf を設定"
TMP_WATCHDOG_CFG="$(mktemp)"
run_root cat "${WATCHDOG_CONF_PATH}" > "${TMP_WATCHDOG_CFG}"

awk -v begin="${MARKER_BEGIN}" -v end="${MARKER_END}" '
  $0 == begin {skip=1; next}
  $0 == end {skip=0; next}
  !skip {print}
' "${TMP_WATCHDOG_CFG}" > "${TMP_WATCHDOG_CFG}.clean"
mv "${TMP_WATCHDOG_CFG}.clean" "${TMP_WATCHDOG_CFG}"

{
  echo ""
  echo "${MARKER_BEGIN}"
  echo "watchdog-device = /dev/watchdog"
  echo "watchdog-timeout = ${WATCHDOG_TIMEOUT}"
  echo "interval = ${CHECK_INTERVAL}"
  echo "max-load-1 = 24"
  echo "test-binary = ${CHECK_SCRIPT_PATH} ${SERVICE_NAME} ${FAILURE_THRESHOLD}"
  echo "${MARKER_END}"
} >> "${TMP_WATCHDOG_CFG}"

if run_root cmp -s "${TMP_WATCHDOG_CFG}" "${WATCHDOG_CONF_PATH}"; then
  echo "  watchdog.conf は変更なしです"
else
  run_root cp "${WATCHDOG_CONF_PATH}" "${WATCHDOG_CONF_PATH}.bak.$(date +%Y%m%d%H%M%S)"
  run_root install -m 644 "${TMP_WATCHDOG_CFG}" "${WATCHDOG_CONF_PATH}"
  WATCHDOG_RESTART_REQUIRED=1
  echo "  watchdog.conf を更新しました"
fi

echo "[6/7] watchdog サービスを有効化・再起動"
if ! run_root systemctl is-enabled --quiet watchdog; then
  run_root systemctl enable watchdog
  echo "  watchdog サービスを有効化しました"
else
  echo "  watchdog サービスは既に有効化済みです"
fi

if (( WATCHDOG_RESTART_REQUIRED == 1 )); then
  run_root systemctl restart watchdog
  echo "  設定変更を反映するため watchdog を再起動しました"
else
  echo "  設定変更がないため watchdog 再起動をスキップしました"
fi

echo "[7/7] 動作確認"
run_root systemctl --no-pager --lines=20 status watchdog

cat <<EOF

=== 設定完了 ===
- ハードウェア Watchdog: 有効
- 監視対象サービス: ${SERVICE_NAME}

補足:
- ${SERVICE_NAME} が ${FAILURE_THRESHOLD} 回連続で非稼働になると、
  watchdog がフィードを停止し自動再起動が実行されます。
- 次回起動時にも有効化するため、${BOOT_CONFIG_PATH} と ${MODULES_LOAD_CONF} を更新済みです。
- すぐにブート設定反映を確実にしたい場合は再起動してください: sudo reboot
EOF
