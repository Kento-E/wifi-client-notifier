#!/usr/bin/env python3
"""
WiFi通知ツール通知制御モジュール

通知の判定（クールダウン、再接続閾値）と送信を担当する。
"""

import time
import logging
from typing import Dict, List, Optional, Tuple

try:
    from src.state_manager import StateManager
except ModuleNotFoundError:
    from state_manager import StateManager


class NotificationHandler:
    """通知の判定と送信を行う。"""

    def __init__(
        self,
        state_manager: StateManager,
        notifiers: List[object],
        notification_cooldown_seconds: int = 0,
        reconnect_notify_after_seconds: int = 3600,
        monitored_macs: Optional[set] = None,
        repeat_notification_macs: Optional[set] = None,
        notify_unknown_devices_once: bool = False,
    ):
        """初期化。

        Args:
            state_manager: 状態管理インスタンス
            notifiers: 通知チャネル（EmailNotifier等）のリスト
            notification_cooldown_seconds: 同一MAC への再通知クールダウン（秒）
            reconnect_notify_after_seconds: 再接続通知の閾値（秒）
            monitored_macs: 監視対象MAC（None=全て、空集合=なし）
            repeat_notification_macs: 再通知対象MAC
            notify_unknown_devices_once: 未知端末の初回通知のみ有効化
        """
        self.state_manager = state_manager
        self.notifiers = notifiers or []
        self.notification_cooldown_seconds = notification_cooldown_seconds
        self.reconnect_notify_after_seconds = reconnect_notify_after_seconds
        self.monitored_macs = monitored_macs or set()
        self.repeat_notification_macs = repeat_notification_macs or set()
        self.notify_unknown_devices_once = notify_unknown_devices_once
        # 分岐モードは repeat_notification_macs または notify_unknown_devices_once
        self.branch_notification_mode_enabled = (
            bool(self.repeat_notification_macs) or notify_unknown_devices_once
        )
        self.calendar_init_error: Optional[str] = None

    def should_notify_device(self, mac: str) -> Tuple[bool, bool]:
        """対象MACを通知すべきか、未知端末通知かどうかを判定する。

        Args:
            mac: デバイスのMACアドレス

        Returns:
            (通知すべき, 未知端末フラグ) のタプル
        """
        if self.branch_notification_mode_enabled:
            if mac in self.repeat_notification_macs:
                return True, False
            if (
                self.notify_unknown_devices_once
                and mac not in self.state_manager.unknown_notified_macs
            ):
                return True, True
            return False, False

        should_notify = not self.monitored_macs or mac in self.monitored_macs
        return should_notify, False

    def get_notification_cooldown_remaining(self, mac: str) -> int:
        """同一MACへの再通知クールダウン残秒数を返す。

        Args:
            mac: デバイスのMACアドレス

        Returns:
            クールダウン残秒数（0以上）
        """
        if self.notification_cooldown_seconds <= 0:
            return 0

        last_sent = self.state_manager.last_notified_at.get(mac.lower())
        if last_sent is None:
            return 0

        elapsed = int(time.time() - last_sent)
        remaining = self.notification_cooldown_seconds - elapsed
        return max(0, remaining)

    def should_force_notify_by_reconnect(self, mac: str) -> Tuple[bool, Optional[float]]:
        """再接続により通知をスキップすべきクールダウンを無視すべきか判定する。

        Args:
            mac: デバイスのMACアドレス

        Returns:
            (スキップすべき, 不在秒数) のタプル
        """
        if self.reconnect_notify_after_seconds <= 0:
            return False, None

        disconnected_since = self.state_manager.disconnected_at.get(mac.lower())
        if disconnected_since is None:
            return False, None

        absence_seconds = time.time() - disconnected_since
        should_force = absence_seconds >= self.reconnect_notify_after_seconds
        return should_force, absence_seconds if should_force else None

    def send_notifications(
        self,
        device_info: Dict[str, str],
        is_unknown_device: bool = False,
        detected_at: Optional[float] = None,
    ) -> bool:
        """有効な通知チャネルへ順番に通知する。

        1つ以上の通知チャネルが成功した場合はTrueを返す。

        Args:
            device_info: デバイス情報辞書
            is_unknown_device: 未知端末フラグ
            detected_at: 検出時刻（Unix時刻）

        Returns:
            通知成功時はTrue、全失敗時はFalse
        """
        if not self.notifiers:
            logging.error("通知チャネルが設定されていません")
            return False

        try:
            from src.notifiers import EmailNotifier
        except ModuleNotFoundError:
            from notifiers import EmailNotifier

        notification_payload = dict(device_info)
        channel_errors: List[str] = []

        if self.calendar_init_error:
            channel_errors.append(f"Googleカレンダー通知の初期化に失敗: {self.calendar_init_error}")

        # 非メール通知を先に送信
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

        # エラー情報をメール本文に含める
        if channel_errors:
            notification_payload["_channel_errors"] = channel_errors

        # メール通知を最後に送信
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

    def init_baseline_unknown_devices(self, current_macs: set) -> None:
        """初回実行時のベースライン（既知の未知デバイス）を設定する。

        Args:
            current_macs: 現在接続中のMAC集合
        """
        if self.notify_unknown_devices_once:
            baseline_unknown_devices = {
                mac for mac in current_macs if mac not in self.repeat_notification_macs
            }
            self.state_manager.unknown_notified_macs.update(baseline_unknown_devices)
