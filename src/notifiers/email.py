"""
メール通知処理モジュール

SMTP経由でメール通知を送信する機能を提供します。
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional

from .base import BaseNotifier


class EmailNotifier(BaseNotifier):
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

    def send_notification(
        self,
        device_info: Dict[str, str],
        is_unknown_device: bool = False,
        detected_at: Optional[float] = None,
    ) -> bool:
        """
        新しいデバイス接続についてメール通知を送信する。

        Args:
            device_info: デバイス情報を含む辞書
            is_unknown_device: 未知端末の初回通知かどうか
            detected_at: 検出時刻（UNIXタイムスタンプ）

        Returns:
            メール送信成功時はTrue、失敗時はFalse
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(self.recipient_emails)
            notification_subject = "未知の端末を検出" if is_unknown_device else "新しいWiFi接続を検出"
            vendor = str(device_info.get("vendor", "")).strip()
            subject_target = vendor or device_info.get("mac", "Unknown Device")
            msg["Subject"] = f"{notification_subject} - {subject_target}"

            # メール本文を作成
            body = self._create_email_body(device_info, is_unknown_device=is_unknown_device)
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

    def _create_email_body(
        self, device_info: Dict[str, str], is_unknown_device: bool = False
    ) -> str:
        """
        メール本文テキストを作成する。

        Args:
            device_info: デバイス情報を含む辞書
            is_unknown_device: 未知端末の初回通知かどうか

        Returns:
            フォーマット済みのメール本文
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notification_type = "未知の端末（初回のみ通知）" if is_unknown_device else "新規WiFi接続"
        vendor = str(device_info.get("vendor", "")).strip()
        vendor_line = f"メーカー: {vendor}\n" if vendor else ""

        additional_lines = []
        field_labels = [
            ("dhcp_hostname", "DHCPホスト名"),
            ("mdns_name", "mDNS名"),
            ("netbios_name", "NetBIOS名"),
            ("connection_band", "接続バンド"),
            ("rssi", "RSSI"),
            ("bssid", "BSSID"),
            ("connection_time", "接続時間"),
            ("device_type", "端末種別"),
            ("os_guess", "OS推定"),
            ("fingerprint", "指紋情報"),
        ]
        for field_key, label in field_labels:
            value = str(device_info.get(field_key, "")).strip()
            if value:
                additional_lines.append(f"{label}: {value}")

        additional_info = "\n".join(additional_lines)
        if additional_info:
            additional_info = f"{additional_info}\n"

        body = f"""
WiFi接続が検出されました

通知種別: {notification_type}

検出時刻: {timestamp}
MACアドレス: {device_info.get('mac', 'Unknown')}
IPアドレス: {device_info.get('ip', 'Unknown')}
ホスト名: {device_info.get('hostname', 'Unknown')}
{vendor_line}
{additional_info}

---
WiFi Client Notifier
"""
        return body.strip()
