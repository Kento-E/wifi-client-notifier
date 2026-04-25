# wifi-client-notifier

Wi-Fi接続検知ツール

## 概要

ローカルネットワークに接続した端末を検出し、メール通知を送信するPythonスクリプトです。

**Raspberry Pi Zero 2 W** などのローカルネットワーク上のホストで常時稼働させることを想定しており、
同じWi-Fi環境に新しい端末が接続してきたときに自動でSMTPメール通知を送ります。

メーカー提供のルータ管理通知サービスの終了に伴い、
同様の機能を自前で実現するために開発されたツールです。

**📖 すぐに始めたい方は本READMEの「クイックスタート」から開始してください。**

## プロジェクト構成

```text
wifi-client-notifier/
├── src/                      # ソースコード
│   ├── wifi_notifier.py      # メイン監視スクリプト
│   ├── arp_scanner.py        # ARPスキャナー（Raspberry Pi向け）
│   ├── html_parser.py        # HTML/JSONパーサー
│   ├── test_config.py        # 設定テストツール
│   └── demo.py               # デモスクリプト
├── docs/                     # ドキュメント
│   └── CUSTOMIZATION.md      # カスタマイズガイド
├── config/                   # 設定ファイル
│   ├── config.example.yaml   # 設定例
│   └── wifi-notifier.service # systemdサービスファイル
├── deployment/               # デプロイ関連
│   ├── Dockerfile            # Dockerイメージ
│   ├── docker-compose.yml    # Docker Compose設定
│   └── setup.sh              # セットアップスクリプト
└── .github/                  # GitHub設定
    ├── workflows/            # CI/自動化ワークフロー
    └── instructions/         # Copilot用途別指示書
```

## 主な機能

- **ARPスキャン**によるローカルネットワーク上の接続端末の監視（Raspberry Pi向け）
- ルータ管理APIを使用した接続端末の監視
- 新規WiFi接続の検出とSMTPメール通知
- Googleカレンダーへの予定自動登録通知（任意）
- 特定MACアドレスの再通知制御と未知端末の初回通知
- ログ出力（ファイル＋コンソール）

## 検出方式

- `arp`（推奨）: ARPスキャンによるローカルネットワーク監視。
    必要なものは root権限（直接実行時）またはCAP_NET_RAWケーパビリティ（systemd）。
- `router`: ルータ管理APIを使用した接続監視。
    必要なものはルータの管理者パスワード。

`config.yaml` の `detection_method` で切り替えられます。

## 必要要件

- Python 3.11以上
- SMTPサーバーへのアクセス（Gmail、独自SMTPサーバーなど）
- Googleカレンダー通知を使う場合: サービスアカウントJSON、対象カレンダーの共有設定
- **ARPスキャンモード**:
    root権限（直接実行時は`sudo`）またはCAP_NET_RAWケーパビリティ（systemd）、
    scapy（`pip install scapy`）
- **ルータAPIモード**: WiFiルータへのアクセス権限（管理者ユーザー名とパスワード）

## クイックスタート

最短で動かす場合は、以下の5ステップだけ実施してください。

1. リポジトリを取得して依存パッケージをインストール

```bash
git clone https://github.com/Kento-E/wifi-client-notifier.git
cd wifi-client-notifier
pip install -r requirements.txt
```

1. 設定ファイルを作成

```bash
cp config/config.example.yaml config.yaml
```

1. `config.yaml` の最小必須項目を設定

- `detection_method`: `arp` または `router`
- `email`: SMTPサーバー、ユーザー、パスワード、送受信先
- Googleカレンダー利用時は `google_calendar.credentials_file` と `calendar_id`

1. 設定テストを実行（ARPモードはsudo推奨）

```bash
sudo python src/test_config.py config.yaml
```

1. 監視を開始

```bash
sudo python src/wifi_notifier.py config.yaml
```

詳細な設定例や運用方法は、このまま下の「設定」「使用方法」「トラブルシューティング」を参照してください。

## インストール

1. リポジトリをクローン:

```bash
git clone https://github.com/Kento-E/wifi-client-notifier.git
cd wifi-client-notifier
```

1. 依存パッケージをインストール:

```bash
pip install -r requirements.txt
```

1. （開発者向け）コード品質チェックを有効化:

```bash
# コミット前の品質チェックを自動化
./scripts/setup_git_hooks.sh

# 手動チェック
./scripts/run_quality_checks.sh
```

本リポジトリでは、Pythonコードの整形を `black`、
静的チェックを `flake8`、Markdownチェックを `markdownlint-cli2` で統一しています。
開発時は [scripts/run_quality_checks.sh](scripts/run_quality_checks.sh) を実行し、
CIでも同じスクリプトで差分チェックを行います。
また、[scripts/setup_git_hooks.sh](scripts/setup_git_hooks.sh) を実行すると、
コミット前に同じ検証が自動実行されます。

**開発環境のセットアップ**: コードの修正や機能追加を行う場合は、[deployment/README.md](deployment/README.md) を参照してください。

## 設定

1. サンプル設定ファイルをコピー:

```bash
cp config/config.example.yaml config.yaml
```

1. `config.yaml`を編集して、環境に合わせて設定してください。

設定項目の詳細は `config/config.example.yaml` を参照してください。

通知制御の主な設定:

- `repeat_notification_devices`: この一覧に入れたMACアドレスだけ再通知対象にする
- `notify_unknown_devices_once`: 上記以外の端末を「未知の端末」として初回のみ通知する
- `monitored_devices`: 旧来の単純フィルタ設定。上記2項目を使わない場合のみ利用

Googleカレンダー通知の主な設定（任意）:

- `google_calendar.enabled`: `true` で有効化
- `google_calendar.credentials_file` または
    `google_calendar.credentials_file_env`: サービスアカウントJSONの配置先
- `google_calendar.calendar_id`: 登録先カレンダーID（専用カレンダー推奨）
- `google_calendar.max_retries` / `retry_delay_seconds`: API失敗時のリトライ制御
- `google_calendar.dedupe_window_minutes`: 重複登録防止の検索時間幅

Googleカレンダー通知を有効化する手順（推奨）:

1. Google Cloud でサービスアカウントを作成し、JSONキーをダウンロード
2. JSONを安全な場所へ配置（例: `/home/pi/secrets/google-service-account.json`）
3. `config.yaml` の `google_calendar.credentials_file` にその絶対パスを設定
4. 対象カレンダーをサービスアカウントのメールアドレスへ「予定の変更権限」で共有
5. `google_calendar.calendar_id` に対象カレンダーIDを設定

設定キー名の注意:

- 正しいキーは `credentials_file` です
- `credentails_file` は誤記のため認識されません
- 起動ログや通知メールに「Googleカレンダー通知の初期化に失敗」と出た場合は、まずキー名とパスを確認してください

1. 設定をテスト:

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
1. アプリパスワードを生成（<https://myaccount.google.com/apppasswords）>
1. 生成したアプリパスワードを`smtp_password`に設定

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

1. Dockerイメージをビルド:

```bash
docker-compose build
```

1. コンテナを起動:

```bash
docker-compose up -d
```

1. ログを確認:

```bash
docker-compose logs -f
```

1. コンテナを停止:

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

1. サービスファイルをコピー:

```bash
sudo cp config/wifi-notifier.service /etc/systemd/system/
```

1. サービスを有効化して起動:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wifi-notifier
sudo systemctl start wifi-notifier
sudo systemctl status wifi-notifier
```

1. ログを確認:

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

### Googleカレンダーへ登録できない

- サービスアカウントJSONのパスが正しいか確認
- 登録先カレンダーをサービスアカウントへ共有済みか確認
- `google_calendar.calendar_id` が対象カレンダーIDと一致するか確認
- 設定キー名が `credentials_file` になっているか確認（`credentails_file` は誤記）
- 接続通知メール本文の「通知チャネル異常」にエラー詳細が出ていないか確認

### デバイスが検出されない

- ログファイルを確認
- ログレベルを`DEBUG`に変更して詳細情報を取得
- ARPスキャンモードの場合: サブネットが正しいか確認（自動検出または手動設定）
- ルータAPIモードの場合: `get_connected_devices()`メソッドのカスタマイズが必要な場合があります

### 再通知の条件を調整したい

- `repeat_notification_devices` に再通知したいMACアドレスを設定
- `notify_unknown_devices_once: true` で、それ以外を未知端末として初回のみ通知
- `notification_cool_down_minutes` と `reconnect_notify_after_minutes` で再通知の間隔を調整

## 免責事項

このツールは非公式なものであり、ルータメーカーとは一切関係ありません。
使用は自己責任でお願いします。
