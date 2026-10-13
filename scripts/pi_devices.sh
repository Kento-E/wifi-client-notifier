#!/bin/sh
set -eu

# 使い方: pi_devices.sh [--repeat-only]
#   --repeat-only  repeat_notification_devices に含まれる端末のみ出力する
repeat_only=0
for arg in "$@"; do
	case "$arg" in
	--repeat-only) repeat_only=1 ;;
	*)
		echo "Usage: $0 [--repeat-only]" >&2
		exit 1
		;;
	esac
done

project_dir="${WIFI_NOTIFIER_PROJECT_DIR:-$HOME/work/wifi-client-notifier}"
if [ ! -d "$project_dir" ] && [ -d "$HOME/wifi-client-notifier" ]; then
	project_dir="$HOME/wifi-client-notifier"
fi

# CAP_NET_RAW を付与した専用コピーがあれば使う（sudo なしで ARP スキャンするため）
python_bin="$project_dir/.venv/bin/python3-netraw"
if [ ! -x "$python_bin" ]; then
	python_bin="$project_dir/.venv/bin/python3"
fi

cd "$project_dir"
exec "$python_bin" -c '
import json
import sys

import yaml

from src.arp_scanner import ARPScanner

repeat_only = sys.argv[1] == "1"
config = yaml.safe_load(open("config/config.yaml", encoding="utf-8"))
arp_config = config.get("arp", {})
devices = ARPScanner(subnet=arp_config.get("subnet"), interface=arp_config.get("interface")).scan(
    timeout=arp_config.get("timeout", 2)
)
if repeat_only:
    repeat_devices = config.get("repeat_notification_devices") or []
    repeat_macs = {mac.strip().lower() for mac in repeat_devices if isinstance(mac, str) and mac.strip()}
    devices = [device for device in devices if device["mac"].lower() in repeat_macs]
print(json.dumps(devices, ensure_ascii=False, indent=2, sort_keys=True))
' "$repeat_only"
