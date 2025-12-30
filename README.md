# aterm-wifi-client-notifier
Wi-Fi接続検知ツール

## 概要

Atermルータに無線接続した端末を検出し、メール通知を送信するPythonスクリプトです。

NECのAtermステーション通知サービスの終了（https://www.aterm.jp/product/atermstation/info/2025/info0929.html）に伴い、
同様の機能を自前で実現するために開発されました。

## 主な機能

- Atermルータへの定期的なアクセスによる接続端末の監視
- 新規WiFi接続の検出
- SMTPによるメール通知
- 特定MACアドレスのフィルタリング（オプション）
- ログ出力

## 必要要件

- Python 3.7以上
- Atermルータへのアクセス権限（管理者ユーザー名とパスワード）
- SMTPサーバーへのアクセス（Gmail、独自SMTPサーバーなど）

## インストール

1. リポジトリをクローン:
```bash
git clone https://github.com/Kento-E/aterm-wifi-client-notifier.git
cd aterm-wifi-client-notifier
```

2. 依存パッケージをインストール:
```bash
pip install -r requirements.txt
```

## 設定

1. サンプル設定ファイルをコピー:
```bash
cp config.example.json config.json
```

2. `config.json`を編集して、環境に合わせて設定:

```json
{
  "router": {
    "ip": "192.168.10.1",           // ルータのIPアドレス
    "username": "admin",             // 管理者ユーザー名
    "password": "your_password"      // 管理者パスワード
  },
  "email": {
    "smtp_server": "smtp.gmail.com", // SMTPサーバー
    "smtp_port": 587,                 // SMTPポート
    "smtp_user": "your_email@gmail.com",
    "smtp_password": "your_app_password",  // アプリパスワード
    "sender_email": "your_email@gmail.com",
    "recipient_emails": [
      "notify@example.com"            // 通知先メールアドレス
    ],
    "use_tls": true
  },
  "monitored_devices": [              // 監視対象MACアドレス（空なら全デバイス）
    "AA:BB:CC:DD:EE:FF"
  ],
  "check_interval": 60,               // チェック間隔（秒）
  "log_level": "INFO",                // ログレベル
  "log_file": "wifi_notifier.log"    // ログファイル名
}
```

### Gmail設定の注意事項

Gmailを使用する場合：
1. Googleアカウントで2段階認証を有効化
2. アプリパスワードを生成（https://myaccount.google.com/apppasswords）
3. 生成したアプリパスワードを`smtp_password`に設定

## 使用方法

### 基本的な使用

```bash
python wifi_notifier.py config.json
```

### バックグラウンドで実行（Linux/Mac）

```bash
nohup python wifi_notifier.py config.json &
```

### systemdサービスとして実行（Linux）

1. サービスファイルを作成: `/etc/systemd/system/wifi-notifier.service`

```ini
[Unit]
Description=Aterm WiFi Client Notifier
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/aterm-wifi-client-notifier
ExecStart=/usr/bin/python3 /path/to/aterm-wifi-client-notifier/wifi_notifier.py /path/to/config.json
Restart=always

[Install]
WantedBy=multi-user.target
```

2. サービスを有効化して起動:

```bash
sudo systemctl enable wifi-notifier
sudo systemctl start wifi-notifier
sudo systemctl status wifi-notifier
```

## ルータモデルごとのカスタマイズ

このスクリプトは汎用的な実装となっています。ご使用のAtermルータモデルによっては、
`wifi_notifier.py`の`AtermRouter`クラスをカスタマイズする必要がある場合があります。

特に以下のメソッドを確認してください：
- `login()`: 認証方法がモデルにより異なる場合があります
- `get_connected_devices()`: デバイスリスト取得のエンドポイントやパース方法

ルータの管理画面でブラウザの開発者ツールを使用してネットワークリクエストを確認し、
適切なエンドポイントとパラメータを特定してください。

## トラブルシューティング

### ルータにログインできない

- ルータのIPアドレス、ユーザー名、パスワードを確認
- ルータの管理画面にブラウザでアクセスできるか確認
- ルータモデルに応じて`login()`メソッドのカスタマイズが必要な場合があります

### メール送信ができない

- SMTP設定を確認
- Gmailの場合、アプリパスワードを使用しているか確認
- ファイアウォールでSMTPポートが許可されているか確認

### デバイスが検出されない

- ログファイルを確認
- ログレベルを`DEBUG`に変更して詳細情報を取得
- ルータモデルに応じて`get_connected_devices()`メソッドのカスタマイズが必要な場合があります

## ライセンス

MIT License

## 貢献

Issue、Pull Requestを歓迎します。

## 免責事項

このツールは非公式なものであり、NEC及びAtermとは一切関係ありません。
使用は自己責任でお願いします。
