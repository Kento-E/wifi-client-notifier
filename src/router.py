"""
WiFiルータ通信モジュール

WiFiルータの管理APIと通信し、接続デバイス情報を取得します。
"""

import requests
import json
import logging
from typing import Dict, List

try:
    from src.html_parser import parse_wireless_lan_status, extract_devices_from_json
except ModuleNotFoundError:
    from html_parser import parse_wireless_lan_status, extract_devices_from_json


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
