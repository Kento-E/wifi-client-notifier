# 正しいPRタイトルと説明

このファイルは、現在のPRで使用すべき正しい日本語のタイトルと説明を記載しています。

## PRタイトル（日本語版）

```
Atermルータ用セルフホスト型WiFi接続通知ツール
```

## PR説明（日本語版）

```markdown
## 変更概要

NECのAtermステーション通知サービス終了に伴い、AtermルータのWiFi接続を監視し、SMTP経由でメール通知を送信するセルフホスト型Pythonソリューションを実装しました。

## 主な実装内容

- **`wifi_notifier.py`** - ルータポーリング、デバイス追跡、SMTP通知を行うメイン監視スクリプト
- **`aterm_scraper.py`** - 複数のルータレスポンス形式に対応したHTML/JSONパーサー
- **`test_config.py`** - ルータ接続とSMTP設定を検証するテストツール
- **`demo.py`** - ルータアクセスなしでメール通知をテストするデモスクリプト

## 設定方法

JSON形式の設定ファイルで以下を指定：

```json
{
  "router": {"ip": "192.168.10.1", "username": "admin", "password": "..."},
  "email": {"smtp_server": "smtp.gmail.com", "smtp_port": 587, ...},
  "monitored_devices": ["AA:BB:CC:DD:EE:FF"],
  "check_interval": 60
}
```

## デプロイオプション

- Pythonスクリプト単体実行
- systemdサービス（`wifi-notifier.service`）
- Docker/docker-compose

## ドキュメント（日本語）

- **QUICKSTART.md** - 5ステップセットアップガイド
- **CUSTOMIZATION.md** - ルータモデル別カスタマイズガイド（ログイン方法、エンドポイントURL、レスポンス解析）
- **CONTRIBUTING.md** - デバイス互換性報告ガイド

## 認証方式

デフォルト実装は古いAtermモデル向けにMD5ハッシュを使用。カスタマイズガイドにSHA-256やBasic認証のバリエーションも記載。

## エージェント指示書

- **`.github/agents/`** - AIエージェント用の指示ファイル。コミットメッセージ、コードコメント、ドキュメント、PR/Issue説明がすべて日本語で生成されるよう設定（日本のAtermルータユーザー向け）
```

## 使用方法

GitHubのPR編集画面で、上記の日本語タイトルと説明に置き換えてください。
