#!/usr/bin/env bash

set -euo pipefail

# Raspberry Pi ConnectへRaspberry Piを登録するスクリプト
# ローカルPCから実行し、SSH経由で認証キー（auth key）を使ってサインインする。
# 認証キーはConnectのSettingsページで発行する（個人用は作成から6時間で失効・1回限り・1台に1つ）。

PI_HOST="${PI_HOST:-}"
AUTH_KEY="${RPI_CONNECT_AUTH_KEY:-}"
AUTH_KEY_FILE=""

usage() {
  cat <<'USAGE'
使用方法:
  ./deployment/register_rpi_connect.sh [オプション]

オプション:
  --host <user@host>       SSH接続先（環境変数 PI_HOST より優先）
  --auth-key-file <path>   認証キーを書いたローカルファイル
                           （未指定時は環境変数 RPI_CONNECT_AUTH_KEY、それも無ければ入力を求める）
  -h, --help               ヘルプを表示

例:
  PI_HOST=pi@raspberrypi.local ./deployment/register_rpi_connect.sh
  ./deployment/register_rpi_connect.sh --host pi@raspberrypi.local --auth-key-file ~/rpi-connect.key
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      PI_HOST="$2"
      shift 2
      ;;
    --auth-key-file)
      AUTH_KEY_FILE="$2"
      shift 2
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

if [[ -z "${PI_HOST}" ]]; then
  echo "エラー: SSH接続先が未指定です。--host または環境変数 PI_HOST を指定してください。" >&2
  echo "例: PI_HOST=pi@raspberrypi.local ./deployment/register_rpi_connect.sh" >&2
  exit 1
fi

echo "=== Raspberry Pi Connect 登録 ==="
echo "接続先: ${PI_HOST}"

echo "[1/4] SSH接続確認"
ssh -o BatchMode=yes -o ConnectTimeout=8 "${PI_HOST}" "echo 'SSH接続OK'"

echo "[2/4] rpi-connect-lite導入・常駐設定"
ssh "${PI_HOST}" bash -s <<'EOF'
set -e
if ! command -v rpi-connect >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y rpi-connect-lite
fi
# Connectはユーザーサービスのため、ログインしていなくても動くようにlingerを有効化する
sudo loginctl enable-linger "$(id -un)"
rpi-connect on
EOF

if ssh "${PI_HOST}" "rpi-connect status" | grep -q "Signed in: yes"; then
  echo "[3/4] 既にサインイン済みのため登録をスキップ"
else
  if [[ -n "${AUTH_KEY_FILE}" ]]; then
    AUTH_KEY="$(tr -d '[:space:]' < "${AUTH_KEY_FILE}")"
  fi
  if [[ -z "${AUTH_KEY}" ]]; then
    read -r -s -p "認証キー（rpuak_... / rpoak_...）を入力してください: " AUTH_KEY
    echo ""
  fi
  if [[ "${AUTH_KEY}" != rpuak_* && "${AUTH_KEY}" != rpoak_* ]]; then
    echo "エラー: 認証キーの形式が不正です（rpuak_ または rpoak_ で始まる必要があります）" >&2
    exit 1
  fi

  echo "[3/4] 認証キーでサインイン"
  # コマンドライン引数に載せるとpsで見えるため、標準入力経由で一時ファイルに書き出して渡す
  # mktempは所有者のみ読み書き可（600）で作成される
  printf '%s\n' "${AUTH_KEY}" | ssh "${PI_HOST}" \
    'key_file="$(mktemp)" && trap "rm -f \"$key_file\"" EXIT && cat > "$key_file" && rpi-connect signin --auth-key=@"$key_file" </dev/null'
fi

echo "[4/4] 状態確認"
ssh "${PI_HOST}" "rpi-connect status"

echo ""
echo "=== 登録完了 ==="
echo "https://connect.raspberrypi.com/ からデバイスにアクセスできます。"
