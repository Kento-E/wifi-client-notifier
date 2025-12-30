#!/usr/bin/env python3
"""
Test script for Aterm WiFi Client Notifier

This script helps test the configuration and connectivity.
"""

import sys
import json
import smtplib
import requests
from email.mime.text import MIMEText


def test_config_file(config_path):
    """Test if config file can be loaded."""
    print("設定ファイルをテスト中...")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("✓ 設定ファイルの読み込み成功")
        return config
    except FileNotFoundError:
        print("✗ エラー: 設定ファイルが見つかりません")
        return None
    except json.JSONDecodeError as e:
        print(f"✗ エラー: JSONの形式が正しくありません: {e}")
        return None


def test_router_connection(config):
    """Test connection to router."""
    print("\nルータへの接続をテスト中...")
    try:
        router_ip = config['router']['ip']
        url = f"http://{router_ip}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✓ ルータ ({router_ip}) への接続成功")
            return True
        else:
            print(f"✗ ルータからの応答コード: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print(f"✗ エラー: ルータへの接続がタイムアウトしました")
        return False
    except requests.exceptions.ConnectionError:
        print(f"✗ エラー: ルータに接続できません。IPアドレスを確認してください")
        return False
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def test_smtp_connection(config):
    """Test SMTP connection and authentication."""
    print("\nSMTP接続をテスト中...")
    try:
        email_config = config['email']
        
        if email_config.get('use_tls', True):
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
        else:
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        
        print(f"✓ SMTPサーバー ({email_config['smtp_server']}) への接続成功")
        
        server.login(email_config['smtp_user'], email_config['smtp_password'])
        print("✓ SMTP認証成功")
        
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("✗ エラー: SMTP認証に失敗しました。ユーザー名とパスワードを確認してください")
        return False
    except smtplib.SMTPException as e:
        print(f"✗ SMTPエラー: {e}")
        return False
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False


def send_test_email(config):
    """Send a test email."""
    print("\nテストメールを送信中...")
    try:
        email_config = config['email']
        
        msg = MIMEText("これはAterm WiFi Client Notifierからのテストメールです。", 'plain', 'utf-8')
        msg['Subject'] = "テストメール - Aterm WiFi Client Notifier"
        msg['From'] = email_config['sender_email']
        msg['To'] = ', '.join(email_config['recipient_emails'])
        
        if email_config.get('use_tls', True):
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
        else:
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        
        server.login(email_config['smtp_user'], email_config['smtp_password'])
        server.send_message(msg)
        server.quit()
        
        print(f"✓ テストメールを送信しました: {email_config['recipient_emails']}")
        return True
        
    except Exception as e:
        print(f"✗ テストメール送信失敗: {e}")
        return False


def main():
    """Main test function."""
    print("=== Aterm WiFi Client Notifier 設定テスト ===\n")
    
    if len(sys.argv) != 2:
        print("使用方法: python test_config.py <config_file>")
        print("例: python test_config.py config.json")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Test config file
    config = test_config_file(config_path)
    if not config:
        sys.exit(1)
    
    # Test router connection
    router_ok = test_router_connection(config)
    
    # Test SMTP connection
    smtp_ok = test_smtp_connection(config)
    
    # Offer to send test email
    if smtp_ok:
        print("\nテストメールを送信しますか? (y/n): ", end='')
        response = input().lower()
        if response == 'y':
            send_test_email(config)
    
    # Summary
    print("\n=== テスト結果 ===")
    print(f"設定ファイル: ✓")
    print(f"ルータ接続: {'✓' if router_ok else '✗'}")
    print(f"SMTP接続: {'✓' if smtp_ok else '✗'}")
    
    if router_ok and smtp_ok:
        print("\n✓ すべてのテストが成功しました！")
        print("次のコマンドでモニタリングを開始できます:")
        print(f"python wifi_notifier.py {config_path}")
    else:
        print("\n✗ いくつかのテストが失敗しました。設定を確認してください。")


if __name__ == "__main__":
    main()
