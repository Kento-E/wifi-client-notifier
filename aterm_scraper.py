#!/usr/bin/env python3
"""
Atermルータクライアント - Webスクレイピングを使用した代替実装

このモジュールは、APIアクセスが利用できない場合に、Atermルータの
Webインターフェースからデバイス情報をスクレイピングする関数を提供します。
"""

from bs4 import BeautifulSoup
import re
from typing import List, Dict


def parse_wireless_lan_status(html_content: str) -> List[Dict[str, str]]:
    """
    無線LANステータスページを解析して接続デバイスを抽出する。
    
    この関数は一般的なAtermルータのHTML形式の解析を試みます。
    
    Args:
        html_content: ルータの無線ステータスページからのHTMLコンテンツ
        
    Returns:
        デバイス情報を含む辞書のリスト
    """
    devices = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # デバイス情報を含むテーブルを検索
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                
                if len(cells) >= 2:
                    # MACアドレスパターンを探す
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)
                        
                        # MACアドレスパターン: XX:XX:XX:XX:XX:XX
                        mac_pattern = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
                        mac_match = re.search(mac_pattern, text)
                        
                        if mac_match:
                            device = {
                                'mac': mac_match.group(0).upper(),
                                'ip': '',
                                'hostname': ''
                            }
                            
                            # 近くのセルからIPアドレスを取得を試みる
                            if i + 1 < len(cells):
                                next_text = cells[i + 1].get_text(strip=True)
                                ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
                                ip_match = re.search(ip_pattern, next_text)
                                if ip_match:
                                    device['ip'] = ip_match.group(0)
                            
                            # ホスト名を取得を試みる
                            if i > 0:
                                prev_text = cells[i - 1].get_text(strip=True)
                                if prev_text and not re.search(mac_pattern, prev_text):
                                    device['hostname'] = prev_text
                            
                            devices.append(device)
                            break
        
        return devices
        
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []


def extract_devices_from_json(json_data: Dict) -> List[Dict[str, str]]:
    """
    JSONレスポンスからデバイス情報を抽出する。
    
    一部のAtermルータはデバイスリストをJSON形式で返します。
    
    Args:
        json_data: ルータからのJSONレスポンス
        
    Returns:
        デバイス情報を含む辞書のリスト
    """
    devices = []
    
    try:
        # 異なるJSON構造を処理
        # 一般的なキー: 'clients', 'devices', 'wlan_clients'
        
        if 'clients' in json_data:
            client_list = json_data['clients']
        elif 'devices' in json_data:
            client_list = json_data['devices']
        elif 'wlan_clients' in json_data:
            client_list = json_data['wlan_clients']
        else:
            # JSON内のリストを検索を試みる
            for value in json_data.values():
                if isinstance(value, list):
                    client_list = value
                    break
            else:
                return []
        
        for client in client_list:
            if isinstance(client, dict):
                device = {
                    'mac': client.get('mac', client.get('macaddr', '')).upper(),
                    'ip': client.get('ip', client.get('ipaddr', '')),
                    'hostname': client.get('hostname', client.get('name', ''))
                }
                
                if device['mac']:
                    devices.append(device)
        
        return devices
        
    except Exception as e:
        print(f"Error extracting devices from JSON: {e}")
        return []
