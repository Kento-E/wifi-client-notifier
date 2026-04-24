#!/usr/bin/env python3
"""
ARPスキャナーモジュール

Raspberry Pi Zero 2 Wなどのローカルネットワーク上のホストから
ARPスキャンを使用して接続中のデバイスを検出します。
scapyライブラリを使用し、root権限またはCAP_NET_RAWケーパビリティが必要です。
"""

import logging
import os
import glob
import re
import socket
import subprocess
from typing import Dict, List, Optional, Tuple

try:
    from scapy.all import ARP, Ether, srp  # type: ignore

    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

try:
    from mac_vendor_lookup import MacLookup  # type: ignore

    MAC_VENDOR_AVAILABLE = True
except ImportError:
    MAC_VENDOR_AVAILABLE = False


def _require_scapy() -> None:
    """scapyが利用可能か確認し、利用できない場合は例外を送出する。"""
    if not SCAPY_AVAILABLE:
        raise ImportError(
            "scapyがインストールされていません。"
            " 'pip install scapy' を実行してインストールしてください。"
        )


def _has_cap_net_raw() -> bool:
    """
    現在のプロセスがCAP_NET_RAWケーパビリティを持っているか確認する。

    Linuxの /proc/self/status から実効ケーパビリティを読み取ります。
    Linux以外では常にFalseを返します。
    """
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("CapEff:"):
                    cap_eff = int(line.split()[1], 16)
                    # CAP_NET_RAW のビット番号は 13
                    return bool(cap_eff & (1 << 13))
    except OSError as e:
        logging.debug(f"CAP_NET_RAWチェックに失敗しました（Linux以外の環境では無視可）: {e}")
    except ValueError as e:
        logging.debug(f"CAP_NET_RAWの解析に失敗しました: {e}")
    return False


def _require_network_raw_capability() -> None:
    """
    ARPスキャンに必要な権限（root権限またはCAP_NET_RAWケーパビリティ）を確認する。

    以下のいずれかの条件を満たさない場合は PermissionError を送出する:
    - 実効UID = 0（root）
    - CAP_NET_RAW ケーパビリティを保有（systemd の AmbientCapabilities=CAP_NET_RAW 等）
    """
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        return  # root権限あり
    if _has_cap_net_raw():
        return  # CAP_NET_RAWケーパビリティあり
    raise PermissionError(
        "ARPスキャンにはroot権限またはCAP_NET_RAWケーパビリティが必要です。"
        " 'sudo python src/wifi_notifier.py <config_file>' で実行するか、"
        " systemdサービスで AmbientCapabilities=CAP_NET_RAW を設定してください。"
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
        # MACアドレスからベンダー名を取得するためのルックアップテーブルを初期化
        self._mac_lookup: Optional[MacLookup] = None
        if MAC_VENDOR_AVAILABLE:
            try:
                self._mac_lookup = MacLookup()
            except Exception as e:
                logging.warning(f"MACベンダールックアップの初期化に失敗しました: {e}")

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

        Raises:
            PermissionError: root権限またはCAP_NET_RAWケーパビリティがない場合
        """
        _require_network_raw_capability()
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
            dhcp_hostname_map = self._load_dhcp_hostname_map()
            for _, received in answered_list:
                mac = received.hwsrc.upper()
                ip = received.psrc
                hostname = self._resolve_hostname(ip)
                vendor = self._lookup_vendor(mac)
                dhcp_hostname = self._lookup_dhcp_hostname(mac, ip, dhcp_hostname_map)
                mdns_name = self._resolve_mdns_name(ip, fallback_hostname=hostname)
                netbios_name = self._resolve_netbios_name(ip)
                device_type, os_guess = self._guess_device_profile(
                    hostname=hostname,
                    vendor=vendor,
                    dhcp_hostname=dhcp_hostname,
                    mdns_name=mdns_name,
                    netbios_name=netbios_name,
                )
                fingerprint = self._build_fingerprint(
                    vendor=vendor,
                    hostname=hostname,
                    dhcp_hostname=dhcp_hostname,
                    mdns_name=mdns_name,
                    netbios_name=netbios_name,
                    device_type=device_type,
                    os_guess=os_guess,
                )
                devices.append(
                    {
                        "mac": mac,
                        "ip": ip,
                        "hostname": hostname,
                        "vendor": vendor,
                        "dhcp_hostname": dhcp_hostname,
                        "mdns_name": mdns_name,
                        "netbios_name": netbios_name,
                        # ARP方式では接続品質情報は取得元がないため空で返す
                        "connection_band": "",
                        "rssi": "",
                        "bssid": "",
                        "connection_time": "",
                        "device_type": device_type,
                        "os_guess": os_guess,
                        "fingerprint": fingerprint,
                    }
                )
                logging.debug(
                    "デバイス検出: MAC=%s, IP=%s, hostname=%s, vendor=%s, "
                    "dhcp=%s, mdns=%s, netbios=%s, type=%s, os=%s",
                    mac,
                    ip,
                    hostname,
                    vendor,
                    dhcp_hostname,
                    mdns_name,
                    netbios_name,
                    device_type,
                    os_guess,
                )

            logging.info(f"ARPスキャン完了: {len(devices)}台のデバイスを検出しました")
            return devices

        except PermissionError:
            # scapyが投げたPermissionErrorは呼び出し元まで伝播させる
            raise
        except Exception as e:
            logging.error(f"ARPスキャン中にエラーが発生しました: {e}")
            # 例外を再スローして呼び出し元で失敗を正確に検知できるようにする
            raise

    @staticmethod
    def _resolve_hostname(ip: str, timeout: float = 1.0) -> str:
        """
        IPアドレスからホスト名をタイムアウト付きで逆引きする。

        DNS逆引きが設定されていない環境での遅延を防ぐため、
        タイムアウトを設定してベストエフォートで名前解決を試みます。

        注意: `socket.setdefaulttimeout()` はプロセスグローバルな設定です。
        マルチスレッド環境では他スレッドのソケット操作に影響する可能性がありますが、
        `finally` で元の値に戻すことで影響を最小化しています。
        `gethostbyaddr()` は個別タイムアウト設定に対応していないため、この実装を採用しています。

        Args:
            ip: 解決するIPアドレス
            timeout: 名前解決のタイムアウト秒数（デフォルト: 1秒）

        Returns:
            ホスト名、解決できない場合はIPアドレスをそのまま返す
        """
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except (socket.herror, socket.gaierror, socket.timeout, OSError):
            return ip
        finally:
            socket.setdefaulttimeout(old_timeout)

    def _lookup_vendor(self, mac: str) -> str:
        """
        MACアドレスのOUI部分からデバイスメーカー名を取得する。

        mac-vendor-lookupライブラリを使用してオフラインでベンダー名を解決します。
        ライブラリが未インストールの場合や未知のOUIの場合は空文字を返します。

        Args:
            mac: MACアドレス（例: "AC:DE:48:00:11:22"）

        Returns:
            ベンダー名（例: "Apple, Inc."）、取得できない場合は空文字
        """
        if self._mac_lookup is None:
            return ""
        try:
            return self._mac_lookup.lookup(mac)
        except Exception:
            return ""

    @staticmethod
    def _load_dhcp_hostname_map() -> Dict[str, str]:
        """ローカルDHCPリース情報から MAC/IP -> ホスト名の対応表を作成する。"""
        result: Dict[str, str] = {}
        candidates: List[str] = []
        for pattern in (
            "/var/lib/misc/dnsmasq.leases",
            "/var/lib/NetworkManager/dnsmasq-*.leases",
            "/var/lib/NetworkManager/dnsmasq.leases",
        ):
            candidates.extend(glob.glob(pattern))

        for lease_file in candidates:
            try:
                with open(lease_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) < 4:
                            continue
                        # dnsmasq形式: <expiry> <mac> <ip> <hostname> <client-id>
                        mac = parts[1].strip().lower()
                        ip = parts[2].strip()
                        hostname = parts[3].strip()
                        if hostname in {"*", "-", ""}:
                            continue
                        if mac:
                            result[f"mac:{mac}"] = hostname
                        if ip:
                            result[f"ip:{ip}"] = hostname
            except OSError:
                continue

        return result

    @staticmethod
    def _lookup_dhcp_hostname(mac: str, ip: str, dhcp_hostname_map: Dict[str, str]) -> str:
        """DHCPリース情報からホスト名を取得する。"""
        mac_key = f"mac:{mac.lower()}"
        ip_key = f"ip:{ip}"
        return dhcp_hostname_map.get(mac_key, dhcp_hostname_map.get(ip_key, ""))

    @staticmethod
    def _run_command(command: List[str], timeout: float = 1.5) -> str:
        """外部コマンドを短時間実行し、標準出力を返す。"""
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if completed.returncode != 0:
                return ""
            return completed.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def _resolve_mdns_name(self, ip: str, fallback_hostname: str = "") -> str:
        """mDNS名を推定して返す。"""
        if fallback_hostname.endswith(".local"):
            return fallback_hostname

        output = self._run_command(["avahi-resolve-address", ip])
        if output:
            # 例: "192.168.10.20\thostname.local"
            parts = output.split()
            candidate = parts[-1] if parts else ""
            if candidate.endswith(".local"):
                return candidate

        return ""

    def _resolve_netbios_name(self, ip: str) -> str:
        """NetBIOS名を取得する。取得不可時は空文字。"""
        output = self._run_command(["nmblookup", "-A", ip])
        if not output:
            return ""

        for line in output.splitlines():
            # 例: "MYPC           <00> -         B <ACTIVE>"
            match = re.match(r"^\s*([^<\s][^<]*)\s+<00>\s+-.*<ACTIVE>", line)
            if match:
                name = match.group(1).strip()
                if name:
                    return name

        return ""

    @staticmethod
    def _guess_device_profile(
        hostname: str,
        vendor: str,
        dhcp_hostname: str,
        mdns_name: str,
        netbios_name: str,
    ) -> Tuple[str, str]:
        """端末種別とOS推定をベストエフォートで返す。"""
        combined = " ".join([hostname, vendor, dhcp_hostname, mdns_name, netbios_name]).lower()

        if any(keyword in combined for keyword in ("iphone", "ipad", "ios", "apple")):
            return "スマートフォン/タブレット", "iOS/iPadOS"
        if any(keyword in combined for keyword in ("macbook", "imac", "mac mini", "macos")):
            return "PC", "macOS"
        if any(keyword in combined for keyword in ("android", "pixel", "galaxy", "xperia")):
            return "スマートフォン/タブレット", "Android"
        if any(keyword in combined for keyword in ("windows", "desktop-", "laptop-", "win")):
            return "PC", "Windows"
        if any(keyword in combined for keyword in ("playstation", "ps5", "ps4", "nintendo")):
            return "ゲーム機", "専用OS"
        if any(
            keyword in combined for keyword in ("tv", "bravia", "regza", "fire tv", "chromecast")
        ):
            return "家電/AV機器", "組み込みOS"

        if vendor:
            return "不明", "不明"
        return "", ""

    @staticmethod
    def _build_fingerprint(
        vendor: str,
        hostname: str,
        dhcp_hostname: str,
        mdns_name: str,
        netbios_name: str,
        device_type: str,
        os_guess: str,
    ) -> str:
        """OUI以外の識別に使える情報を要約した文字列を返す。"""
        items = [
            vendor,
            dhcp_hostname,
            mdns_name,
            netbios_name,
            hostname,
            device_type,
            os_guess,
        ]
        normalized = []
        seen = set()
        for item in items:
            value = str(item).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(value)

        return " | ".join(normalized)
