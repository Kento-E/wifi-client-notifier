"""
Firebase Cloud Messaging 通知処理モジュール

FCM HTTP v1 API を利用して Android 端末へプッシュ通知を送信する。
"""

import json
import logging
import time
from datetime import UTC, datetime

import requests

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
except ImportError:
    Request = None
    service_account = None

from .base import BaseNotifier


class FirebaseNotifier(BaseNotifier):
    """Firebase Cloud Messaging による通知を処理する。"""

    SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
    FIRESTORE_SCOPE = "https://www.googleapis.com/auth/datastore"
    # この秒数を超えてハートビートが成功しなかった場合を「途切れた」とみなす
    HEARTBEAT_GAP_SECONDS = 300

    def __init__(
        self,
        project_id: str,
        credentials_file: str,
        registration_tokens: list[str],
        notification_title_prefix: str = "🛜",
        timeout_seconds: int = 10,
    ):
        """Firebase 通知機能を初期化する。"""
        if service_account is None or Request is None:
            raise ImportError("Firebase通知を使うには google-auth のインストールが必要です")

        normalized_tokens = [token.strip() for token in registration_tokens if token.strip()]
        if not normalized_tokens:
            raise ValueError("Firebase通知先 registration_tokens が空です")

        self.project_id = project_id.strip()
        self.credentials_file = credentials_file
        self.registration_tokens = normalized_tokens
        self.notification_title_prefix = (
            notification_title_prefix.strip() if notification_title_prefix else "🛜"
        )
        self.timeout_seconds = max(1, int(timeout_seconds))
        self._last_heartbeat_ok_at: float | None = None
        self._online_since: str | None = None
        self._credentials = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=[self.SCOPE, self.FIRESTORE_SCOPE],
        )

    def send_notification(
        self,
        device_info: dict[str, str],
        is_unknown_device: bool = False,
        detected_at: float | None = None,
    ) -> bool:
        """対象端末へプッシュ通知を送信する。"""
        title = self._build_title(device_info, is_unknown_device)
        body = self._build_body(device_info, is_unknown_device, detected_at)
        data = self._build_data_payload(device_info, is_unknown_device, detected_at)
        return self.send_message(title, body, data)

    def send_message(self, title: str, body: str, data: dict[str, str] | None = None) -> bool:
        """任意のタイトル・本文で全登録端末へプッシュ通知を送信する。"""
        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        data = data or {}
        endpoint = f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"

        success_count = 0
        for token in self.registration_tokens:
            payload = {
                "message": {
                    "token": token,
                    "notification": {
                        "title": title,
                        "body": body,
                    },
                    "data": data,
                    "android": {
                        "priority": "high",
                    },
                }
            }

            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if response.ok:
                    success_count += 1
                    continue

                logging.error(
                    "Firebase通知の送信に失敗しました: status=%s body=%s",
                    response.status_code,
                    response.text,
                )
            except Exception as e:
                logging.error("Firebase通知の送信中に例外が発生しました: %s", e)

        if success_count == len(self.registration_tokens):
            logging.info("Firebase通知を送信しました: %s件", success_count)
            return True

        if success_count > 0:
            logging.warning(
                "Firebase通知の一部が失敗しました（成功: %s / 全体: %s）",
                success_count,
                len(self.registration_tokens),
            )
            return True

        return False

    def send_heartbeat(self, host: str) -> bool:
        """Firestore の heartbeats/<host> に last_seen（現在時刻）を書き込む。

        送信が途切れた後の最初の成功時刻を online_since として併せて記録する。
        途絶からの復帰時刻を、監視側の確認タイミングに依存せず特定するために使う。
        """
        url = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{self.project_id}/databases/(default)/documents/heartbeats/{host}"
        )
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        gap_detected = (
            self._last_heartbeat_ok_at is None
            or time.monotonic() - self._last_heartbeat_ok_at > self.HEARTBEAT_GAP_SECONDS
        )
        online_since = now if gap_detected else self._online_since
        fields = {"last_seen": {"timestampValue": now}}
        if online_since is not None:
            fields["online_since"] = {"timestampValue": online_since}
        try:
            response = requests.patch(
                url,
                params={"updateMask.fieldPaths": list(fields)},
                headers={"Authorization": f"Bearer {self._get_access_token()}"},
                json={"fields": fields},
                timeout=self.timeout_seconds,
            )
            if response.ok:
                self._last_heartbeat_ok_at = time.monotonic()
                self._online_since = online_since
                return True
            logging.error(
                "ハートビートの送信に失敗しました: status=%s body=%s",
                response.status_code,
                response.text,
            )
        except Exception as e:
            logging.error("ハートビートの送信中に例外が発生しました: %s", e)
        return False

    def _get_access_token(self) -> str:
        """Google 認証情報からアクセストークンを取得する。"""
        credentials = self._credentials
        if not credentials.valid:
            credentials.refresh(Request())

        if not credentials.token:
            raise ValueError("Firebase通知用のアクセストークン取得に失敗しました")

        return credentials.token

    def _build_title(self, device_info: dict[str, str], is_unknown_device: bool) -> str:
        """通知タイトルを組み立てる。"""
        if is_unknown_device:
            event_label = "未知端末を検出"
        elif str(device_info.get("_notification_type", "")).strip() == "repeat_known_device":
            event_label = "既知端末の再接続"
        else:
            event_label = "新しいWiFi接続"

        device_label = (
            FirebaseNotifier._real_hostname(device_info)
            or str(device_info.get("vendor", "")).strip()
            or str(device_info.get("mac", "Unknown"))
        )
        return f"{self.notification_title_prefix}: {event_label} - {device_label}"

    @staticmethod
    def _real_hostname(device_info: dict[str, str]) -> str:
        """IPの逆引きに失敗した際のIPフォールバック値を除いたホスト名を返す。"""
        hostname = str(device_info.get("hostname", "")).strip()
        if hostname == str(device_info.get("ip", "")).strip():
            return ""
        return hostname

    @staticmethod
    def _build_body(
        device_info: dict[str, str],
        is_unknown_device: bool,
        detected_at: float | None,
    ) -> str:
        """通知本文を組み立てる。"""
        detected_at_text = "Unknown"
        if detected_at is not None:
            detected_at_text = datetime.fromtimestamp(detected_at).strftime("%Y-%m-%d %H:%M:%S")

        if is_unknown_device:
            event_label = "未知端末"
        elif str(device_info.get("_notification_type", "")).strip() == "repeat_known_device":
            event_label = "既知端末の再接続"
        else:
            event_label = "新規接続"

        hostname = FirebaseNotifier._real_hostname(device_info)
        mac = device_info.get("mac", "Unknown")
        ip_address = device_info.get("ip", "Unknown")
        parts = [hostname, mac, ip_address, detected_at_text]
        return f"{event_label}: " + " / ".join(p for p in parts if p)

    @staticmethod
    def _build_data_payload(
        device_info: dict[str, str],
        is_unknown_device: bool,
        detected_at: float | None,
    ) -> dict[str, str]:
        """アプリ側で参照できる data ペイロードを組み立てる。"""
        payload = {
            "mac": str(device_info.get("mac", "")),
            "ip": str(device_info.get("ip", "")),
            "hostname": str(device_info.get("hostname", "")),
            "vendor": str(device_info.get("vendor", "")),
            "notification_type": str(device_info.get("_notification_type", "new_device")),
            "is_unknown_device": "true" if is_unknown_device else "false",
        }
        if detected_at is not None:
            payload["detected_at"] = str(int(detected_at))

        channel_errors = device_info.get("_channel_errors")
        if isinstance(channel_errors, list) and channel_errors:
            payload["channel_errors"] = json.dumps(channel_errors, ensure_ascii=False)

        return payload
