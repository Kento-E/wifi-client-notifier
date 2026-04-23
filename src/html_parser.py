#!/usr/bin/env python3
"""
WiFiルータクライアント - Webスクレイピングを使用した代替実装

このモジュールは、APIアクセスが利用できない場合に、WiFiルータの
Webインターフェースからデバイス情報をスクレイピングする関数を提供します。
"""

from bs4 import BeautifulSoup
import re
from typing import List, Dict


def _first_non_empty_str(source: Dict, keys: List[str]) -> str:
    """候補キーから最初に見つかった非空文字列を返す。"""
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized
    return ""


def _guess_device_profile(
    *, vendor: str, hostname: str, dhcp_hostname: str, mdns_name: str
) -> Dict[str, str]:
    """取得情報から端末種別とOSを推定する。"""
    combined = " ".join([vendor, hostname, dhcp_hostname, mdns_name]).lower()

    if any(keyword in combined for keyword in ("iphone", "ipad", "ios", "apple")):
        return {"device_type": "スマートフォン/タブレット", "os_guess": "iOS/iPadOS"}
    if any(keyword in combined for keyword in ("macbook", "imac", "mac mini", "macos")):
        return {"device_type": "PC", "os_guess": "macOS"}
    if any(keyword in combined for keyword in ("android", "pixel", "galaxy", "xperia")):
        return {"device_type": "スマートフォン/タブレット", "os_guess": "Android"}
    if any(keyword in combined for keyword in ("windows", "desktop-", "laptop-", "win")):
        return {"device_type": "PC", "os_guess": "Windows"}

    return {"device_type": "", "os_guess": ""}


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
                                "vendor": "",
                                "dhcp_hostname": "",
                                "mdns_name": "",
                                "netbios_name": "",
                                "connection_band": "",
                                "rssi": "",
                                "bssid": "",
                                "connection_time": "",
                                "device_type": "",
                                "os_guess": "",
                                "fingerprint": "",
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

                            devices.append(device)
                            break

        return devices

    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []


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
                device = {
                    "mac": client.get("mac", client.get("macaddr", "")).upper(),
                    "ip": client.get("ip", client.get("ipaddr", "")),
                    "hostname": client.get("hostname", client.get("name", "")),
                    "vendor": _first_non_empty_str(
                        client,
                        ["vendor", "manufacturer", "oui_vendor"],
                    ),
                    "dhcp_hostname": _first_non_empty_str(
                        client,
                        ["dhcp_hostname", "dhcpHostName", "host_name"],
                    ),
                    "mdns_name": _first_non_empty_str(
                        client,
                        ["mdns_name", "mdns", "bonjour_name"],
                    ),
                    "netbios_name": _first_non_empty_str(
                        client,
                        ["netbios_name", "netbios", "nb_name"],
                    ),
                    "connection_band": _first_non_empty_str(
                        client,
                        ["band", "freq_band", "wireless_band"],
                    ),
                    "rssi": _first_non_empty_str(
                        client,
                        ["rssi", "signal", "signal_dbm"],
                    ),
                    "bssid": _first_non_empty_str(
                        client,
                        ["bssid", "ap_bssid"],
                    ),
                    "connection_time": _first_non_empty_str(
                        client,
                        ["connection_time", "connected_time", "uptime"],
                    ),
                    "device_type": _first_non_empty_str(client, ["device_type", "type"]),
                    "os_guess": _first_non_empty_str(client, ["os_guess", "os", "platform"]),
                }

                if not device["device_type"] or not device["os_guess"]:
                    guessed = _guess_device_profile(
                        vendor=device["vendor"],
                        hostname=device["hostname"],
                        dhcp_hostname=device["dhcp_hostname"],
                        mdns_name=device["mdns_name"],
                    )
                    if not device["device_type"]:
                        device["device_type"] = guessed["device_type"]
                    if not device["os_guess"]:
                        device["os_guess"] = guessed["os_guess"]

                fingerprint_items = [
                    device.get("vendor", ""),
                    device.get("dhcp_hostname", ""),
                    device.get("mdns_name", ""),
                    device.get("netbios_name", ""),
                    device.get("hostname", ""),
                    device.get("device_type", ""),
                    device.get("os_guess", ""),
                ]
                device["fingerprint"] = " | ".join(
                    [item.strip() for item in fingerprint_items if str(item).strip()]
                )

                if device["mac"]:
                    devices.append(device)

        return devices

    except Exception as e:
        print(f"Error extracting devices from JSON: {e}")
        return []
