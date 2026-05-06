#!/usr/bin/env python3
"""
WiFi通知ツール設定管理モジュール

設定ファイルの読み込み、バリデーション、ロギング設定を担当する。
"""

import os
import logging
import yaml
from typing import Dict, Any


class ConfigManager:
    """YAML設定ファイルの読み込みとバリデーションを行う。"""

    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """設定ファイルを読み込む（YAML形式）。

        Args:
            config_path: 設定ファイルのパス

        Returns:
            設定辞書

        Raises:
            FileNotFoundError: 設定ファイルが見つからない場合
            Exception: 設定ファイルの読み込み失敗時
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"エラー: 設定ファイル '{config_path}' が見つかりません")
            print("設定ファイルを作成してください:")
            print("  cp config/config.example.yaml config.yaml")
            raise
        except Exception as e:
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            raise

    @staticmethod
    def setup_logging(config: Dict[str, Any]) -> None:
        """ロギング設定をセットアップする。

        Args:
            config: 設定辞書
        """
        log_level = config.get("log_level", "INFO")
        log_file = config.get("log_file", "wifi_notifier.log")
        logging.root.handlers = []
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(),
            ],
            force=True,
        )

    @staticmethod
    def get_state_file_path(config: Dict[str, Any], config_path: str) -> str:
        """設定から状態ファイルパスを取得する。

        相対パスは設定ファイルのディレクトリからの相対パスとして扱う。

        Args:
            config: 設定辞書
            config_path: 設定ファイルのパス

        Returns:
            状態ファイルの完全パス
        """
        try:
            from src.constants import DEFAULT_STATE_FILE
        except ModuleNotFoundError:
            from constants import DEFAULT_STATE_FILE

        config_dir = os.path.dirname(os.path.abspath(config_path))
        configured_state_file = str(config.get("state_file", "")).strip()

        if configured_state_file:
            expanded_state_file = os.path.expanduser(configured_state_file)
            if os.path.isabs(expanded_state_file):
                return expanded_state_file
            else:
                return os.path.join(config_dir, expanded_state_file)
        else:
            return os.path.join(config_dir, DEFAULT_STATE_FILE)

    @staticmethod
    def parse_bool_config(value: Any, default: bool = False) -> bool:
        """真偽値設定を安全に解釈する。

        Args:
            value: 解析対象の値
            default: デフォルト値

        Returns:
            真偽値
        """
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    @staticmethod
    def validate_detection_method(config: Dict[str, Any]) -> str:
        """検出方式の検証。

        Args:
            config: 設定辞書

        Returns:
            検証済みの検出方式

        Raises:
            ValueError: 検出方式が無効な場合
        """
        detection_method = config.get("detection_method")
        valid_methods = ("arp", "router")

        if detection_method is None:
            raise ValueError(
                "detection_method が設定されていません。"
                f" config.yaml に detection_method を指定してください。"
                f"有効な値: {valid_methods}。"
            )

        if detection_method not in valid_methods:
            raise ValueError(
                f"detection_method の値 '{detection_method}' は無効です。"
                f" 有効な値: {valid_methods}。"
                " config.yaml の detection_method を確認してください。"
            )

        return detection_method

    @staticmethod
    def validate_router_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """ルータ設定の検証。

        Args:
            config: 設定辞書

        Returns:
            検証済みのルータ設定

        Raises:
            ValueError: ルータ設定が不足している場合
        """
        router_config = config.get("router")
        if not router_config:
            raise ValueError(
                "detection_method が 'router' の場合は 'router' " "セクションの設定が必要です。"
            )
        return router_config

    @staticmethod
    def validate_email_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """メール設定の検証。

        Args:
            config: 設定辞書

        Returns:
            検証済みのメール設定

        Raises:
            KeyError: メール設定が不足している場合
        """
        email_config = config.get("email", {})
        required_keys = [
            "smtp_server",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "sender_email",
            "recipient_emails",
        ]
        missing_keys = [key for key in required_keys if key not in email_config]
        if missing_keys:
            raise KeyError(f"メール設定に必須キーが不足しています: {', '.join(missing_keys)}")
        return email_config

    @staticmethod
    def get_email_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """メール設定を取得する。"""
        email_config = config.get("email", {})
        if not isinstance(email_config, dict):
            return {}
        return email_config

    @staticmethod
    def get_google_calendar_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Google Calendar設定を取得する。

        無効またはデフォルト値の場合は空辞書を返す。

        Args:
            config: 設定辞書

        Returns:
            Google Calendar設定（無効な場合は空辞書）
        """
        calendar_config = config.get("google_calendar", {})
        if not isinstance(calendar_config, dict):
            return {}
        return calendar_config

    @staticmethod
    def get_firebase_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Firebase 設定を取得する。"""
        firebase_config = config.get("firebase", {})
        if not isinstance(firebase_config, dict):
            return {}
        return firebase_config

    @staticmethod
    def parse_string_list_config(value: Any) -> list[str]:
        """文字列配列設定を安全に解釈する。"""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def parse_int_config(value: Any, default: int, key_name: str, minimum: int = 1) -> int:
        """整数設定を安全に解釈する。

        Args:
            value: 解析対象の値
            default: デフォルト値
            key_name: 設定キー名（ログ出力用）
            minimum: 最小値

        Returns:
            整数値
        """
        try:
            parsed_value = int(value)
            if parsed_value < minimum:
                logging.warning(
                    f"{key_name} が {minimum} 未満のため {default} を使用します: {parsed_value}"
                )
                return default
            return parsed_value
        except (TypeError, ValueError):
            logging.warning(f"{key_name} の値が不正のため {default} を使用します: {value}")
            return default
