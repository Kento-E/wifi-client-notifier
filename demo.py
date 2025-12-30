#!/usr/bin/env python3
"""
Demo script to simulate WiFi monitoring without a real router

This script helps test the notification system without requiring actual router access.
"""

import time
import json
import sys
from wifi_notifier import EmailNotifier
from datetime import datetime


def demo_notification():
    """Demonstrate email notification functionality."""
    
    print("=== Aterm WiFi Client Notifier デモ ===\n")
    
    # Load config
    if len(sys.argv) != 2:
        print("使用方法: python demo.py <config_file>")
        print("例: python demo.py config.json")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗: {e}")
        sys.exit(1)
    
    # Initialize email notifier
    email_config = config['email']
    notifier = EmailNotifier(
        email_config['smtp_server'],
        email_config['smtp_port'],
        email_config['smtp_user'],
        email_config['smtp_password'],
        email_config['sender_email'],
        email_config['recipient_emails'],
        email_config.get('use_tls', True)
    )
    
    # Simulate device connection
    demo_device = {
        'mac': 'AA:BB:CC:DD:EE:FF',
        'ip': '192.168.10.100',
        'hostname': 'demo-device'
    }
    
    print("デモ用デバイス情報:")
    print(f"  MACアドレス: {demo_device['mac']}")
    print(f"  IPアドレス: {demo_device['ip']}")
    print(f"  ホスト名: {demo_device['hostname']}")
    print()
    
    print("通知メールを送信中...")
    
    success = notifier.send_notification(demo_device)
    
    if success:
        print("✓ デモ通知メールの送信に成功しました！")
        print(f"送信先: {email_config['recipient_emails']}")
    else:
        print("✗ メール送信に失敗しました")
        print("設定を確認してください")
    
    print("\n=== デモ終了 ===")


if __name__ == "__main__":
    demo_notification()
