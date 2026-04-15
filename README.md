# wifi-client-notifier

Wi-Fi接続検知ツール

## 概要

ローカルネットワークに接続した端末を検出し、メール通知を送信するPythonスクリプトです。

**Raspberry Pi Zero 2 W** などのローカルネットワーク上のホストで常時稼働させることを想定しており、
同じWi-Fi環境に新しい端末が接続してきたときに自動でSMTPメール通知を送ります。

メーカー提供のルータ管理通知サービスの終了に伴い、
同様の機能を自前で実現するために開発されたツールです。

**📖 すぐに始めたい方は [クイックスタートガイド](docs/QUICKSTART.md) をご覧ください。**

**☁️ GitHub Actionsで自動実行したい方は [GitHub Actions設定ガイド](docs/GITHUB_ACTIONS.md) をご覧ください。**

## プロジェクト構成

```
wifi-client-notifier/
├── src/                      # ソースコード
│   ├── wifi_notifier.py      # メイン監視スクリプト
│   ├── arp_scanner.py        # ARPスキャナー（Raspberry Pi向け）
│   ├── html_parser.py        # HTML/JSONパーサー
│   ├── test_config.py        # 設定テストツール
│   └── demo.py               # デモスクリプト
├── docs/                     # ドキュメント
│   ├── QUICKSTART.md         # クイックスタート
│   ├── GITHUB_ACTIONS.md     # GitHub Actions設定ガイド
│   └── CUSTOMIZATION.md      # カスタマイズガイド
├── config/                   # 設定ファイル
│   ├── config.example.yaml   # 設定例
│   └── wifi-notifier.service # systemdサービスファイル
├── deployment/               # デプロイ関連
│   ├── Dockerfile            # Dockerイメージ
│   ├── docker-compose.yml    # Docker Compose設定
│   └── setup.sh              # セットアップスクリプト
├── scripts/                  # ユーティリティスクリプト
│   └── generate_config.py    # GitHub Actions用設定生成
└── .github/                  # GitHub設定
    ├── workflows/            # GitHub Actionsワークフロー
    └── instructions/         # Copilot用途別指示書
```

## 主な機能

- **ARPスキャン**によるローカルネットワーク上の接続端末の監視（Raspberry Pi向け）
- ルータ管理APIを使用した接続端末の監視（GitHub Actions向け）
- 新規WiFi接続の検出とSMTPメール通知
- 特定MACアドレスのフィルタリング（オプション）
- ログ出力（ファイル＋コンソール）

## 検出方式

| 方式          | 説明                                      | 必要なもの                                                       |
| ------------- | ----------------------------------------- | ---------------------------------------------------------------- |
| `arp`（推奨） | ARPスキャンによるローカルネットワーク監視 | root権限（直接実行時）またはCAP_NET_RAWケーパビリティ（systemd） |
| `router`      | ルータ管理APIを使用した接続監視           | ルータの管理者パスワード                                         |

`config.yaml` の `detection_method` で切り替えられます。

## 必要要件

- Python 3.11以上
- SMTPサーバーへのアクセス（Gmail、独自SMTPサーバーなど）
- **ARPスキャンモード**: root権限（直接実行時は`sudo`）またはCAP_NET_RAWケーパビリティ（systemd）、scapy（`pip install scapy`）
- **ルータAPIモード**: WiFiルータへのアクセス権限（管理者ユーザー名とパスワード）

## インストール

1. リポジトリをクローン:

```bash
git clone https://github.com/Kento-E/wifi-client-notifier.git
cd wifi-client-notifier
```

2. 依存パッケージをインストール:

```bash
pip install -r requirements.txt
```

**開発環境のセットアップ**: コードの修正や機能追加を行う場合は、[deployment/README.md](deployment/README.md) を参照してください。

## 設定

1. サンプル設定ファイルをコピー:

```bash
cp config/config.example.yaml config.yaml
```

2. `config.yaml`を編集して、環境に合わせて設定してください。

設定項目の詳細は `config/config.example.yaml` を参照してください。

3. 設定をテスト:

```bash
# ARPスキャンモードの場合はsudoが必要
sudo python src/test_config.py config.yaml
```

このテストスクリプトは以下を確認します：

- 設定ファイルの読み込み
- ARPスキャンまたはルータへの接続
- SMTP認証
- テストメールの送信（オプション）

### Gmail設定の注意事項

Gmailを使用する場合：

1. Googleアカウントで2段階認証を有効化
2. アプリパスワードを生成（<https://myaccount.google.com/apppasswords）>
3. 生成したアプリパスワードを`smtp_password`に設定

## 使用方法

### Raspberry Pi Zero 2 Wでの実行（推奨）

ARPスキャンモードではroot権限またはCAP_NET_RAWケーパビリティが必要です。
直接実行する場合は`sudo`を使用してください:

```bash
sudo python src/wifi_notifier.py config.yaml
```

常時稼働させる場合はsystemdサービスの利用を推奨します（rootユーザー不要、詳細は後述）。

### バックグラウンドで実行（Linux/Mac）

```bash
sudo nohup python src/wifi_notifier.py config.yaml &
```

### Dockerで実行

1. config.yamlを作成して設定を入力

2. Dockerイメージをビルド:

```bash
docker-compose build
```

3. コンテナを起動:

```bash
docker-compose up -d
```

4. ログを確認:

```bash
docker-compose logs -f
```

5. コンテナを停止:

```bash
docker-compose down
```

### systemdサービスとして実行（Linux / Raspberry Pi）

1. サービスファイルをカスタマイズ:

`config/wifi-notifier.service`ファイルを編集し、以下を実際の値に置き換えます：

- `<YOUR_USER>`: 実行ユーザー名（専用の非rootユーザーを推奨）
- `<YOUR_GROUP>`: 実行グループ名
- `/path/to/wifi-client-notifier`: このリポジトリのパス

ARPスキャンモードでは `AmbientCapabilities=CAP_NET_RAW` が設定済みのため、rootユーザーは不要です。

`ExecStart` は仮想環境の Python と `config/config.yaml` を指すように設定してください。

2. サービスファイルをコピー:

```bash
sudo cp config/wifi-notifier.service /etc/systemd/system/
```

3. サービスを有効化して起動:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wifi-notifier
sudo systemctl start wifi-notifier
sudo systemctl status wifi-notifier
```

4. ログを確認:

```bash
sudo journalctl -u wifi-notifier -f
```

## ルータモデルごとのカスタマイズ（ルータAPIモード使用時）

`detection_method: "router"` を使用する場合のみ必要です。

ご使用のWiFiルータモデルによっては、
`src/wifi_notifier.py`の`WiFiRouter`クラスをカスタマイズする必要がある場合があります。

詳細は [カスタマイズガイド](docs/CUSTOMIZATION.md) をご覧ください。

特に以下のメソッドを確認してください：

- `login()`: 認証方法がモデルにより異なる場合があります
- `get_connected_devices()`: デバイスリスト取得のエンドポイントやパース方法

ルータの管理画面でブラウザの開発者ツールを使用してネットワークリクエストを確認し、
適切なエンドポイントとパラメータを特定してください。

## トラブルシューティング

### ARPスキャンができない

- 直接実行の場合: root権限で実行しているか確認（`sudo python ...`）
- systemdサービスの場合: `AmbientCapabilities=CAP_NET_RAW` が設定されているか確認
- scapyがインストールされているか確認（`pip install scapy`）
- ネットワークインターフェース名を確認（`ip addr`コマンドで確認）
- `config.yaml` の `arp.interface` に正しいインターフェース名（例: `wlan0`）を設定

### ルータにログインできない（ルータAPIモード）

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
- ARPスキャンモードの場合: サブネットが正しいか確認（自動検出または手動設定）
- ルータAPIモードの場合: `get_connected_devices()`メソッドのカスタマイズが必要な場合があります

## 免責事項

このツールは非公式なものであり、ルータメーカーとは一切関係ありません。
使用は自己責任でお願いします。
