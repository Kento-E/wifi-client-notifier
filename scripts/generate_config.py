#!/usr/bin/env python3
"""
GitHub Actions Secretsから設定ファイルを生成するスクリプト

環境変数から設定値を読み取り、config.yamlファイルを生成します。
DETECTION_METHOD 環境変数で検出方式を切り替えられます（デフォルト: "router"）。
"""

import os
import yaml
import sys


def get_env_required(key: str) -> str:
    """
    必須の環境変数を取得する。

    Args:
        key: 環境変数名

    Returns:
        環境変数の値

    Raises:
        ValueError: 環境変数が設定されていない場合
    """
    value = os.getenv(key)
    if not value:
        raise ValueError(f"必須の環境変数が設定されていません: {key}")
    return value


def get_env_optional(key: str, default: str = "") -> str:
    """
    オプションの環境変数を取得する。

    Args:
        key: 環境変数名
        default: デフォルト値

    Returns:
        環境変数の値またはデフォルト値
    """
    return os.getenv(key, default)


def parse_list(value: str) -> list:
    """
    カンマ区切りの文字列をリストに変換する。

    Args:
        value: カンマ区切りの文字列

    Returns:
        リスト
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def generate_config():
    """環境変数から設定ファイルを生成する。"""
    try:
        detection_method = get_env_optional("DETECTION_METHOD", "router")

        config = {
            "detection_method": detection_method,
        }

        if detection_method == "arp":
            # ARPスキャンモード（Raspberry Pi向け）
            arp_config: dict = {"timeout": int(get_env_optional("ARP_TIMEOUT", "2"))}
            subnet = get_env_optional("ARP_SUBNET")
            if subnet:
                arp_config["subnet"] = subnet
            interface = get_env_optional("ARP_INTERFACE")
            if interface:
                arp_config["interface"] = interface
            config["arp"] = arp_config
        else:
            # ルータAPIモード（デフォルト、GitHub Actions向け）
            config["router"] = {
                "ip": get_env_required("ROUTER_IP"),
                "username": get_env_required("ROUTER_USERNAME"),
                "password": get_env_required("ROUTER_PASSWORD"),
            }

        # メール設定（両モード共通で必須）
        config["email"] = {
            "smtp_server": get_env_required("SMTP_SERVER"),
            "smtp_port": int(get_env_required("SMTP_PORT")),
            "smtp_user": get_env_required("SMTP_USER"),
            "smtp_password": get_env_required("SMTP_PASSWORD"),
            "sender_email": get_env_required("SENDER_EMAIL"),
            "recipient_emails": parse_list(get_env_required("RECIPIENT_EMAILS")),
            "use_tls": get_env_optional("USE_TLS", "true").lower() == "true",
        }

        config["monitored_devices"] = parse_list(get_env_optional("MONITORED_DEVICES", ""))
        config["check_interval"] = int(get_env_optional("CHECK_INTERVAL", "60"))
        config["log_level"] = get_env_optional("LOG_LEVEL", "INFO")
        config["log_file"] = get_env_optional("LOG_FILE", "wifi_notifier.log")

        # config.yamlに書き出し
        with open("config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        print("✓ config.yaml を正常に生成しました")
        print(f"  - 検出方式: {detection_method}")
        if detection_method == "arp":
            print(f"  - サブネット: {config['arp'].get('subnet', '自動検出')}")
        else:
            print(f"  - ルータIP: {config['router']['ip']}")
        print(f"  - SMTPサーバー: {config['email']['smtp_server']}")
        print(f"  - 受信者数: {len(config['email']['recipient_emails'])}")
        print(f"  - 監視デバイス数: {len(config['monitored_devices'])}")

    except ValueError as e:
        print(f"✗ エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ 予期しないエラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    generate_config()
