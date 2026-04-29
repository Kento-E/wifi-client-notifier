#!/usr/bin/env python3
"""
WiFi通知ツール状態管理モジュール

既知デバイス、未知デバイス通知履歴、デバイス切断情報などを管理する。
"""

import os
import json
import logging
import tempfile
from typing import Dict, Set


class StateManager:
    """デバイス状態と通知履歴を管理する。"""

    def __init__(self, state_file: str):
        """初期化。

        Args:
            state_file: 状態ファイルのパス
        """
        self.state_file = state_file
        self.known_devices: Set[str] = set()
        self.unknown_notified_macs: Set[str] = set()
        self.missing_counts: Dict[str, int] = {}
        self.last_notified_at: Dict[str, float] = {}
        self.disconnected_at: Dict[str, float] = {}
        self.state_loaded: bool = False

    def load(self) -> bool:
        """状態ファイルから状態を読み込む。

        Returns:
            読み込み成功時はTrue、ファイルが存在しない場合や失敗時はFalse
        """
        if not os.path.exists(self.state_file):
            self.state_loaded = False
            self.known_devices = set()
            self.unknown_notified_macs = set()
            self.missing_counts = {}
            self.last_notified_at = {}
            self.disconnected_at = {}
            return False

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            # 既知デバイスのリスト
            known_devices_list = state.get("known_devices", [])
            if not isinstance(known_devices_list, list):
                raise ValueError("known_devices は配列である必要があります")
            self.known_devices = {
                mac.strip().lower()
                for mac in known_devices_list
                if isinstance(mac, str) and mac.strip()
            }

            # 未知デバイス初回通知済みリスト
            unknown_notified_list = state.get("unknown_notified_macs", [])
            if not isinstance(unknown_notified_list, list):
                raise ValueError("unknown_notified_macs は配列である必要があります")
            self.unknown_notified_macs = {
                mac.strip().lower()
                for mac in unknown_notified_list
                if isinstance(mac, str) and mac.strip()
            }

            # 見失い回数
            raw_missing_counts = state.get("missing_counts", {})
            self.missing_counts = {}
            if isinstance(raw_missing_counts, dict):
                for mac, count in raw_missing_counts.items():
                    if not isinstance(mac, str):
                        continue
                    try:
                        parsed_count = int(count)
                        if parsed_count < 0:
                            logging.warning(
                                "状態ファイルに負の missing_counts を検出したため "
                                "0 に補正します: %s=%s",
                                mac,
                                parsed_count,
                            )
                            parsed_count = 0
                        self.missing_counts[mac.lower()] = parsed_count
                    except (TypeError, ValueError):
                        continue

            for mac in self.known_devices:
                self.missing_counts.setdefault(mac, 0)

            # 最後の通知時刻
            raw_last_notified_at = state.get("last_notified_at", {})
            self.last_notified_at = {}
            if isinstance(raw_last_notified_at, dict):
                for mac, timestamp in raw_last_notified_at.items():
                    if not isinstance(mac, str):
                        continue
                    try:
                        parsed_timestamp = float(timestamp)
                        if parsed_timestamp < 0:
                            continue
                        self.last_notified_at[mac.lower()] = parsed_timestamp
                    except (TypeError, ValueError):
                        continue

            # 切断時刻
            raw_disconnected_at = state.get("disconnected_at", {})
            self.disconnected_at = {}
            if isinstance(raw_disconnected_at, dict):
                for mac, timestamp in raw_disconnected_at.items():
                    if not isinstance(mac, str):
                        continue
                    try:
                        parsed_timestamp = float(timestamp)
                        if parsed_timestamp < 0:
                            continue
                        self.disconnected_at[mac.lower()] = parsed_timestamp
                    except (TypeError, ValueError):
                        continue

            self.state_loaded = True
            logging.info(
                "状態ファイルを読み込みました: known=%s (%s)",
                len(self.known_devices),
                self.state_file,
            )
            return True

        except Exception as e:
            logging.warning("状態ファイルの読み込みに失敗したため空状態で開始します: %s", e)
            self.state_loaded = False
            self.known_devices = set()
            self.unknown_notified_macs = set()
            self.missing_counts = {}
            self.last_notified_at = {}
            self.disconnected_at = {}
            return False

    def save(self) -> None:
        """現在の状態をファイルに保存する。"""
        tmp_path = None
        try:
            state = {
                "known_devices": sorted(self.known_devices),
                "unknown_notified_macs": sorted(self.unknown_notified_macs),
                "missing_counts": {
                    mac: self.missing_counts.get(mac, 0) for mac in self.known_devices
                },
                "last_notified_at": {
                    mac: self.last_notified_at[mac] for mac in sorted(self.last_notified_at)
                },
                "disconnected_at": {
                    mac: self.disconnected_at[mac] for mac in sorted(self.disconnected_at)
                },
            }
            state_dir = os.path.dirname(self.state_file)
            if state_dir:
                os.makedirs(state_dir, exist_ok=True)

            fd, tmp_path = tempfile.mkstemp(
                prefix=".wifi_notifier_state_",
                suffix=".tmp",
                dir=state_dir or ".",
                text=True,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.state_file)
            tmp_path = None
        except Exception as e:
            logging.error("状態ファイルの保存に失敗しました: %s", e)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def add_known_device(self, mac: str) -> None:
        """デバイスを既知デバイスリストに追加する。

        Args:
            mac: デバイスのMACアドレス
        """
        mac_lower = mac.lower()
        self.known_devices.add(mac_lower)
        self.missing_counts.setdefault(mac_lower, 0)

    def remove_known_device(self, mac: str) -> None:
        """デバイスを既知デバイスリストから削除する。

        Args:
            mac: デバイスのMACアドレス
        """
        mac_lower = mac.lower()
        self.known_devices.discard(mac_lower)
        self.missing_counts.pop(mac_lower, None)

    def mark_device_notified(self, mac: str, timestamp: float) -> None:
        """デバイスの通知時刻を記録する。

        Args:
            mac: デバイスのMACアドレス
            timestamp: 通知時刻（Unix時刻）
        """
        self.last_notified_at[mac.lower()] = timestamp

    def mark_device_disconnected(self, mac: str, timestamp: float) -> None:
        """デバイスの切断時刻を記録する。

        Args:
            mac: デバイスのMACアドレス
            timestamp: 切断時刻（Unix時刻）
        """
        self.disconnected_at[mac.lower()] = timestamp

    def clear_missing_count(self, mac: str) -> None:
        """デバイスの見失い回数をクリアする。

        Args:
            mac: デバイスのMACアドレス
        """
        self.missing_counts[mac.lower()] = 0

    def increment_missing_count(self, mac: str) -> int:
        """デバイスの見失い回数をインクリメントする。

        Args:
            mac: デバイスのMACアドレス

        Returns:
            更新後の見失い回数
        """
        mac_lower = mac.lower()
        new_count = self.missing_counts.get(mac_lower, 0) + 1
        self.missing_counts[mac_lower] = new_count
        return new_count
