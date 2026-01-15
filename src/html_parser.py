#!/usr/bin/env python3
"""
WiFiルータクライアント - Webスクレイピングを使用した代替実装

このモジュールは、APIアクセスが利用できない場合に、WiFiルータの
Webインターフェースからデバイス情報をスクレイピングする関数を提供します。
"""

from bs4 import BeautifulSoup
import re
from typing import List, Dict

# MACアドレスのOUI（Organizationally Unique Identifier）の長さ（文字数）
OUI_LENGTH = 8  # "XX:XX:XX" 形式


def parse_wireless_lan_status(html_content: str) -> List[Dict[str, str]]:
    """
    無線LANステータスページを解析して接続デバイスを抽出する。

    この関数は一般的なルータのHTML形式の解析を試みます。

    Args:
        html_content: ルータの無線ステータスページからのHTMLコンテンツ

    Returns:
        デバイス情報を含む辞書のリスト
    """
    devices = []

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # デバイス情報を含むテーブルを検索
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")

            for row in rows:
                cells = row.find_all("td")

                if len(cells) >= 2:
                    # MACアドレスパターンを探す
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)

                        # MACアドレスパターン: XX:XX:XX:XX:XX:XX
                        mac_pattern = r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})"
                        mac_match = re.search(mac_pattern, text)

                        if mac_match:
                            device = {
                                "mac": mac_match.group(0).upper(),
                                "ip": "",
                                "hostname": "",
                                "user_agent": "",
                                "device_type": "",
                                "vendor": "",
                                "signal_strength": "",
                                "connection_speed": "",
                                "connection_time": "",
                            }

                            # 近くのセルからIPアドレスを取得を試みる
                            if i + 1 < len(cells):
                                next_text = cells[i + 1].get_text(strip=True)
                                ip_pattern = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
                                ip_match = re.search(ip_pattern, next_text)
                                if ip_match:
                                    device["ip"] = ip_match.group(0)

                            # ホスト名を取得を試みる
                            if i > 0:
                                prev_text = cells[i - 1].get_text(strip=True)
                                if prev_text and not re.search(mac_pattern, prev_text):
                                    device["hostname"] = prev_text

                            # 追加情報を全てのセルから抽出を試みる
                            for j, extra_cell in enumerate(cells):
                                extra_text = extra_cell.get_text(strip=True)

                                # 信号強度の検出（例: "75%", "-60 dBm"など）
                                if "%" in extra_text or "dBm" in extra_text or "dbm" in extra_text:
                                    device["signal_strength"] = extra_text

                                # 接続速度の検出（例: "150Mbps", "1200Mbps"など）
                                if (
                                    "Mbps" in extra_text
                                    or "mbps" in extra_text
                                    or "Gbps" in extra_text
                                ):
                                    device["connection_speed"] = extra_text

                                # デバイス種別の検出（例: "スマートフォン", "PC", "tablet"など）
                                device_type_keywords = [
                                    "phone",
                                    "smartphone",
                                    "tablet",
                                    "pc",
                                    "laptop",
                                    "desktop",
                                    "mobile",
                                    "スマートフォン",
                                    "タブレット",
                                    "パソコン",
                                    "ノートPC",
                                ]
                                extra_lower = extra_text.lower()
                                for keyword in device_type_keywords:
                                    if keyword in extra_lower:
                                        device["device_type"] = extra_text
                                        break

                            # MACアドレスからベンダー情報を推定
                            device["vendor"] = _get_vendor_from_mac(device["mac"])

                            devices.append(device)
                            break

        return devices

    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []


def _get_vendor_from_mac(mac_address: str) -> str:
    """
    MACアドレスのOUI（最初の3バイト）から製造元を推定する。

    Args:
        mac_address: MACアドレス

    Returns:
        製造元名（不明な場合は空文字列）
    """
    # MACアドレスのOUI（最初の3バイト）から製造元を判定
    # 一般的なベンダーのOUIプレフィックス
    oui_vendors = {
        "00:50:F2": "Microsoft",
        "00:0C:F1": "Intel",
        "00:1B:63": "Apple",
        "00:25:00": "Apple",
        "00:26:BB": "Apple",
        "00:3E:E1": "Apple",
        "00:50:E4": "Apple",
        "AC:DE:48": "Apple",
        "B8:27:EB": "Raspberry Pi Foundation",
        "DC:A6:32": "Raspberry Pi Foundation",
        "E4:5F:01": "Raspberry Pi Foundation",
        "00:1A:11": "Google",
        "00:1E:C2": "Apple",
        "28:CF:E9": "Apple",
        "54:26:96": "Apple",
        "84:38:35": "Apple",
        "A4:5E:60": "Apple",
        "D0:C5:F3": "Apple",
        "E0:F8:47": "Apple",
        "F4:F5:D8": "Google",
        "00:1F:5B": "Apple",
        "00:23:12": "Apple",
        "00:23:32": "Apple",
        "00:23:6C": "Apple",
        "00:23:DF": "Apple",
        "00:24:36": "Apple",
        "00:25:4B": "Apple",
        "00:25:BC": "Apple",
        "00:26:08": "Apple",
        "00:26:4A": "Apple",
        "3C:15:C2": "Apple",
        "60:33:4B": "Apple",
        "60:F8:1D": "Apple",
        "64:20:0C": "Apple",
        "64:B9:E8": "Apple",
        "68:A8:6D": "Apple",
        "6C:40:08": "Apple",
        "70:11:24": "Apple",
        "70:CD:60": "Apple",
        "78:31:C1": "Apple",
        "78:A3:E4": "Apple",
        "7C:11:BE": "Apple",
        "7C:6D:62": "Apple",
        "80:BE:05": "Apple",
        "80:E6:50": "Apple",
        "88:1F:A1": "Apple",
        "8C:58:77": "Apple",
        "8C:7C:92": "Apple",
        "90:27:E4": "Apple",
        "90:72:40": "Apple",
        "98:FE:94": "Apple",
        "9C:20:7B": "Apple",
        "A4:D1:8C": "Apple",
        "A8:20:66": "Apple",
        "A8:66:7F": "Apple",
        "A8:88:08": "Apple",
        "AC:3C:0B": "Apple",
        "AC:87:A3": "Apple",
        "B0:34:95": "Apple",
        "B4:F0:AB": "Apple",
        "B8:09:8A": "Apple",
        "B8:C7:5D": "Apple",
        "BC:3B:AF": "Apple",
        "BC:52:B7": "Apple",
        "BC:6C:21": "Apple",
        "BC:92:6B": "Apple",
        "C0:84:7D": "Apple",
        "C4:2C:03": "Apple",
        "C8:2A:14": "Apple",
        "C8:B5:B7": "Apple",
        "CC:25:EF": "Apple",
        "CC:29:F5": "Apple",
        "D0:25:98": "Apple",
        "D4:9A:20": "Apple",
        "D8:30:62": "Apple",
        "D8:9E:3F": "Apple",
        "D8:A2:5E": "Apple",
        "DC:2B:2A": "Apple",
        "E0:B9:A5": "Apple",
        "E4:25:E7": "Apple",
        "E4:9A:79": "Apple",
        "E8:04:0B": "Apple",
        "E8:80:2E": "Apple",
        "EC:85:2F": "Apple",
        "F0:DC:E2": "Apple",
        "F4:0F:24": "Apple",
        "F8:1E:DF": "Apple",
        "F8:27:93": "Apple",
        "FC:25:3F": "Apple",
        "00:15:83": "Sony",
        "00:19:C5": "Sony",
        "00:1D:BA": "Sony",
        "00:24:BE": "Sony",
        "00:0D:93": "Samsung",
        "00:12:FB": "Samsung",
        "00:13:77": "Samsung",
        "00:15:B9": "Samsung",
        "00:16:32": "Samsung",
        "00:16:6B": "Samsung",
        "00:16:6C": "Samsung",
        "00:17:C9": "Samsung",
        "00:17:D5": "Samsung",
        "00:18:AF": "Samsung",
        "00:1A:8A": "Samsung",
        "00:1B:98": "Samsung",
        "00:1C:43": "Samsung",
        "00:1D:25": "Samsung",
        "00:1E:7D": "Samsung",
        "00:1F:CC": "Samsung",
        "00:21:19": "Samsung",
        "00:21:4C": "Samsung",
        "00:23:39": "Samsung",
        "00:23:D6": "Samsung",
        "00:23:D7": "Samsung",
        "00:24:54": "Samsung",
        "00:24:90": "Samsung",
        "00:24:91": "Samsung",
        "00:24:E9": "Samsung",
        "00:25:38": "Samsung",
        "00:26:37": "Samsung",
        "00:26:5D": "Samsung",
        "00:26:5F": "Samsung",
        "00:E0:64": "Samsung",
    }

    # MACアドレスの最初の8文字（OUI）を取得
    if len(mac_address) >= OUI_LENGTH:
        oui = mac_address[:OUI_LENGTH].upper()
        return oui_vendors.get(oui, "")

    return ""


def extract_devices_from_json(json_data: Dict) -> List[Dict[str, str]]:
    """
    JSONレスポンスからデバイス情報を抽出する。

    一部のルータはデバイスリストをJSON形式で返します。

    Args:
        json_data: ルータからのJSONレスポンス

    Returns:
        デバイス情報を含む辞書のリスト
    """
    devices = []

    try:
        # 異なるJSON構造を処理
        # 一般的なキー: 'clients', 'devices', 'wlan_clients'

        if "clients" in json_data:
            client_list = json_data["clients"]
        elif "devices" in json_data:
            client_list = json_data["devices"]
        elif "wlan_clients" in json_data:
            client_list = json_data["wlan_clients"]
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
                mac_addr = client.get("mac", client.get("macaddr", "")).upper()

                device = {
                    "mac": mac_addr,
                    "ip": client.get("ip", client.get("ipaddr", "")),
                    "hostname": client.get("hostname", client.get("name", "")),
                    "user_agent": client.get("user_agent", client.get("useragent", "")),
                    "device_type": client.get("device_type", client.get("type", "")),
                    "vendor": client.get("vendor", ""),
                    "signal_strength": client.get("signal_strength", client.get("rssi", "")),
                    "connection_speed": client.get("connection_speed", client.get("speed", "")),
                    "connection_time": client.get(
                        "connection_time", client.get("connected_time", "")
                    ),
                }

                # ベンダー情報が提供されていない場合は、MACアドレスから推定
                if not device["vendor"] and mac_addr:
                    device["vendor"] = _get_vendor_from_mac(mac_addr)

                if device["mac"]:
                    devices.append(device)

        return devices

    except Exception as e:
        print(f"Error extracting devices from JSON: {e}")
        return []
