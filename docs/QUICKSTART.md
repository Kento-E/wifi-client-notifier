# クイックスタートガイド

このガイドでは、最も簡単な方法でWiFi Client Notifierをセットアップして実行する手順を説明します。

## 前提条件

- Python 3.7以上がインストールされている
- WiFiルータの管理者権限（ユーザー名とパスワード）
- メール送信用のSMTPサーバーアクセス（Gmailなど）

## 5ステップでセットアップ

### ステップ1: リポジトリをクローン

```bash
git clone https://github.com/Kento-E/wifi-client-notifier.git
cd wifi-client-notifier
```

### ステップ2: 依存パッケージをインストール

```bash
./deployment/setup.sh
```

または手動で:
```bash
pip install -r requirements.txt
```

### ステップ3: 設定ファイルを作成

```bash
cp config/config.example.yaml config.yaml
```

`config.yaml`を編集して以下を設定:

**必須項目:**
- `router.ip`: ルータのIPアドレス（例: 192.168.10.1）
- `router.username`: 管理者ユーザー名（通常は "admin"）
- `router.password`: 管理者パスワード
- `email.smtp_server`: SMTPサーバー（Gmail: smtp.gmail.com）
- `email.smtp_port`: SMTPポート（Gmail: 587）
- `email.smtp_user`: メールアドレス
- `email.smtp_password`: SMTPパスワード（Gmailの場合はアプリパスワード）
- `email.sender_email`: 送信元メールアドレス
- `email.recipient_emails`: 通知先メールアドレスのリスト

**オプション:**
- `monitored_devices`: 監視したい特定のMACアドレス（空の場合は全デバイス）
- `check_interval`: チェック間隔（秒）、デフォルトは60秒

### ステップ4: 設定をテスト

```bash
python src/test_config.py config.yaml
```

このコマンドで以下を確認:
- ✓ 設定ファイルが正しく読み込めるか
- ✓ ルータに接続できるか
- ✓ SMTP認証が成功するか
- オプションでテストメールを送信

### ステップ5: 実行

**テスト実行（フォアグラウンド）:**
```bash
python src/wifi_notifier.py config.yaml
```

Ctrl+Cで停止できます。

**バックグラウンド実行（推奨）:**

Linux/Mac:
```bash
nohup python src/wifi_notifier.py config.yaml &
```

または、Docker:
```bash
docker-compose up -d
```

## Gmailの設定（推奨）

Gmailを使用する場合の手順:

1. Googleアカウントで2段階認証を有効化
   - https://myaccount.google.com/security

2. アプリパスワードを生成
   - https://myaccount.google.com/apppasswords
   - アプリ: "その他（カスタム名）"
   - 名前: "WiFi Notifier"

3. 生成された16文字のパスワードを`config.yaml`の`password`フィールド（email配下）に設定

4. 設定例:
```yaml
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  username: "your_email@gmail.com"
  password: "abcd efgh ijkl mnop"
  from: "your_email@gmail.com"
  to: "recipient@example.com"
```

## トラブルシューティング

### ルータに接続できない

1. ブラウザでルータの管理画面にアクセスできるか確認
2. IPアドレス、ユーザー名、パスワードを再確認
3. ルータモデルによってはカスタマイズが必要 → `CUSTOMIZATION.md`参照

### メール送信できない

1. SMTP設定を再確認
2. Gmailの場合、アプリパスワードを使用しているか確認
3. ファイアウォール設定を確認

### デバイスが検出されない

1. ログファイル（`wifi_notifier.log`）を確認
2. `config.yaml`の`log_level`を`"DEBUG"`に変更して詳細ログを取得
3. ルータモデル固有の設定が必要な場合 → `CUSTOMIZATION.md`参照

## 次のステップ

- **長期運用**: systemdサービスまたはDockerで常時稼働させる（README.md参照）
- **カスタマイズ**: 特定のデバイスのみ監視、チェック間隔の調整など
- **トラブル対応**: `CUSTOMIZATION.md`でルータ固有の設定を確認

## サポート

問題が発生した場合は、GitHubのIssueで報告してください:
https://github.com/Kento-E/wifi-client-notifier/issues

以下の情報を含めてください:
- WiFiルータのモデル名
- エラーメッセージやログ
- 実行環境（OS、Pythonバージョン）
