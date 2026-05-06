"""
Googleカレンダー通知処理モジュール

Googleカレンダーへの予定登録通知を行う機能を提供します。
"""

import time
import logging
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    service_account = None
    build = None
    HttpError = None

from .base import BaseNotifier


class GoogleCalendarNotifier(BaseNotifier):
    """Googleカレンダーへの予定登録通知を処理する。"""

    SCOPE = "https://www.googleapis.com/auth/calendar.events"

    def __init__(
        self,
        credentials_file: str,
        calendar_id: str,
        timezone_name: str = "Asia/Tokyo",
        summary_prefix: str = "🛜",
        max_retries: int = 3,
        retry_delay_seconds: int = 3,
        dedupe_window_minutes: int = 10,
    ):
        """
        Googleカレンダー通知機能を初期化する。

        Args:
            credentials_file: サービスアカウントJSONのパス
            calendar_id: 登録先カレンダーID
            timezone_name: 予定登録に使用するタイムゾーン
            summary_prefix: 予定タイトルの先頭文字列
            max_retries: 登録失敗時の最大リトライ回数
            retry_delay_seconds: リトライ間隔（秒）
            dedupe_window_minutes: 重複確認時に検索する時間幅（分）
        """
        if service_account is None or build is None:
            raise ImportError(
                "Googleカレンダー機能を使うには google-auth と "
                "google-api-python-client のインストールが必要です"
            )

        self.credentials_file = credentials_file
        self.calendar_id = calendar_id
        self.summary_prefix = summary_prefix.strip() if summary_prefix else "🛜"
        self.max_retries = max(1, int(max_retries))
        self.retry_delay_seconds = max(1, int(retry_delay_seconds))
        self.dedupe_window_minutes = max(1, int(dedupe_window_minutes))

        try:
            self.timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            logging.warning(
                "Googleカレンダー設定の timezone が不正のため UTC を使用します: %s",
                timezone_name,
            )
            self.timezone = ZoneInfo("UTC")

        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=[self.SCOPE],
        )
        self.service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        self.service_account_email = getattr(credentials, "service_account_email", "")
        self._validate_calendar_access()

    def _validate_calendar_access(self) -> None:
        """初期化時に対象カレンダーへのアクセス可否を検証する。

        calendar.events スコープで利用可能な events.list を使って
        アクセス権を確認する（calendars.get は calendar.readonly 以上が必要なため使用しない）。
        """
        try:
            self.service.events().list(
                calendarId=self.calendar_id,
                maxResults=1,
            ).execute()
        except Exception as e:
            if HttpError is not None and isinstance(e, HttpError):
                status = getattr(e.resp, "status", None)
                if status in (403, 404):
                    account_hint = (
                        self.service_account_email
                        if self.service_account_email
                        else "サービスアカウント"
                    )
                    raise ValueError(
                        "Googleカレンダーへアクセスできません。"
                        f" calendar_id='{self.calendar_id}' を確認し、"
                        f"{account_hint} に対象カレンダーの共有権限を付与してください"
                    ) from e
            raise

    def send_notification(
        self,
        device_info: Dict[str, str],
        is_unknown_device: bool = False,
        detected_at: Optional[float] = None,
    ) -> bool:
        """検出デバイス情報をGoogleカレンダー予定として登録する。"""
        detected_ts = detected_at if detected_at is not None else time.time()
        started_at = datetime.fromtimestamp(detected_ts, tz=self.timezone)
        ended_at = started_at

        dedupe_key = self._build_dedupe_key(device_info, is_unknown_device, detected_ts)
        if self._event_already_exists(dedupe_key, started_at):
            logging.info("Googleカレンダー登録をスキップ（重複検知）: %s", dedupe_key)
            return True

        event = {
            "summary": self._build_summary(device_info, is_unknown_device),
            "description": self._build_description(device_info, is_unknown_device, started_at),
            "start": {
                "dateTime": started_at.isoformat(),
                "timeZone": str(self.timezone),
            },
            "end": {
                "dateTime": ended_at.isoformat(),
                "timeZone": str(self.timezone),
            },
            "extendedProperties": {
                "private": {
                    "wifi_notifier_key": dedupe_key,
                }
            },
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
                logging.info("Googleカレンダーへ予定登録しました: %s", dedupe_key)
                return True
            except Exception as e:
                if self._is_conflict_error(e):
                    logging.info("Googleカレンダー登録は既存イベントと競合したため成功扱いにします")
                    return True

                if attempt >= self.max_retries:
                    logging.error("Googleカレンダー登録に失敗しました（リトライ上限）: %s", e)
                    return False

                logging.warning(
                    "Googleカレンダー登録に失敗したためリトライします " "(%s/%s): %s",
                    attempt,
                    self.max_retries,
                    e,
                )
                time.sleep(self.retry_delay_seconds)

        return False

    def _event_already_exists(self, dedupe_key: str, started_at: datetime) -> bool:
        """同一重複キーを持つ予定が既にあるか確認する。"""
        time_min = datetime.fromtimestamp(
            started_at.timestamp() - (self.dedupe_window_minutes * 60),
            tz=self.timezone,
        ).isoformat()
        time_max = datetime.fromtimestamp(
            started_at.timestamp() + (self.dedupe_window_minutes * 60),
            tz=self.timezone,
        ).isoformat()

        try:
            result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    maxResults=5,
                    privateExtendedProperty=[f"wifi_notifier_key={dedupe_key}"],
                )
                .execute()
            )
            items = result.get("items", [])
            return bool(items)
        except Exception as e:
            logging.warning("重複確認に失敗したため登録を継続します: %s", e)
            return False

    @staticmethod
    def _is_conflict_error(error: Exception) -> bool:
        """API競合エラー（409）を重複として判定する。"""
        if HttpError is not None and isinstance(error, HttpError):
            return getattr(error.resp, "status", None) == 409
        return "409" in str(error)

    def _build_summary(self, device_info: Dict[str, str], is_unknown_device: bool) -> str:
        """予定タイトルを生成する。"""
        mac = device_info.get("mac", "Unknown")
        hostname = device_info.get("hostname", "Unknown")
        unknown_prefix = "未知端末 " if is_unknown_device else ""
        return f"{self.summary_prefix}: {unknown_prefix}{hostname} ({mac})"

    @staticmethod
    def _build_description(
        device_info: Dict[str, str],
        is_unknown_device: bool,
        started_at: datetime,
    ) -> str:
        """予定説明を生成する。"""
        raw_notification_type = str(device_info.get("_notification_type", "")).strip()
        if is_unknown_device:
            notification_type = "未知の端末（初回のみ通知）"
        elif raw_notification_type == "repeat_known_device":
            notification_type = "既知端末の再接続"
        else:
            notification_type = "新規WiFi接続"

        vendor = str(device_info.get("vendor", "")).strip()
        vendor_line = f"メーカー: {vendor}\n" if vendor else ""

        return (
            "WiFi接続通知\n\n"
            f"通知種別: {notification_type}\n"
            f"検出時刻: {started_at.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"MACアドレス: {device_info.get('mac', 'Unknown')}\n"
            f"IPアドレス: {device_info.get('ip', 'Unknown')}\n"
            f"ホスト名: {device_info.get('hostname', 'Unknown')}\n"
            f"{vendor_line}"
        )

    @staticmethod
    def _build_dedupe_key(
        device_info: Dict[str, str],
        is_unknown_device: bool,
        detected_ts: float,
    ) -> str:
        """1分単位で重複判定するためのキーを生成する。"""
        bucket_minute = int(detected_ts // 60)
        mac = device_info.get("mac", "unknown").lower()
        event_type = "unknown" if is_unknown_device else "known"
        return f"{event_type}:{mac}:{bucket_minute}"
