# デフォルトエージェント指示

## 言語設定

**すべての応答、コメント、ドキュメント、コードコメントは日本語で出力してください。**

## 基本方針

このリポジトリは日本のAtermルータユーザー向けのプロジェクトです。すべてのコミュニケーションは日本語で行ってください。

### 出力言語ルール

1. **コミットメッセージ**: 日本語で記述
2. **コードコメント**: 日本語で記述
3. **ドキュメント**: 日本語で記述（README、ガイドなど）
4. **エラーメッセージ**: 可能な限り日本語で出力
5. **ログ出力**: 日本語メッセージを含める
6. **Pull Requestの説明**: 日本語で記述
7. **Issueのコメント**: 日本語で記述

### 例外

以下の場合のみ英語を使用できます：
- 変数名、関数名、クラス名（Pythonの命名規則に従う）
- 技術用語で日本語訳が不自然な場合（例: HTTP, SMTP, JSON）
- 外部ライブラリのAPI呼び出し

## コーディング規約

### Pythonコード

```python
def get_device_list():
    """
    デバイスリストを取得する
    
    Returns:
        デバイス情報のリスト
    """
    # デバイスリストを取得
    devices = []
    
    try:
        # ルータに接続
        response = connect_to_router()
        devices = parse_response(response)
    except Exception as e:
        logging.error(f"デバイスリスト取得エラー: {e}")
    
    return devices
```

### コミットメッセージ

良い例：
```
WiFi接続監視機能を追加

- 新規接続デバイスの検出機能を実装
- メール通知機能を追加
- 設定ファイルのサンプルを作成
```

悪い例（英語）：
```
Add WiFi monitoring feature

- Implement new device detection
- Add email notification
- Create config sample
```

### ドキュメント

すべてのMarkdownファイルは日本語で記述してください：
- README.md
- CONTRIBUTING.md
- QUICKSTART.md
- CUSTOMIZATION.md
- その他すべての.mdファイル

## Pull Request とコメント

### Pull Request説明

```markdown
## 変更概要

Atermルータの接続監視とメール通知機能を実装しました。

## 主な変更点

- `wifi_notifier.py`: メイン監視スクリプト
- `config.example.json`: 設定ファイルのサンプル
- `README.md`: 使用方法の説明

## テスト

- 基本的な動作確認を実施
- SMTP送信テストを実施
```

### コメント返信

コメントへの返信も日本語で行ってください：

```markdown
ご指摘ありがとうございます。
ログ出力の初期化順序を修正しました。

コミット: abc1234
```

## 品質基準

1. すべての出力が日本語であることを確認
2. 技術的な正確性を維持
3. ユーザーフレンドリーな説明を提供
4. 日本のルータユーザーに適した内容

このガイドラインに従って、すべての作業を日本語で実施してください。
