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
import tempfile
import yaml
import logging
import sys
import json
from typing import Dict, List, Optional, Set

try:
    from src.constants import DEFAULT_STATE_FILE
    from src.router import WiFiRouter
    from src.notifiers import EmailNotifier, GoogleCalendarNotifier
except ModuleNotFoundError:
    from constants import DEFAULT_STATE_FILE
    from router import WiFiRouter
    from notifiers import EmailNotifier, GoogleCalendarNotifier


class WiFiMonitor:
    """WiFi接続を監視して通知を送信する。"""

    def __init__(self, config_path: str):
        """
        設定ファイルを使用して監視機能を初期化する。

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self.config_dir = os.path.dirname(os.path.abspath(config_path))
        self._setup_logging()
        self.router: Optional[WiFiRouter] = None
        self.arp_scanner = None
        self.notifiers: List[object] = []
        self.known_devices: Set[str] = set()
        self.monitored_macs: Set[str] = set()
        self.repeat_notification_macs: Set[str] = set()
        self.unknown_notified_macs: Set[str] = set()
        self.missing_counts: Dict[str, int] = {}
        self.last_notified_at: Dict[str, float] = {}
        self.disconnected_at: Dict[str, float] = {}
        self.disconnect_grace_scans: int = 3
        self.notification_cooldown_seconds: int = 0
        self.reconnect_notify_after_seconds: int = 3600
        self.notify_unknown_devices_once: bool = False
        self.branch_notification_mode_enabled: bool = False
        self.calendar_init_error: Optional[str] = None
        configured_state_file = str(self.config.get("state_file", "")).strip()
        if configured_state_file:
            expanded_state_file = os.path.expanduser(configured_state_file)
            if os.path.isabs(expanded_state_file):
                self.state_file = expanded_state_file
            else:
                self.state_file = os.path.join(self.config_dir, expanded_state_file)
        else:
            self.state_file = os.path.join(self.config_dir, DEFAULT_STATE_FILE)
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
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            raise

    def _setup_logging(self):
        """ロギング設定をセットアップする。"""
        log_level = self.config.get("log_level", "INFO")
        log_file = self.config.get("log_file", "wifi_notifier.log")
        logging.root.handlers = []
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
            force=True,
        )

    @staticmethod
    def _parse_bool_config(value, default: bool = False) -> bool:
        """真偽値設定を安全に解釈する。"""
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

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
            router_config = self.config.get("router")
            if not router_config:
                raise ValueError(
                    "detection_method が 'router' の場合は 'router' セクションの設定が必要です。"
                )
            self.router = WiFiRouter(
                router_config["ip"], router_config["username"], router_config["password"]
            )
            logging.info("検出方式: ルータAPI")

        email_config = self.config["email"]
        email_notifier = EmailNotifier(
            email_config["smtp_server"],
            email_config["smtp_port"],
            email_config["smtp_user"],
            email_config["smtp_password"],
            email_config["sender_email"],
            email_config["recipient_emails"],
            email_config.get("use_tls", True),
        )
        self.notifiers = [email_notifier]

        calendar_config = self.config.get("google_calendar", {})
        if not isinstance(calendar_config, dict):
            calendar_config = {}

        calendar_enabled = self._parse_bool_config(calendar_config.get("enabled"), default=False)
        if calendar_enabled:
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
                    raise ValueError("環境変数が未設定または空です: " f"{credentials_file_env}")
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
                    event_duration_minutes=calendar_config.get("event_duration_minutes", 30),
                    summary_prefix=calendar_config.get("summary_prefix", "WiFi接続検知"),
                    max_retries=calendar_config.get("max_retries", 3),
                    retry_delay_seconds=calendar_config.get("retry_delay_seconds", 3),
                    dedupe_window_minutes=calendar_config.get("dedupe_window_minutes", 10),
                )
                self.notifiers.append(calendar_notifier)
                logging.info("Googleカレンダー通知: 有効（カレンダーID: %s）", calendar_id)
            except Exception as e:
                self.calendar_init_error = str(e)
                logging.error(
                    "Googleカレンダー通知の初期化に失敗したためメール通知のみ継続します: %s",
                    e,
                )
        else:
            logging.info("Googleカレンダー通知: 無効")

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
        self.notify_unknown_devices_once = self._parse_bool_config(
            self.config.get("notify_unknown_devices_once"),
            default=False,
        )
        self.branch_notification_mode_enabled = bool(self.repeat_notification_macs) or (
            "notify_unknown_devices_once" in self.config
        )
        if self.branch_notification_mode_enabled:
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

        raw_grace_scans = self.config.get("disconnect_grace_scans", 3)
        try:
            self.disconnect_grace_scans = max(1, int(raw_grace_scans))
        except (TypeError, ValueError):
            self.disconnect_grace_scans = 3
            logging.warning(
                "disconnect_grace_scans の値が不正のため 3 を使用します: %s",
                raw_grace_scans,
            )
        logging.info(
            f"切断判定の猶予回数: {self.disconnect_grace_scans}回（連続で見失った場合に切断扱い）"
        )

        raw_cooldown_minutes = self.config.get(
            "notification_cool_down_minutes",
            self.config.get("notification_cooldown_minutes", 0),
        )
        try:
            self.notification_cooldown_seconds = max(0, int(raw_cooldown_minutes) * 60)
        except (TypeError, ValueError):
            self.notification_cooldown_seconds = 0
            logging.warning(
                "notification_cool_down_minutes の値が不正のため 0 を使用します: %s",
                raw_cooldown_minutes,
            )
        if self.notification_cooldown_seconds > 0:
            logging.info(
                "通知クールダウン: %s分（同一MACの再通知を抑止）",
                self.notification_cooldown_seconds // 60,
            )
        else:
            logging.info("通知クールダウン: 無効")

        raw_reconnect_minutes = self.config.get("reconnect_notify_after_minutes", 60)
        try:
            self.reconnect_notify_after_seconds = max(0, int(raw_reconnect_minutes) * 60)
        except (TypeError, ValueError):
            self.reconnect_notify_after_seconds = 3600
            logging.warning(
                "reconnect_notify_after_minutes の値が不正のため 60 を使用します: %s",
                raw_reconnect_minutes,
            )
        if self.reconnect_notify_after_seconds > 0:
            logging.info(
                "再接続通知閾値: %s分（この時間以上の不在後の再接続はクールダウンを無視して通知）",
                self.reconnect_notify_after_seconds // 60,
            )
        else:
            logging.info("再接続通知閾値: 無効（0分）")

        logging.info("コンポーネントの初期化が完了しました")

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

        self._load_state()
        if not self.state_loaded:
            initial_devices = self._get_current_devices()
            self.known_devices = {dev["mac"].lower() for dev in initial_devices}
            self.missing_counts = {mac: 0 for mac in self.known_devices}
            if self.notify_unknown_devices_once:
                baseline_unknown_devices = {
                    mac for mac in self.known_devices if mac not in self.repeat_notification_macs
                }
                self.unknown_notified_macs.update(baseline_unknown_devices)
            logging.info(
                "初回実行のため現在接続中デバイスをベースライン登録します: %s台",
                len(self.known_devices),
            )

        if single_run:
            logging.info("シングルランモード: 1回チェックして終了します")
            self._check_for_new_devices()
            self._save_state()
            logging.info("シングルランが完了しました")
            return

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
        """状態ファイルから既知デバイス情報を読み込む。"""
        if not os.path.exists(self.state_file):
            self.state_loaded = False
            self.known_devices = set()
            self.unknown_notified_macs = set()
            self.missing_counts = {}
            self.last_notified_at = {}
            self.disconnected_at = {}
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

            unknown_notified_list = state.get("unknown_notified_macs", [])
            if not isinstance(unknown_notified_list, list):
                raise ValueError("unknown_notified_macs は配列である必要があります")
            self.unknown_notified_macs = {
                mac.strip().lower()
                for mac in unknown_notified_list
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

            raw_disconnected_at = state.get("disconnected_at", {})
            self.disconnected_at = {}
            if isinstance(raw_disconnected_at, dict):
                for mac, timestamp in raw_disconnected_at.items():
                    if not isinstance(mac, str):
                        continue
                    try:
                        parsed_timestamp = float(timestamp)
                        if parsed_timestamp < 0:
                            continue
                        self.disconnected_at[mac.lower()] = parsed_timestamp
                    except (TypeError, ValueError):
                        continue

            self.state_loaded = True
            logging.info(
                f"状態ファイルを読み込みました: known={len(self.known_devices)} "
                f"({self.state_file})"
            )
            return True

        except Exception as e:
            logging.warning(f"状態ファイルの読み込みに失敗したため空状態で開始します: {e}")
            self.state_loaded = False
            self.known_devices = set()
            self.unknown_notified_macs = set()
            self.missing_counts = {}
            self.last_notified_at = {}
            self.disconnected_at = {}
            return False

    def _save_state(self):
        """既知デバイス情報を状態ファイルに保存する。"""
        tmp_path = None
        try:
            state = {
                "known_devices": sorted(self.known_devices),
                "unknown_notified_macs": sorted(self.unknown_notified_macs),
                "missing_counts": {
                    mac: self.missing_counts.get(mac, 0) for mac in self.known_devices
                },
                "last_notified_at": {
                    mac: self.last_notified_at[mac] for mac in sorted(self.last_notified_at)
                },
                "disconnected_at": {
                    mac: self.disconnected_at[mac] for mac in sorted(self.disconnected_at)
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
            new_macs = current_macs - self.known_devices

            for mac in new_macs:
                device_info = next(
                    (dev for dev in current_devices if dev["mac"].lower() == mac), None
                )

                if device_info:
                    detected_at = time.time()
                    should_notify, is_unknown_device = self._should_notify_device(mac)

                    if should_notify:
                        if is_unknown_device:
                            logging.info("未知の端末を初回検出しました: %s", mac)
                            notification_device_info = dict(device_info)
                            sent = self._send_notifications(
                                notification_device_info,
                                is_unknown_device=True,
                                detected_at=detected_at,
                            )
                            if sent:
                                self.unknown_notified_macs.add(mac)
                                self.last_notified_at[mac] = detected_at
                        else:
                            disconnected_since = self.disconnected_at.get(mac)
                            absence_seconds = (
                                time.time() - disconnected_since
                                if disconnected_since is not None
                                else None
                            )
                            force_notify_by_reconnect = (
                                self.reconnect_notify_after_seconds > 0
                                and absence_seconds is not None
                                and absence_seconds >= self.reconnect_notify_after_seconds
                            )

                            cooldown_remaining = self._get_notification_cooldown_remaining(mac)
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
                                    self.branch_notification_mode_enabled
                                    and mac in self.repeat_notification_macs
                                ):
                                    notification_device_info["_notification_type"] = (
                                        "repeat_known_device"
                                    )
                                sent = self._send_notifications(
                                    notification_device_info,
                                    detected_at=detected_at,
                                )
                                if sent:
                                    self.last_notified_at[mac] = detected_at
                    else:
                        if (
                            self.branch_notification_mode_enabled
                            and mac in self.unknown_notified_macs
                        ):
                            logging.debug(
                                "未知端末は既に初回通知済みのため通知しません: %s",
                                mac,
                            )
                        else:
                            logging.debug(f"新しいデバイスを検出しましたが、監視対象外です: {mac}")

                    self.known_devices.add(mac)
                    self.missing_counts[mac] = 0
                    self.disconnected_at.pop(mac, None)

            for mac in current_macs:
                if mac in self.known_devices:
                    self.missing_counts[mac] = 0

            disconnected_candidates = self.known_devices - current_macs
            disconnected: Set[str] = set()
            for mac in disconnected_candidates:
                miss_count = self.missing_counts.get(mac, 0) + 1
                self.missing_counts[mac] = miss_count
                if miss_count >= self.disconnect_grace_scans:
                    disconnected.add(mac)

            if disconnected:
                logging.info(
                    f"切断されたデバイス数: {len(disconnected)}"
                    f"（連続{self.disconnect_grace_scans}回見失いで判定）"
                )
                for mac in disconnected:
                    self.known_devices.discard(mac)
                    self.missing_counts.pop(mac, None)
                    self.disconnected_at[mac] = time.time()

        except Exception as e:
            logging.error(f"新しいデバイスのチェック中にエラーが発生しました: {e}")

    def _send_notifications(
        self,
        device_info: Dict[str, str],
        is_unknown_device: bool = False,
        detected_at: Optional[float] = None,
    ) -> bool:
        """有効な通知チャネルへ順番に通知し、1つでも成功したらTrueを返す。"""
        if not self.notifiers:
            logging.error("通知チャネルが設定されていません")
            return False

        notification_payload = dict(device_info)
        channel_errors: List[str] = []
        if self.calendar_init_error:
            channel_errors.append(f"Googleカレンダー通知の初期化に失敗: {self.calendar_init_error}")

        email_notifiers = [n for n in self.notifiers if isinstance(n, EmailNotifier)]
        other_notifiers = [n for n in self.notifiers if not isinstance(n, EmailNotifier)]

        success_count = 0
        for notifier in other_notifiers:
            notifier_name = notifier.__class__.__name__
            try:
                sent = notifier.send_notification(
                    notification_payload,
                    is_unknown_device=is_unknown_device,
                    detected_at=detected_at,
                )
                if sent:
                    success_count += 1
                else:
                    logging.warning("通知チャネルの送信に失敗しました: %s", notifier_name)
                    channel_errors.append(
                        f"{notifier_name} の送信に失敗しました（詳細はログを確認）"
                    )
            except Exception as e:
                logging.error("通知チャネル処理で例外が発生しました: %s (%s)", notifier_name, e)
                channel_errors.append(f"{notifier_name} で例外が発生: {e}")

        if channel_errors:
            notification_payload["_channel_errors"] = channel_errors

        for notifier in email_notifiers:
            notifier_name = notifier.__class__.__name__
            try:
                sent = notifier.send_notification(
                    notification_payload,
                    is_unknown_device=is_unknown_device,
                    detected_at=detected_at,
                )
                if sent:
                    success_count += 1
                else:
                    logging.warning("通知チャネルの送信に失敗しました: %s", notifier_name)
            except Exception as e:
                logging.error("通知チャネル処理で例外が発生しました: %s (%s)", notifier_name, e)

        if success_count == len(self.notifiers):
            return True

        if success_count > 0:
            logging.warning(
                "一部の通知チャネルで失敗しました（成功: %s / 全体: %s）",
                success_count,
                len(self.notifiers),
            )
            return True

        return False

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

    def _should_notify_device(self, mac: str) -> tuple[bool, bool]:
        """対象MACを通知すべきかと未知端末通知かどうかを返す。"""
        if self.branch_notification_mode_enabled:
            if mac in self.repeat_notification_macs:
                return True, False
            if self.notify_unknown_devices_once and mac not in self.unknown_notified_macs:
                return True, True
            return False, False

        should_notify = not self.monitored_macs or mac in self.monitored_macs
        return should_notify, False


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
