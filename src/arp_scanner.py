#!/usr/bin/env python3
"""
ARPスキャナーモジュール

Raspberry Pi Zero 2 Wなどのローカルネットワーク上のホストから
ARPスキャンを使用して接続中のデバイスを検出します。
scapyライブラリを使用し、root権限が必要です。
"""

import logging
import socket
from typing import Dict, List, Optional

try:
    from scapy.all import ARP, Ether, srp  # type: ignore

    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False


def _require_scapy() -> None:
    """scapyが利用可能か確認し、利用できない場合は例外を送出する。"""
    if not SCAPY_AVAILABLE:
        raise ImportError(
            "scapyがインストールされていません。"
            " 'pip install scapy' を実行してインストールしてください。"
        )


class ARPScanner:
    """
    ARPスキャンを使用してローカルネットワーク上のデバイスを検出するクラス。

    Raspberry Pi Zero 2 Wなど、ローカルネットワーク上のホストで動作します。
    ルータへの管理者アクセスが不要です。
    実行にはroot権限が必要です（sudo python または systemdサービスでroot実行）。
    """

    def __init__(self, subnet: Optional[str] = None, interface: Optional[str] = None):
        """
        ARPスキャナーを初期化する。

        Args:
            subnet: スキャン対象のサブネット（例: "192.168.1.0/24"）
                    Noneの場合はデフォルトゲートウェイのサブネットを自動検出します。
            interface: 使用するネットワークインターフェース名（例: "wlan0"）
                       Noneの場合はscapyがデフォルトを使用します。
        """
        _require_scapy()
        self.subnet = subnet
        self.interface = interface

    def _detect_subnet(self) -> str:
        """
        現在のホストのIPアドレスからサブネットを自動検出する。

        外部への接続は行わず、ルーティングテーブルを参照してローカルIPを取得します。
        /24サブネットを仮定します（家庭用ネットワークの一般的な設定）。
        正確なサブネットが必要な場合は設定ファイルで明示的に指定してください。

        Returns:
            検出されたサブネット（CIDR表記、例: "192.168.1.0/24"）
        """
        local_ip = self._get_local_ip()
        # /24サブネットを仮定（家庭用ネットワークの一般的な設定）
        # /16や/23などを使用している場合は config.yaml の arp.subnet で明示的に設定してください
        parts = local_ip.rsplit(".", 1)
        subnet = f"{parts[0]}.0/24"
        logging.info(f"サブネットを自動検出しました（/24を仮定）: {subnet}")
        logging.warning(
            "サブネットを /24 と仮定しています。"
            " /16 や /23 など異なるサブネットマスクを使用している場合は"
            " config.yaml の arp.subnet に明示的に設定してください。"
        )
        return subnet

    @staticmethod
    def _get_local_ip() -> str:
        """
        ルーティングテーブルを参照してローカルIPアドレスを取得する。

        外部への実際の接続は行いません。ブロードキャストアドレスへの
        UDPソケットのルーティングを利用してローカルIPを特定します。

        Returns:
            ローカルIPアドレス（取得できない場合は "192.168.1.1"）
        """
        # 各プライベートアドレス空間（RFC 1918）の代表的なゲートウェイアドレスを試行する
        # これらへの UDPソケット接続（実際には送信しない）でルーティングテーブルを参照し、
        # 対応するネットワークインターフェースのローカルIPを取得する。
        # 192.168.x.x → 一般的な家庭用ネットワーク
        # 10.x.x.x    → 企業ネットワークや一部のルータ
        # 172.16.x.x  → 中規模ネットワーク（RFC 1918の172.16.0.0/12範囲）
        for dummy_target in ("192.168.1.1", "10.0.0.1", "172.16.0.1"):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect((dummy_target, 1))
                    local_ip = s.getsockname()[0]
                if not local_ip.startswith("127."):
                    return local_ip
            except OSError:
                continue
        # フォールバック: hostnameからIPを解決
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            if not local_ip.startswith("127."):
                return local_ip
        except (socket.gaierror, OSError):
            pass
        logging.warning("ローカルIPアドレスの取得に失敗しました。デフォルト値を使用します")
        return "192.168.1.1"

    def scan(self, timeout: int = 2) -> List[Dict[str, str]]:
        """
        ARPスキャンを実行してネットワーク上のデバイスを検出する。

        Args:
            timeout: ARPレスポンスの待機時間（秒）

        Returns:
            デバイス情報を含む辞書のリスト。
            各辞書には 'mac', 'ip', 'hostname' キーが含まれます。
        """
        subnet = self.subnet or self._detect_subnet()
        logging.debug(f"ARPスキャンを実行します: subnet={subnet}, timeout={timeout}s")

        try:
            # ARPリクエストパケットを作成して送信
            arp_request = ARP(pdst=subnet)
            broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
            arp_request_broadcast = broadcast / arp_request

            kwargs: Dict = {"timeout": timeout, "verbose": 0}
            if self.interface:
                kwargs["iface"] = self.interface

            answered_list, _ = srp(arp_request_broadcast, **kwargs)

            devices = []
            for _, received in answered_list:
                mac = received.hwsrc.upper()
                ip = received.psrc
                hostname = self._resolve_hostname(ip)
                devices.append(
                    {
                        "mac": mac,
                        "ip": ip,
                        "hostname": hostname,
                    }
                )
                logging.debug(f"デバイス検出: MAC={mac}, IP={ip}, hostname={hostname}")

            logging.info(f"ARPスキャン完了: {len(devices)}台のデバイスを検出しました")
            return devices

        except PermissionError:
            logging.error(
                "ARPスキャンにroot権限が必要です。"
                " 'sudo python' または systemdサービスをroot権限で実行してください。"
            )
            return []
        except Exception as e:
            logging.error(f"ARPスキャン中にエラーが発生しました: {e}")
            return []

    @staticmethod
    def _resolve_hostname(ip: str) -> str:
        """
        IPアドレスからホスト名を逆引きする。

        Args:
            ip: 解決するIPアドレス

        Returns:
            ホスト名、解決できない場合はIPアドレスをそのまま返す
        """
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except (socket.herror, socket.gaierror, OSError):
            return ip
