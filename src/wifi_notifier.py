#!/usr/bin/env python3
"""
WiFi接続通知ツール

ローカルネットワーク上の新規デバイス接続を監視し、接続を検出した際に
メール通知を送信するスクリプトです。

検出方式:
  - "arp"    : ARPスキャンによるローカルネットワーク監視（Raspberry Pi向け、ルータ不要）
  - "router" : ルータ管理画面のAPIを使用した接続監視
"""

import requests
import time
import smtplib
import json
import os
import tempfile
import yaml
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional, Set

# 直接実行（python src/wifi_notifier.py）とモジュール実行（python -m src.wifi_notifier）の両方に対応
try:
    from src.html_parser import parse_wireless_lan_status, extract_devices_from_json
    from src.constants import DEFAULT_STATE_FILE
except ModuleNotFoundError:
    from html_parser import parse_wireless_lan_status, extract_devices_from_json
    from constants import DEFAULT_STATE_FILE


class WiFiRouter:
    """WiFiルータと通信するためのインターフェース。"""

    def __init__(self, router_ip: str, username: str, password: str):
        """
        ルータ接続を初期化する。

        Args:
            router_ip: ルータのIPアドレス
            username: 管理者ユーザー名
            password: 管理者パスワード
        """
        self.router_ip = router_ip
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = f"http://{router_ip}"

    def login(self) -> bool:
        """
        ルータにログインする（Basic認証）。

        Returns:
            ログイン成功時はTrue、失敗時はFalse
        """
        try:
            # 注記: これは汎用的なBasic認証の実装です
            # 実際のWiFiルータはモデルによって異なる認証方法が必要な場合があります
            # ユーザーは特定のルータモデルに合わせてカスタマイズする必要があります
            # SHA-256ハッシュなど他の認証方法についてはCUSTOMIZATION.mdを参照してください

            from requests.auth import HTTPBasicAuth

            # Basic認証を設定
            self.session.auth = HTTPBasicAuth(self.username, self.password)

            # 認証が必要なページにアクセスして確認
            response = self.session.get(f"{self.base_url}/index.html", timeout=10)
            return response.status_code == 200

        except Exception as e:
            logging.error(f"Login failed: {e}")
            return False

    def get_connected_devices(self) -> List[Dict[str, str]]:
        """
        現在接続中のWiFiデバイスのリストを取得する。

        Returns:
            デバイス情報を含む辞書のリスト
            各辞書には 'mac', 'ip', 'hostname' キーが含まれます
        """
        try:
            # 注記: 実際のエンドポイントはルータモデルによって異なります
            # 一般的なエンドポイント: /wlmaclist.cgi, /index.cgi/wireless_status
            # ユーザーは特定のモデルに合わせてカスタマイズする必要があります

            devices_url = f"{self.base_url}/index.cgi/wireless_client_list"
            response = self.session.get(devices_url, timeout=10)

            if response.status_code != 200:
                logging.warning(f"Failed to get device list: {response.status_code}")
                return []

            # レスポンスを解析 - ルータモデルによって異なります
            # これはプレースホルダー実装です
            devices = self._parse_device_list(response.text)
            return devices

        except Exception as e:
            logging.error(f"Error getting connected devices: {e}")
            return []

    def _parse_device_list(self, html_content: str) -> List[Dict[str, str]]:
        """
        HTMLレスポンスを解析してデバイス情報を抽出する。

        このメソッドはまずJSONとして解析を試み、失敗した場合はHTMLスクレイピングにフォールバックします。

        Args:
            html_content: ルータからのHTML/JSONレスポンス

        Returns:
            デバイス辞書のリスト
        """
        devices = []

        # まずJSONとして解析を試みる
        try:
            json_data = json.loads(html_content)
            devices = extract_devices_from_json(json_data)
            if devices:
                logging.debug(f"Parsed {len(devices)} devices from JSON")
                return devices
        except (json.JSONDecodeError, ValueError):
            # JSONとしての解析に失敗した場合はHTMLスクレイピングにフォールバックする
            logging.debug("JSONとして解析できなかったため、HTMLパースにフォールバックします")

        # HTMLスクレイピングにフォールバック
        devices = parse_wireless_lan_status(html_content)
        if devices:
            logging.debug(f"Parsed {len(devices)} devices from HTML")

        return devices


class EmailNotifier:
    """SMTP経由でメール通知を処理する。"""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        sender_email: str,
        recipient_emails: List[str],
        use_tls: bool = True,
    ):
        """
        メール通知機能を初期化する。

        Args:
            smtp_server: SMTPサーバーアドレス
            smtp_port: SMTPサーバーポート
            smtp_user: SMTPユーザー名
            smtp_password: SMTPパスワード
            sender_email: 送信元メールアドレス
            recipient_emails: 受信者メールアドレスのリスト
            use_tls: TLSを使用するか（デフォルト: True）
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_email = sender_email
        self.recipient_emails = recipient_emails
        self.use_tls = use_tls

    def send_notification(self, device_info: Dict[str, str]) -> bool:
        """
        新しいデバイス接続についてメール通知を送信する。

        Args:
            device_info: デバイス情報を含む辞書

        Returns:
            メール送信成功時はTrue、失敗時はFalse
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(self.recipient_emails)
            msg["Subject"] = f"新しいWiFi接続を検出 - {device_info.get('mac', 'Unknown Device')}"

            # メール本文を作成
            body = self._create_email_body(device_info)
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # メールを送信
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)

            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()

            logging.info(f"Notification sent for device: {device_info.get('mac', 'Unknown')}")
            return True

        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False

    def _create_email_body(self, device_info: Dict[str, str]) -> str:
        """
        メール本文テキストを作成する。

        Args:
            device_info: デバイス情報を含む辞書

        Returns:
            フォーマット済みのメール本文
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        body = f"""
新しいWiFi接続が検出されました

検出時刻: {timestamp}
MACアドレス: {device_info.get('mac', 'Unknown')}
IPアドレス: {device_info.get('ip', 'Unknown')}
ホスト名: {device_info.get('hostname', 'Unknown')}
メーカー: {device_info.get('vendor', 'Unknown')}

---
WiFi Client Notifier
"""
        return body.strip()


class WiFiMonitor:
    """WiFi接続を監視して通知を送信する。"""

    def __init__(self, config_path: str):
        """
        設定ファイルを使用して監視機能を初期化する。

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self._setup_logging()  # 他の処理の前にロギングを設定
        self.router: Optional[WiFiRouter] = None
        self.arp_scanner = None
        self.notifier: Optional[EmailNotifier] = None
        self.known_devices: Set[str] = set()
        self.monitored_macs: Set[str] = set()
        self.missing_counts: Dict[str, int] = {}
        self.last_notified_at: Dict[str, float] = {}
        self.disconnect_grace_scans: int = 3
        self.notification_cooldown_seconds: int = 0
        self.state_file: str = self.config.get("state_file", DEFAULT_STATE_FILE)
        self.state_loaded: bool = False
        self._initialize_components()

    def _load_config(self, config_path: str) -> Dict:
        """設定ファイルを読み込む（YAML形式）。"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"エラー: 設定ファイル '{config_path}' が見つかりません")
            print("設定ファイルを作成してください:")
            print("  cp config/config.example.yaml config.yaml")
            raise
        except Exception as e:
            # ロギングがまだ設定されていないためprintを使用
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            raise

    def _setup_logging(self):
        """ロギング設定をセットアップする。"""
        log_level = self.config.get("log_level", "INFO")
        log_file = self.config.get("log_file", "wifi_notifier.log")

        # 既存のハンドラーをクリアして最初から設定
        logging.root.handlers = []
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
            force=True,
        )

    def _initialize_components(self):
        """検出方式に応じたコンポーネントを初期化する。"""
        detection_method = self.config.get("detection_method")
        valid_methods = ("arp", "router")
        if detection_method is None:
            raise ValueError(
                "detection_method が設定されていません。"
                f" config.yaml に detection_method を指定してください。有効な値: {valid_methods}。"
            )
        if detection_method not in valid_methods:
            raise ValueError(
                f"detection_method の値 '{detection_method}' は無効です。"
                f" 有効な値: {valid_methods}。"
                " config.yaml の detection_method を確認してください。"
            )

        if detection_method == "arp":
            # ARPスキャンモード（Raspberry Pi向け）
            try:
                from src.arp_scanner import ARPScanner
            except ModuleNotFoundError:
                from arp_scanner import ARPScanner

            arp_config = self.config.get("arp", {})
            self.arp_scanner = ARPScanner(
                subnet=arp_config.get("subnet"),
                interface=arp_config.get("interface"),
            )
            logging.info("検出方式: ARPスキャン（ローカルネットワーク）")
        else:
            # ルータAPIモード
            router_config = self.config.get("router")
            if not router_config:
                raise ValueError("detection_method が 'router' の場合は 'router' セクションの設定が必要です。")
            self.router = WiFiRouter(
                router_config["ip"], router_config["username"], router_config["password"]
            )
            logging.info("検出方式: ルータAPI")

        # メール通知を初期化
        email_config = self.config["email"]
        self.notifier = EmailNotifier(
            email_config["smtp_server"],
            email_config["smtp_port"],
            email_config["smtp_user"],
            email_config["smtp_password"],
            email_config["sender_email"],
            email_config["recipient_emails"],
            email_config.get("use_tls", True),
        )

        # 監視対象デバイスを読み込む（指定されている場合）
        monitored_devices = self.config.get("monitored_devices", [])
        self.monitored_macs = {mac.lower() for mac in monitored_devices}

        # 切断判定の猶予回数（ARP検出の一時的な揺らぎ対策）
        raw_grace_scans = self.config.get("disconnect_grace_scans", 3)
        try:
            self.disconnect_grace_scans = max(1, int(raw_grace_scans))
        except (TypeError, ValueError):
            self.disconnect_grace_scans = 3
            logging.warning(
                "disconnect_grace_scans の値が不正のため 3 を使用します: %s",
                raw_grace_scans,
            )
        logging.info(f"切断判定の猶予回数: {self.disconnect_grace_scans}回（連続で見失った場合に切断扱い）")

        # 同一端末の短時間な再通知を抑止するためのクールダウン
        raw_cooldown_minutes = self.config.get("notification_cooldown_minutes", 0)
        try:
            self.notification_cooldown_seconds = max(0, int(raw_cooldown_minutes) * 60)
        except (TypeError, ValueError):
            self.notification_cooldown_seconds = 0
            logging.warning(
                "notification_cooldown_minutes の値が不正のため 0 を使用します: %s",
                raw_cooldown_minutes,
            )
        if self.notification_cooldown_seconds > 0:
            logging.info(
                "通知クールダウン: %s分（同一MACの再通知を抑止）",
                self.notification_cooldown_seconds // 60,
            )
        else:
            logging.info("通知クールダウン: 無効")

        logging.info("コンポーネントの初期化が完了しました")

    def _get_current_devices(self) -> List[Dict[str, str]]:
        """
        現在の検出方式を使用して接続中デバイスのリストを取得する。

        Returns:
            デバイス情報を含む辞書のリスト
        """
        if self.arp_scanner is not None:
            arp_config = self.config.get("arp", {})
            timeout = arp_config.get("timeout", 2)
            try:
                return self.arp_scanner.scan(timeout=timeout)
            except Exception as e:
                logging.error(f"ARPスキャンに失敗しました: {e}")
                return []
        elif self.router is not None:
            return self.router.get_connected_devices()
        else:
            logging.error("有効な検出コンポーネントが設定されていません")
            return []

    def start(self, single_run: bool = False):
        """
        WiFi接続の監視を開始する。

        Args:
            single_run: Trueの場合、1回だけチェックして終了
        """
        logging.info("WiFiモニターを起動しています")

        # ルータAPIモードの場合はログインが必要
        if self.router is not None:
            if not self.router.login():
                logging.error("ルータへのログインに失敗しました")
                return
            logging.info("ルータへのログインに成功しました")

        # 前回の状態を読み込む（初回は空状態）
        self._load_state()
        if not self.state_loaded:
            # 初回は現在接続中デバイスをベースラインとして登録し、通知スパイクを防ぐ
            initial_devices = self._get_current_devices()
            self.known_devices = {dev["mac"].lower() for dev in initial_devices}
            self.missing_counts = {mac: 0 for mac in self.known_devices}
            logging.info(
                "初回実行のため現在接続中デバイスをベースライン登録します: %s台",
                len(self.known_devices),
            )

        if single_run:
            # 1回だけチェックして終了
            logging.info("シングルランモード: 1回チェックして終了します")
            self._check_for_new_devices()
            self._save_state()
            logging.info("シングルランが完了しました")
            return

        # 監視ループを開始
        check_interval = self.config.get("check_interval", 60)

        try:
            while True:
                self._check_for_new_devices()
                self._save_state()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logging.info("WiFiモニターを停止しています")
        except Exception as e:
            logging.error(f"モニターでエラーが発生しました: {e}")

    def _load_state(self) -> bool:
        """
        状態ファイルから既知デバイス情報を読み込む。

        Returns:
            読み込みに成功した場合はTrue、状態ファイルがない/不正の場合はFalse
        """
        if not os.path.exists(self.state_file):
            self.state_loaded = False
            self.known_devices = set()
            self.missing_counts = {}
            self.last_notified_at = {}
            return False

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            known_devices_list = state.get("known_devices", [])
            if not isinstance(known_devices_list, list):
                raise ValueError("known_devices は配列である必要があります")

            self.known_devices = {
                mac.strip().lower()
                for mac in known_devices_list
                if isinstance(mac, str) and mac.strip()
            }

            raw_missing_counts = state.get("missing_counts", {})
            self.missing_counts = {}
            if isinstance(raw_missing_counts, dict):
                for mac, count in raw_missing_counts.items():
                    if not isinstance(mac, str):
                        continue
                    try:
                        parsed_count = int(count)
                        if parsed_count < 0:
                            logging.warning(
                                "状態ファイルに負の missing_counts を検出したため 0 に補正します: "
                                f"{mac}={parsed_count}"
                            )
                            parsed_count = 0
                        self.missing_counts[mac.lower()] = parsed_count
                    except (TypeError, ValueError):
                        continue

            for mac in self.known_devices:
                self.missing_counts.setdefault(mac, 0)

            raw_last_notified_at = state.get("last_notified_at", {})
            self.last_notified_at = {}
            if isinstance(raw_last_notified_at, dict):
                for mac, timestamp in raw_last_notified_at.items():
                    if not isinstance(mac, str):
                        continue
                    try:
                        parsed_timestamp = float(timestamp)
                        if parsed_timestamp < 0:
                            continue
                        self.last_notified_at[mac.lower()] = parsed_timestamp
                    except (TypeError, ValueError):
                        continue

            self.state_loaded = True
            logging.info(f"状態ファイルを読み込みました: known={len(self.known_devices)} " f"({self.state_file})")
            return True

        except Exception as e:
            logging.warning(f"状態ファイルの読み込みに失敗したため空状態で開始します: {e}")
            self.state_loaded = False
            self.known_devices = set()
            self.missing_counts = {}
            self.last_notified_at = {}
            return False

    def _save_state(self):
        """既知デバイス情報を状態ファイルに保存する。"""
        tmp_path = None
        try:
            state = {
                "known_devices": sorted(self.known_devices),
                "missing_counts": {
                    mac: self.missing_counts.get(mac, 0) for mac in self.known_devices
                },
                "last_notified_at": {
                    mac: self.last_notified_at[mac] for mac in sorted(self.last_notified_at)
                },
            }
            state_dir = os.path.dirname(self.state_file)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)

            fd, tmp_path = tempfile.mkstemp(
                prefix=".wifi_notifier_state_",
                suffix=".tmp",
                dir=state_dir or ".",
                text=True,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.state_file)
            tmp_path = None
        except Exception as e:
            logging.error(f"状態ファイルの保存に失敗しました: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _check_for_new_devices(self):
        """新しいデバイス接続をチェックする。"""
        try:
            current_devices = self._get_current_devices()
            current_macs = {dev["mac"].lower() for dev in current_devices}

            # 新しいデバイスを検出
            new_macs = current_macs - self.known_devices

            for mac in new_macs:
                # デバイス情報を検索
                device_info = next(
                    (dev for dev in current_devices if dev["mac"].lower() == mac), None
                )

                if device_info:
                    # このデバイスについて通知すべきかチェック
                    should_notify = (
                        not self.monitored_macs  # フィルターがない場合は全て通知
                        or mac in self.monitored_macs  # または監視リストに含まれている場合
                    )

                    if should_notify:
                        cooldown_remaining = self._get_notification_cooldown_remaining(mac)
                        if cooldown_remaining > 0:
                            logging.info(
                                "同一端末の再通知を抑止しました: %s（クールダウン残り約%s秒）",
                                mac,
                                cooldown_remaining,
                            )
                        else:
                            logging.info(f"新しいデバイスを検出しました: {mac}")
                            sent = self.notifier.send_notification(device_info)
                            if sent:
                                self.last_notified_at[mac] = time.time()
                    else:
                        logging.debug(f"新しいデバイスを検出しましたが、監視対象外です: {mac}")

                    self.known_devices.add(mac)
                    self.missing_counts[mac] = 0

            # 見えているデバイスは見失いカウントをリセット
            for mac in current_macs:
                if mac in self.known_devices:
                    self.missing_counts[mac] = 0

            # 既知セットから見えなくなったデバイスを猶予付きで切断判定
            disconnected_candidates = self.known_devices - current_macs
            disconnected: Set[str] = set()
            for mac in disconnected_candidates:
                miss_count = self.missing_counts.get(mac, 0) + 1
                self.missing_counts[mac] = miss_count
                if miss_count >= self.disconnect_grace_scans:
                    disconnected.add(mac)

            if disconnected:
                logging.info(
                    f"切断されたデバイス数: {len(disconnected)}" f"（連続{self.disconnect_grace_scans}回見失いで判定）"
                )
                for mac in disconnected:
                    self.known_devices.discard(mac)
                    self.missing_counts.pop(mac, None)

        except Exception as e:
            logging.error(f"新しいデバイスのチェック中にエラーが発生しました: {e}")

    def _get_notification_cooldown_remaining(self, mac: str) -> int:
        """同一MACへの再通知クールダウン残秒数を返す。"""
        if self.notification_cooldown_seconds <= 0:
            return 0

        last_sent = self.last_notified_at.get(mac)
        if last_sent is None:
            return 0

        elapsed = int(time.time() - last_sent)
        remaining = self.notification_cooldown_seconds - elapsed
        return max(0, remaining)


def main():
    """メインエントリーポイント。"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python src/wifi_notifier.py <config_file> [--single-run]")
        print("Example: python src/wifi_notifier.py config.yaml")
        print("Example: python src/wifi_notifier.py config.yaml --single-run")
        sys.exit(1)

    config_file = sys.argv[1]
    single_run = "--single-run" in sys.argv

    try:
        monitor = WiFiMonitor(config_file)
        monitor.start(single_run=single_run)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
