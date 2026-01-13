#!/usr/bin/env python3
"""
WiFi接続通知ツール

WiFiルータのWiFi新規接続を監視し、特定のデバイスが接続された際に
メール通知を送信するスクリプトです。
"""

import requests
import time
import smtplib
import json
import yaml
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Set
from src.html_parser import parse_wireless_lan_status, extract_devices_from_json


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
    
    def __init__(self, smtp_server: str, smtp_port: int, smtp_user: str, 
                 smtp_password: str, sender_email: str, recipient_emails: List[str],
                 use_tls: bool = True):
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
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipient_emails)
            msg['Subject'] = f"新しいWiFi接続を検出 - {device_info.get('hostname', 'Unknown Device')}"
            
            # メール本文を作成
            body = self._create_email_body(device_info)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        body = f"""
新しいWiFi接続が検出されました

検出時刻: {timestamp}
MACアドレス: {device_info.get('mac', 'Unknown')}
IPアドレス: {device_info.get('ip', 'Unknown')}
ホスト名: {device_info.get('hostname', 'Unknown')}

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
        self.router = None
        self.notifier = None
        self.known_devices: Set[str] = set()
        self.monitored_macs: Set[str] = set()
        self._initialize_components()
    
    def _load_config(self, config_path: str) -> Dict:
        """設定ファイルを読み込む（YAML形式）。"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            # ロギングがまだ設定されていないためprintを使用
            print(f"Failed to load config: {e}")
            raise
    
    def _setup_logging(self):
        """ロギング設定をセットアップする。"""
        log_level = self.config.get('log_level', 'INFO')
        log_file = self.config.get('log_file', 'wifi_notifier.log')
        
        # 既存のハンドラーをクリアして最初から設定
        logging.root.handlers = []
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ],
            force=True
        )
    
    def _initialize_components(self):
        """ルータとメール通知のコンポーネントを初期化する。"""
        # ルータ接続を初期化
        router_config = self.config['router']
        self.router = WiFiRouter(
            router_config['ip'],
            router_config['username'],
            router_config['password']
        )
        
        # メール通知を初期化
        email_config = self.config['email']
        self.notifier = EmailNotifier(
            email_config['smtp_server'],
            email_config['smtp_port'],
            email_config['smtp_user'],
            email_config['smtp_password'],
            email_config['sender_email'],
            email_config['recipient_emails'],
            email_config.get('use_tls', True)
        )
        
        # 監視対象デバイスを読み込む（指定されている場合）
        monitored_devices = self.config.get('monitored_devices', [])
        self.monitored_macs = {mac.lower() for mac in monitored_devices}
        
        logging.info("Components initialized successfully")
    
    def start(self, single_run: bool = False):
        """
        WiFi接続の監視を開始する。
        
        Args:
            single_run: Trueの場合、1回だけチェックして終了（GitHub Actions用）
        """
        logging.info("Starting WiFi monitor")
        
        # ルータにログイン
        if not self.router.login():
            logging.error("Failed to login to router")
            return
        
        logging.info("Successfully logged in to router")
        
        # 初期デバイスリストを取得
        initial_devices = self.router.get_connected_devices()
        self.known_devices = {dev['mac'].lower() for dev in initial_devices}
        logging.info(f"Initial devices: {len(self.known_devices)}")
        
        if single_run:
            # 1回だけチェックして終了（GitHub Actions用）
            logging.info("Single run mode - checking once and exiting")
            self._check_for_new_devices()
            logging.info("Single run completed")
            return
        
        # 監視ループを開始
        check_interval = self.config.get('check_interval', 60)
        
        try:
            while True:
                self._check_for_new_devices()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logging.info("Stopping WiFi monitor")
        except Exception as e:
            logging.error(f"Monitor error: {e}")
    
    def _check_for_new_devices(self):
        """新しいデバイス接続をチェックする。"""
        try:
            current_devices = self.router.get_connected_devices()
            current_macs = {dev['mac'].lower() for dev in current_devices}
            
            # 新しいデバイスを検出
            new_macs = current_macs - self.known_devices
            
            for mac in new_macs:
                # デバイス情報を検索
                device_info = next((dev for dev in current_devices if dev['mac'].lower() == mac), None)
                
                if device_info:
                    # このデバイスについて通知すべきかチェック
                    should_notify = (
                        not self.monitored_macs or  # フィルターがない場合は全て通知
                        mac in self.monitored_macs   # または監視リストに含まれている場合
                    )
                    
                    if should_notify:
                        logging.info(f"New device detected: {mac}")
                        self.notifier.send_notification(device_info)
                    else:
                        logging.debug(f"New device detected but not monitored: {mac}")
                    
                    self.known_devices.add(mac)
            
            # 既知セットから切断されたデバイスを削除
            disconnected = self.known_devices - current_macs
            if disconnected:
                logging.info(f"Devices disconnected: {len(disconnected)}")
                self.known_devices = current_macs
                
        except Exception as e:
            logging.error(f"Error checking for new devices: {e}")


def main():
    """メインエントリーポイント。"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python wifi_notifier.py <config_file> [--single-run]")
        print("Example: python wifi_notifier.py config.yaml")
        print("Example: python wifi_notifier.py config.yaml --single-run")
        sys.exit(1)
    
    config_file = sys.argv[1]
    single_run = '--single-run' in sys.argv
    
    try:
        monitor = WiFiMonitor(config_file)
        monitor.start(single_run=single_run)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
