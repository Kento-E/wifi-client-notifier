#!/bin/sh
set -eu

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
exec "$python_bin" -c 'import json; import yaml; from src.arp_scanner import ARPScanner; config=yaml.safe_load(open("config/config.yaml", encoding="utf-8")); arp_config=config.get("arp", {}); devices=ARPScanner(subnet=arp_config.get("subnet"), interface=arp_config.get("interface")).scan(timeout=arp_config.get("timeout", 2)); print(json.dumps(devices, ensure_ascii=False, indent=2, sort_keys=True))'
