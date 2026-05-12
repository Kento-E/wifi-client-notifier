#!/usr/bin/env python3
"""
Firebase登録トークン管理コマンド

registration_tokensを設定ファイルから管理するコマンドラインツール。
デフォルトでは既存のトークンに新しいトークンを追加し、--overwriteオプションで
既存のトークンを置き換えることができます。
"""

import argparse
import sys
import os
import logging
import re
from typing import List


class RegistrationTokenManager:
    """Firebase登録トークンを管理する。"""

    def __init__(self, config_path: str):
        """
        設定ファイルを使用して初期化する。

        Args:
            config_path: 設定ファイルのパス
        """
        self.config_path = config_path
        self.config_content = ""
        self._load_config()

    def _load_config(self) -> None:
        """設定ファイルを読み込む。"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_content = f.read()
        except Exception as e:
            raise Exception(f"設定ファイルの読み込みに失敗しました: {e}")

    def _save_config(self) -> None:
        """設定ファイルを保存する。"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(self.config_content)
            logging.info(f"設定ファイルを保存しました: {self.config_path}")
        except Exception as e:
            raise Exception(f"設定ファイルの保存に失敗しました: {e}")

    def _extract_tokens_from_content(self) -> List[str]:
        """設定ファイルのコンテンツからtokenを抽出する。

        Returns:
            抽出されたトークンのリスト
        """
        tokens = []
        # registration_tokens セクションを探す
        pattern = r"registration_tokens:\s*\n((?:\s+-\s+.*\n)*)"
        match = re.search(pattern, self.config_content)

        if match:
            tokens_block = match.group(1)
            # 各トークンを抽出
            token_lines = re.findall(r'^\s+-\s+"([^"]+)"\s*$', tokens_block, re.MULTILINE)
            tokens.extend(token_lines)

        return tokens

    def _replace_tokens_in_content(self, new_tokens: List[str]) -> None:
        """設定ファイルのトークンセクションを置き換える。

        Args:
            new_tokens: 新しいトークンのリスト
        """
        # YAML形式でトークンを生成
        if new_tokens:
            tokens_yaml = "registration_tokens:\n"
            for token in new_tokens:
                tokens_yaml += f'    - "{token}"\n'
        else:
            tokens_yaml = "registration_tokens: []\n"

        # 既存のregistration_tokensセクションを置き換える
        pattern = r"registration_tokens:\s*(?:\n(?:\s+-\s+.*)*|\s*\[\s*\])"
        self.config_content = re.sub(
            pattern, tokens_yaml.rstrip("\n"), self.config_content, count=1
        )

    def get_current_tokens(self) -> List[str]:
        """現在の登録トークンを取得する。

        Returns:
            登録トークンのリスト
        """
        return self._extract_tokens_from_content()

    def add_tokens(self, new_tokens: List[str]) -> None:
        """既存のトークンに新しいトークンを追加する。

        Args:
            new_tokens: 追加するトークンのリスト
        """
        current_tokens = self.get_current_tokens()

        # 重複を避けて追加
        added_count = 0
        for token in new_tokens:
            if token not in current_tokens:
                current_tokens.append(token)
                added_count += 1
                logging.info(f"トークンを追加しました: {token[:30]}...")

        if added_count > 0:
            self._replace_tokens_in_content(current_tokens)
            self._save_config()
            logging.info(f"合計 {added_count} 個のトークンを追加しました")
        else:
            logging.info("追加するトークンはありません（既に登録済みか重複）")

    def set_tokens(self, new_tokens: List[str]) -> None:
        """登録トークンを置き換える（上書きモード）。

        Args:
            new_tokens: 設定するトークンのリスト
        """
        old_count = len(self.get_current_tokens())
        self._replace_tokens_in_content(new_tokens)
        self._save_config()
        old_msg = f"登録トークンを置き換えました （削除: {old_count}個、"
        new_msg = f"新規: {len(new_tokens)}個）"
        logging.info(old_msg + new_msg)

    def remove_tokens(self, tokens_to_remove: List[str]) -> None:
        """登録トークンを削除する。

        Args:
            tokens_to_remove: 削除するトークンのリスト
        """
        current_tokens = self.get_current_tokens()
        removed_count = 0

        for token in tokens_to_remove:
            if token in current_tokens:
                current_tokens.remove(token)
                removed_count += 1
                logging.info(f"トークンを削除しました: {token[:30]}...")

        if removed_count > 0:
            self._replace_tokens_in_content(current_tokens)
            self._save_config()
            logging.info(f"合計 {removed_count} 個のトークンを削除しました")
        else:
            logging.info("削除するトークンはありません")

    def list_tokens(self) -> None:
        """登録トークンを一覧表示する。"""
        tokens = self.get_current_tokens()

        if not tokens:
            print("登録済みのトークンはありません")
            return

        print(f"\n登録済みのトークン（合計: {len(tokens)}個）:\n")
        for i, token in enumerate(tokens, 1):
            # トークンの前後20文字を表示
            prefix = token[:20] if len(token) >= 20 else token
            suffix = token[-20:] if len(token) >= 20 else ""
            masked = f"{prefix}...{suffix}" if suffix else prefix
            print(f"{i}. {masked}")


def create_parser() -> argparse.ArgumentParser:
    """コマンドラインパーサーを作成する。

    Returns:
        設定されたArgumentParserインスタンス
    """
    parser = argparse.ArgumentParser(
        description="Firebase登録トークンを管理するコマンドラインツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # トークンを追加（デフォルト）
  python src/manage_registration_tokens.py config.yaml add <token>
  python src/manage_registration_tokens.py config.yaml add <token1> <token2> ...

  # トークンを上書き
  python src/manage_registration_tokens.py config.yaml set <token1> <token2> ... --overwrite
  または
  python src/manage_registration_tokens.py config.yaml set --overwrite <token1> <token2> ...

  # トークンを削除
  python src/manage_registration_tokens.py config.yaml remove <token>
  python src/manage_registration_tokens.py config.yaml remove <token1> <token2> ...

  # トークン一覧を表示
  python src/manage_registration_tokens.py config.yaml list
        """,
    )

    parser.add_argument("config", help="設定ファイルのパス（例: config.yaml）")

    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")

    # addコマンド
    add_parser = subparsers.add_parser("add", help="トークンを追加（デフォルト動作）")
    add_parser.add_argument("tokens", nargs="+", help="追加するトークン（1個以上）")

    # setコマンド
    set_parser = subparsers.add_parser(
        "set",
        help="トークンを置き換え（上書きモード）",
        aliases=["overwrite"],
    )
    set_parser.add_argument("tokens", nargs="+", help="設定するトークン（1個以上）")
    set_parser.add_argument(
        "--overwrite",
        "-o",
        action="store_true",
        help="上書きモードを有効にする（明示的な確認用）",
    )

    # removeコマンド
    remove_parser = subparsers.add_parser("remove", help="トークンを削除")
    remove_parser.add_argument("tokens", nargs="+", help="削除するトークン（1個以上）")

    # listコマンド
    subparsers.add_parser("list", help="登録済みのトークンを一覧表示")

    return parser


def setup_logging() -> None:
    """ロギングをセットアップする。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def main():
    """メインエントリーポイント。"""
    setup_logging()
    parser = create_parser()
    args = parser.parse_args()

    # コマンドが指定されていない場合の処理
    if not args.command:
        # デフォルトは list コマンド
        args.command = "list"
        args.tokens = []

    try:
        manager = RegistrationTokenManager(args.config)

        if args.command == "add":
            manager.add_tokens(args.tokens)
        elif args.command in ["set", "overwrite"]:
            manager.set_tokens(args.tokens)
        elif args.command == "remove":
            manager.remove_tokens(args.tokens)
        elif args.command == "list":
            manager.list_tokens()
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logging.error(f"エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
