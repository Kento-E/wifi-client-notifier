# wifi-client-notifier
Wi-Fi接続検知ツール

## 概要

WiFiルータに無線接続した端末を検出し、メール通知を送信するPythonスクリプトです。

メーカー提供のルータ管理通知サービスの終了に伴い、
同様の機能を自前で実現するために開発されたツールです。

**📖 すぐに始めたい方は [クイックスタートガイド](docs/QUICKSTART.md) をご覧ください。**

**☁️ GitHub Actionsで自動実行したい方は [GitHub Actions設定ガイド](docs/GITHUB_ACTIONS.md) をご覧ください。**

## プロジェクト構成

```
wifi-client-notifier/
├── src/                      # ソースコード
│   ├── wifi_notifier.py      # メイン監視スクリプト
│   ├── html_parser.py        # HTML/JSONパーサー
│   ├── test_config.py        # 設定テストツール
│   └── demo.py               # デモスクリプト
├── docs/                     # ドキュメント
│   ├── QUICKSTART.md         # クイックスタート
│   ├── GITHUB_ACTIONS.md     # GitHub Actions設定ガイド
│   ├── CUSTOMIZATION.md      # カスタマイズガイド
│   ├── CONTRIBUTING.md       # 貢献ガイドライン
│   └── AUTO_CLOSE_ISSUES.md  # イシュー自動クローズガイド
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

- WiFiルータへの定期的なアクセスによる接続端末の監視
- 新規WiFi接続の検出
- SMTPによるメール通知
- 特定MACアドレスのフィルタリング（オプション）
- ログ出力

## 必要要件

- Python 3.11以上
- WiFiルータへのアクセス権限（管理者ユーザー名とパスワード）
- SMTPサーバーへのアクセス（Gmail、独自SMTPサーバーなど）

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

## 設定

1. サンプル設定ファイルをコピー:
```bash
cp config/config.example.yaml config.yaml
```

2. `config.yaml`を編集して、環境に合わせて設定してください。

設定項目の詳細は `config/config.example.yaml` を参照してください。

3. 設定をテスト:

```bash
python src/test_config.py config.yaml
```

このテストスクリプトは以下を確認します：
- 設定ファイルの読み込み
- ルータへの接続
- SMTP認証
- テストメールの送信（オプション）

### Gmail設定の注意事項

Gmailを使用する場合：
1. Googleアカウントで2段階認証を有効化
2. アプリパスワードを生成（https://myaccount.google.com/apppasswords）
3. 生成したアプリパスワードを`smtp_password`に設定

## 使用方法

### 基本的な使用

```bash
python src/wifi_notifier.py config.yaml
```

### バックグラウンドで実行（Linux/Mac）

```bash
nohup python src/wifi_notifier.py config.yaml &
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

### systemdサービスとして実行（Linux）

1. サービスファイルをカスタマイズ:

`config/wifi-notifier.service`ファイルを編集し、以下を実際のパスに置き換えます：
- `your_user`: 実行ユーザー名
- `your_group`: 実行グループ名
- `/path/to/wifi-client-notifier`: このリポジトリのパス

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

## ルータモデルごとのカスタマイズ

このスクリプトは汎用的な実装となっています。ご使用のWiFiルータモデルによっては、
`src/wifi_notifier.py`の`WiFiRouter`クラスをカスタマイズする必要がある場合があります。

詳細は [カスタマイズガイド](docs/CUSTOMIZATION.md) をご覧ください。

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

**PRを作成する際は、関連するイシューがある場合は `Closes #番号` でリンクしてください。** 詳細は [イシュー自動クローズガイド](docs/AUTO_CLOSE_ISSUES.md) を参照してください。

詳細な貢献方法については [CONTRIBUTING.md](docs/CONTRIBUTING.md) をご覧ください。

### 開発環境のセットアップ

コード品質を維持するため、linterとフォーマッターを使用しています。

**自動セットアップ（推奨）:**

```bash
# セットアップスクリプトで自動的にインストール・設定
./deployment/setup.sh
```

このスクリプトは依存パッケージのインストールとpre-commitフックの設定を自動で行います。

**手動セットアップ:**

```bash
# 開発用ツールをインストール
pip install black flake8 pre-commit

# pre-commitフックをインストール（コミット時に自動整形）
pre-commit install

# 手動でコードをフォーマット
black src/

# 手動でlintチェック
flake8 src/
```

## 免責事項

このツールは非公式なものであり、ルータメーカーとは一切関係ありません。
使用は自己責任でお願いします。
