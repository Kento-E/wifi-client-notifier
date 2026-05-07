#!/usr/bin/env python3
"""
WiFi接続通知ツール

ローカルネットワーク上の新規デバイス接続を監視し、接続を検出した際に
メール通知を送信するスクリプトです。

検出方式:
  - "arp"    : ARPスキャンによるローカルネットワーク監視（Raspberry Pi向け、ルータ不要）
  - "router" : ルータ管理画面のAPIを使用した接続監視
"""

import time
import os
import logging
import sys
from typing import Dict, List, Optional, Set

try:
    from src.router import WiFiRouter
    from src.notifiers import EmailNotifier, FirebaseNotifier, GoogleCalendarNotifier
    from src.config_manager import ConfigManager
    from src.state_manager import StateManager
    from src.notification_handler import NotificationHandler
except ModuleNotFoundError:
    from router import WiFiRouter
    from notifiers import EmailNotifier, FirebaseNotifier, GoogleCalendarNotifier
    from config_manager import ConfigManager
    from state_manager import StateManager
    from notification_handler import NotificationHandler


class WiFiMonitor:
    """WiFi接続を監視して通知を送信する。"""

    def __init__(self, config_path: str):
        """
        設定ファイルを使用して監視機能を初期化する。

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = ConfigManager.load_config(config_path)
        self.config_dir = os.path.dirname(os.path.abspath(config_path))
        ConfigManager.setup_logging(self.config)

        self.router: Optional[WiFiRouter] = None
        self.arp_scanner = None
        self.notifiers: List[object] = []

        # 状態管理の初期化
        state_file_path = ConfigManager.get_state_file_path(self.config, config_path)
        self.state_manager = StateManager(state_file_path)

        # 設定値の初期化
        self.monitored_macs: Set[str] = set()
        self.repeat_notification_macs: Set[str] = set()
        self.disconnect_grace_scans: int = 3
        self.notification_cooldown_seconds: int = 0
        self.reconnect_notify_after_seconds: int = 3600
        self.notify_unknown_devices_once: bool = False
        self.notification_handler: Optional[NotificationHandler] = None
        self.notifier_init_errors: List[str] = []

        self._initialize_components()

    def _initialize_components(self):
        """検出方式に応じたコンポーネントを初期化する。"""
        detection_method = ConfigManager.validate_detection_method(self.config)

        if detection_method == "arp":
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
            router_config = ConfigManager.validate_router_config(self.config)
            self.router = WiFiRouter(
                router_config["ip"], router_config["username"], router_config["password"]
            )
            logging.info("検出方式: ルータAPI")

        # メール通知の初期化
        email_config = ConfigManager.get_email_config(self.config)
        email_explicitly_enabled = ConfigManager.parse_bool_config(
            email_config.get("enabled"),
            default=False,  # 明示的に enabled: true を設定した場合のみ有効
        )
        self.fallback_email_notifier = None
        if email_config:
            try:
                validated_email_config = ConfigManager.validate_email_config(self.config)
                email_notifier = EmailNotifier(
                    validated_email_config["smtp_server"],
                    validated_email_config["smtp_port"],
                    validated_email_config["smtp_user"],
                    validated_email_config["smtp_password"],
                    validated_email_config["sender_email"],
                    validated_email_config["recipient_emails"],
                    validated_email_config.get("use_tls", True),
                )
                if email_explicitly_enabled:
                    self.notifiers.append(email_notifier)
                    logging.info("メール通知: 有効")
                else:
                    # gc/firebase エラー時のフォールバックとして保持
                    self.fallback_email_notifier = email_notifier
                    logging.info(
                        "メール通知: 無効（gc/firebase エラー時はフォールバックとして送信）"
                    )
            except Exception as e:
                logging.warning("メール通知の設定が不正なためフォールバックも無効です: %s", e)
                logging.info("メール通知: 無効")
        else:
            logging.info("メール通知: 無効")

        # Google Calendar通知の初期化
        calendar_config = ConfigManager.get_google_calendar_config(self.config)
        calendar_enabled = ConfigManager.parse_bool_config(
            calendar_config.get("enabled"), default=False
        )

        if calendar_enabled:
            self._initialize_google_calendar(calendar_config)
        else:
            logging.info("Googleカレンダー通知: 無効")

        firebase_config = ConfigManager.get_firebase_config(self.config)
        firebase_enabled = ConfigManager.parse_bool_config(
            firebase_config.get("enabled"),
            default=False,
        )
        if firebase_enabled:
            self._initialize_firebase(firebase_config)
        else:
            logging.info("Firebase通知: 無効")

        if not self.notifiers and self.fallback_email_notifier is None:
            raise ValueError(
                "有効な通知チャネルがありません。email.enabled、"
                "google_calendar.enabled、firebase.enabled のいずれかを有効にしてください"
            )

        # 監視対象デバイスの設定
        monitored_devices = self.config.get("monitored_devices", [])
        self.monitored_macs = {mac.lower() for mac in monitored_devices}

        repeat_notification_devices = self.config.get("repeat_notification_devices", [])
        if not isinstance(repeat_notification_devices, list):
            logging.warning(
                "repeat_notification_devices は配列である必要があります: %s",
                repeat_notification_devices,
            )
            repeat_notification_devices = []
        self.repeat_notification_macs = {
            mac.strip().lower()
            for mac in repeat_notification_devices
            if isinstance(mac, str) and mac.strip()
        }

        self.notify_unknown_devices_once = ConfigManager.parse_bool_config(
            self.config.get("notify_unknown_devices_once"),
            default=False,
        )

        branch_mode = bool(self.repeat_notification_macs) or (
            "notify_unknown_devices_once" in self.config
        )

        if branch_mode:
            logging.info(
                "通知分岐モード: 有効（再通知対象MAC %s件 / 未知端末初回のみ通知: %s）",
                len(self.repeat_notification_macs),
                "有効" if self.notify_unknown_devices_once else "無効",
            )
            if self.monitored_macs:
                logging.info("通知分岐モードが有効のため monitored_devices は無視されます")
        elif self.monitored_macs:
            logging.info("通知フィルタ: monitored_devices %s件", len(self.monitored_macs))
        else:
            logging.info("通知フィルタ: なし")

        # 切断判定の猶予回数
        self.disconnect_grace_scans = ConfigManager.parse_int_config(
            self.config.get("disconnect_grace_scans", 3),
            default=3,
            key_name="disconnect_grace_scans",
        )
        logging.info(
            "切断判定の猶予回数: %s回（連続で見失った場合に切断扱い）",
            self.disconnect_grace_scans,
        )

        # 通知クールダウン
        raw_cooldown_minutes = self.config.get(
            "notification_cool_down_minutes",
            self.config.get("notification_cooldown_minutes", 0),
        )
        self.notification_cooldown_seconds = (
            ConfigManager.parse_int_config(
                raw_cooldown_minutes,
                default=0,
                key_name="notification_cool_down_minutes",
                minimum=0,
            )
            * 60
        )
        if self.notification_cooldown_seconds > 0:
            logging.info(
                "通知クールダウン: %s分（同一MACの再通知を抑止）",
                self.notification_cooldown_seconds // 60,
            )
        else:
            logging.info("通知クールダウン: 無効")

        # 再接続通知閾値
        raw_reconnect_minutes = self.config.get("reconnect_notify_after_minutes", 60)
        self.reconnect_notify_after_seconds = (
            ConfigManager.parse_int_config(
                raw_reconnect_minutes,
                default=60,
                key_name="reconnect_notify_after_minutes",
                minimum=0,
            )
            * 60
        )
        if self.reconnect_notify_after_seconds > 0:
            logging.info(
                "再接続通知閾値: %s分（この時間以上の不在後の再接続はクールダウンを無視して通知）",
                self.reconnect_notify_after_seconds // 60,
            )
        else:
            logging.info("再接続通知閾値: 無効（0分）")

        # 通知ハンドラーの初期化
        self.notification_handler = NotificationHandler(
            self.state_manager,
            self.notifiers,
            notification_cooldown_seconds=self.notification_cooldown_seconds,
            reconnect_notify_after_seconds=self.reconnect_notify_after_seconds,
            monitored_macs=self.monitored_macs,
            repeat_notification_macs=self.repeat_notification_macs,
            notify_unknown_devices_once=self.notify_unknown_devices_once,
            fallback_email_notifier=self.fallback_email_notifier,
        )
        if self.notifier_init_errors:
            self.notification_handler.notifier_init_errors = list(self.notifier_init_errors)

        logging.info("コンポーネントの初期化が完了しました")

    def _initialize_google_calendar(self, calendar_config: Dict) -> None:
        """Google Calendar通知を初期化する。

        Args:
            calendar_config: Google Calendar設定
        """
        try:
            credentials_file_env = str(calendar_config.get("credentials_file_env", "")).strip()
            credentials_file = ""

            if credentials_file_env:
                credentials_file = os.getenv(credentials_file_env, "")

            credentials_file = os.path.expanduser(str(credentials_file).strip())
            calendar_id = str(calendar_config.get("calendar_id", "")).strip()

            if not credentials_file_env:
                raise ValueError(
                    "google_calendar.enabled が true の場合は "
                    "credentials_file_env を設定してください"
                )
            if not credentials_file:
                raise ValueError(f"環境変数が未設定または空です: {credentials_file_env}")
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(
                    f"GoogleサービスアカウントJSONが見つかりません: {credentials_file}"
                )
            if not calendar_id:
                raise ValueError(
                    "google_calendar.enabled が true の場合は calendar_id を設定してください"
                )

            calendar_notifier = GoogleCalendarNotifier(
                credentials_file=credentials_file,
                calendar_id=calendar_id,
                timezone_name=calendar_config.get("timezone", "Asia/Tokyo"),
                summary_prefix=calendar_config.get("summary_prefix", "🛜"),
                max_retries=calendar_config.get("max_retries", 3),
                retry_delay_seconds=calendar_config.get("retry_delay_seconds", 3),
                dedupe_window_minutes=calendar_config.get("dedupe_window_minutes", 10),
            )
            self.notifiers.append(calendar_notifier)
            logging.info(
                "Googleカレンダー通知: 有効（カレンダーID: %s, summary_prefix: %s）",
                calendar_id,
                calendar_notifier.summary_prefix,
            )
        except Exception as e:
            self.notifier_init_errors.append(f"Googleカレンダー通知の初期化に失敗: {e}")
            logging.error(
                "Googleカレンダー通知の初期化に失敗したため他の通知チャネルのみ継続します: %s",
                e,
            )

    def _initialize_firebase(self, firebase_config: Dict) -> None:
        """Firebase 通知を初期化する。"""
        try:
            credentials_file_env = str(firebase_config.get("credentials_file_env", "")).strip()
            credentials_file = ""

            if credentials_file_env:
                credentials_file = os.getenv(credentials_file_env, "")

            credentials_file = os.path.expanduser(str(credentials_file).strip())
            project_id = str(firebase_config.get("project_id", "")).strip()
            registration_tokens = ConfigManager.parse_string_list_config(
                firebase_config.get("registration_tokens", [])
            )

            if not credentials_file_env:
                raise ValueError(
                    "firebase.enabled が true の場合は credentials_file_env を設定してください"
                )
            if not credentials_file:
                raise ValueError(f"環境変数が未設定または空です: {credentials_file_env}")
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(
                    f"FirebaseサービスアカウントJSONが見つかりません: {credentials_file}"
                )
            if not project_id:
                raise ValueError("firebase.enabled が true の場合は project_id を設定してください")
            if not registration_tokens:
                raise ValueError(
                    "firebase.enabled が true の場合は registration_tokens を設定してください"
                )

            firebase_notifier = FirebaseNotifier(
                project_id=project_id,
                credentials_file=credentials_file,
                registration_tokens=registration_tokens,
                notification_title_prefix=firebase_config.get(
                    "notification_title_prefix", "WiFi通知"
                ),
                timeout_seconds=firebase_config.get("timeout_seconds", 10),
            )
            self.notifiers.append(firebase_notifier)
            logging.info(
                "Firebase通知: 有効（project_id: %s, 送信先: %s件）",
                project_id,
                len(registration_tokens),
            )
        except Exception as e:
            self.notifier_init_errors.append(f"Firebase通知の初期化に失敗: {e}")
            logging.error(
                "Firebase通知の初期化に失敗したため他の通知チャネルのみ継続します: %s",
                e,
            )

    def _get_current_devices(self) -> List[Dict[str, str]]:
        """現在の検出方式を使用して接続中デバイスのリストを取得する。"""
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
        """WiFi接続の監視を開始する。"""
        logging.info("WiFiモニターを起動しています")

        if self.router is not None:
            if not self.router.login():
                logging.error("ルータへのログインに失敗しました")
                return
            logging.info("ルータへのログインに成功しました")

        self.state_manager.load()
        if not self.state_manager.state_loaded:
            initial_devices = self._get_current_devices()
            initial_macs = {dev["mac"].lower() for dev in initial_devices}
            for mac in initial_macs:
                self.state_manager.add_known_device(mac)
            self.notification_handler.init_baseline_unknown_devices(initial_macs)
            logging.info(
                "初回実行のため現在接続中デバイスをベースライン登録します: %s台",
                len(initial_macs),
            )

        if single_run:
            logging.info("シングルランモード: 1回チェックして終了します")
            self._check_for_new_devices()
            self.state_manager.save()
            logging.info("シングルランが完了しました")
            return

        check_interval = self.config.get("check_interval", 60)

        try:
            while True:
                self._check_for_new_devices()
                self.state_manager.save()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logging.info("WiFiモニターを停止しています")
        except Exception as e:
            logging.error("モニターでエラーが発生しました: %s", e)

    def _check_for_new_devices(self):
        """新しいデバイス接続をチェックする。"""
        try:
            current_devices = self._get_current_devices()
            current_macs = {dev["mac"].lower() for dev in current_devices}
            new_macs = current_macs - self.state_manager.known_devices

            for mac in new_macs:
                device_info = next(
                    (dev for dev in current_devices if dev["mac"].lower() == mac), None
                )

                if device_info:
                    detected_at = time.time()
                    should_notify, is_unknown_device = (
                        self.notification_handler.should_notify_device(mac)
                    )

                    if should_notify:
                        if is_unknown_device:
                            logging.info("未知の端末を初回検出しました: %s", mac)
                            sent = self.notification_handler.send_notifications(
                                dict(device_info),
                                is_unknown_device=True,
                                detected_at=detected_at,
                            )
                            if sent:
                                self.state_manager.unknown_notified_macs.add(mac)
                                self.state_manager.mark_device_notified(mac, detected_at)
                        else:
                            disconnected_since = self.state_manager.disconnected_at.get(mac)
                            (
                                force_notify_by_reconnect,
                                absence_seconds,
                            ) = self.notification_handler.should_force_notify_by_reconnect(mac)

                            cooldown_remaining = (
                                self.notification_handler.get_notification_cooldown_remaining(mac)
                            )
                            if cooldown_remaining > 0 and not force_notify_by_reconnect:
                                logging.info(
                                    "同一端末の再通知を抑止しました: %s（クールダウン残り約%s秒）",
                                    mac,
                                    cooldown_remaining,
                                )
                            else:
                                if force_notify_by_reconnect:
                                    logging.info(
                                        "%s分ぶりの再接続を検出しました（強制通知）: %s",
                                        int(absence_seconds // 60),
                                        mac,
                                    )
                                else:
                                    logging.info(f"新しいデバイスを検出しました: {mac}")
                                notification_device_info = dict(device_info)
                                if disconnected_since is not None:
                                    notification_device_info["_notification_type"] = (
                                        "repeat_known_device"
                                    )
                                if (
                                    self.notification_handler.branch_notification_mode_enabled
                                    and mac in self.repeat_notification_macs
                                ):
                                    notification_device_info["_notification_type"] = (
                                        "repeat_known_device"
                                    )
                                sent = self.notification_handler.send_notifications(
                                    notification_device_info,
                                    detected_at=detected_at,
                                )
                                if sent:
                                    self.state_manager.mark_device_notified(mac, detected_at)
                    else:
                        if (
                            self.notification_handler.branch_notification_mode_enabled
                            and mac in self.state_manager.unknown_notified_macs
                        ):
                            logging.debug(
                                "未知端末は既に初回通知済みのため通知しません: %s",
                                mac,
                            )
                        else:
                            logging.debug(f"新しいデバイスを検出しましたが、監視対象外です: {mac}")

                    self.state_manager.add_known_device(mac)
                    self.state_manager.clear_missing_count(mac)
                    self.state_manager.disconnected_at.pop(mac, None)

            for mac in current_macs:
                if mac in self.state_manager.known_devices:
                    self.state_manager.clear_missing_count(mac)

            disconnected_candidates = self.state_manager.known_devices - current_macs
            disconnected: Set[str] = set()
            for mac in disconnected_candidates:
                miss_count = self.state_manager.increment_missing_count(mac)
                if miss_count >= self.disconnect_grace_scans:
                    disconnected.add(mac)

            if disconnected:
                logging.info(
                    f"切断されたデバイス数: {len(disconnected)}"
                    f"（連続{self.disconnect_grace_scans}回見失いで判定）"
                )
                for mac in disconnected:
                    self.state_manager.remove_known_device(mac)
                    self.state_manager.mark_device_disconnected(mac, time.time())

        except Exception as e:
            logging.error("新しいデバイスのチェック中にエラーが発生しました: %s", e)


def main():
    """メインエントリーポイント。"""
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
