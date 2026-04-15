# クイックスタートガイド

このガイドでは、最も簡単な方法でWiFi Client Notifierをセットアップして実行する手順を説明します。

## 前提条件

- Python 3.11以上がインストールされている
- メール送信用のSMTPサーバーアクセス（Gmailなど）
- **ARPスキャンモード（推奨）**: root権限（直接実行時は`sudo`）、またはsystemdの`CAP_NET_RAW`設定
- **ルータAPIモード**: WiFiルータの管理者権限（ユーザー名とパスワード）

## セットアップ手順

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

`config.yaml`を編集して以下を設定します。

#### ARPスキャンモード（Raspberry Pi / ローカルネットワーク向け・推奨）

```yaml
detection_method: "arp"

arp:
  # サブネットは省略すると自動検出されます
  # subnet: "192.168.1.0/24"
  # Raspberry Pi Zero 2 W の WiFiインターフェース
  # interface: "wlan0"
  timeout: 2

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "your_email@gmail.com"
  smtp_password: "your_app_password"
  sender_email: "your_email@gmail.com"
  recipient_emails:
    - "notify_recipient@example.com"
  use_tls: true
```

#### ルータAPIモード（GitHub Actions向け）

```yaml
detection_method: "router"

router:
  ip: "192.168.10.1"
  username: "admin"
  password: "your_router_password"

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "your_email@gmail.com"
  smtp_password: "your_app_password"
  sender_email: "your_email@gmail.com"
  recipient_emails:
    - "notify_recipient@example.com"
  use_tls: true
```

**オプション項目:**
- `monitored_devices`: 監視したい特定のMACアドレスのリスト（空の場合は全デバイスを通知）
- `check_interval`: チェック間隔（秒）、デフォルトは60秒

### ステップ4: 設定をテスト

```bash
# ARPスキャンモードの場合はsudoが必要
sudo python src/test_config.py config.yaml
```

このコマンドで以下を確認:
- ✓ 設定ファイルが正しく読み込めるか
- ✓ ARPスキャン（またはルータ接続）が成功するか
- ✓ SMTP認証が成功するか
- オプションでテストメールを送信

### ステップ5: 実行

**テスト実行（フォアグラウンド）:**
```bash
# ARPスキャンモードはroot権限が必要
sudo python src/wifi_notifier.py config.yaml
```

Ctrl+Cで停止できます。

**バックグラウンド実行（推奨）:**

Linux / Raspberry Pi:
```bash
sudo nohup python src/wifi_notifier.py config.yaml &
```

## Raspberry Pi Zero 2 Wでの常時稼働セットアップ

Raspberry Pi Zero 2 WでWi-Fi接続監視を常時稼働させる手順です。

### systemdサービスとして登録

1. `config/wifi-notifier.service`を編集（`<YOUR_USER>`、`<YOUR_GROUP>`、パスを実際の値に置き換え）:
```ini
[Service]
User=<YOUR_USER>
Group=<YOUR_GROUP>
WorkingDirectory=/path/to/wifi-client-notifier
ExecStart=/usr/bin/python3 /path/to/wifi-client-notifier/src/wifi_notifier.py /path/to/config.yaml
# ARPスキャン用ケーパビリティ（root不要）
AmbientCapabilities=CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_RAW
```

2. サービスを有効化:
```bash
sudo cp config/wifi-notifier.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wifi-notifier
sudo systemctl start wifi-notifier
```

3. 動作確認:
```bash
sudo systemctl status wifi-notifier
sudo journalctl -u wifi-notifier -f
```

## Gmailの設定（推奨）

Gmailを使用する場合の手順:

1. Googleアカウントで2段階認証を有効化
   - https://myaccount.google.com/security

2. アプリパスワードを生成
   - https://myaccount.google.com/apppasswords
   - アプリ: "その他（カスタム名）"
   - 名前: "WiFi Notifier"

3. 生成された16文字のパスワードを`config.yaml`の`email.smtp_password`に設定

## トラブルシューティング

### ARPスキャンが失敗する

1. 直接実行の場合: root権限で実行しているか確認（`sudo python ...`）
2. systemdサービスの場合: `AmbientCapabilities=CAP_NET_RAW` が設定されているか確認
3. scapyがインストールされているか確認（`pip install scapy`）
4. ネットワークインターフェース名を確認（`ip addr` または `ifconfig`）
5. `config.yaml`の`arp.interface`にインターフェース名を明示的に設定

### ルータに接続できない（ルータAPIモード）

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
3. ARPスキャンモードの場合: サブネットが正しいか確認

## 次のステップ

- **長期運用**: systemdサービスで常時稼働させる（README.md参照）
- **カスタマイズ**: 特定のデバイスのみ監視、チェック間隔の調整など
- **ルータAPIモードのカスタマイズ**: `CUSTOMIZATION.md`でルータ固有の設定を確認

## サポート

問題が発生した場合は、GitHubのIssueで報告してください:
https://github.com/Kento-E/wifi-client-notifier/issues

以下の情報を含めてください:
- 使用している検出方式（ARPスキャンまたはルータAPI）
- WiFiルータのモデル名（ルータAPIモードの場合）
- エラーメッセージやログ
- 実行環境（OS、Pythonバージョン、Raspberry Piモデルなど）
