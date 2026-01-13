# GitHub Actions Secrets設定ガイド

このドキュメントでは、GitHub Actions SecretsとWorkflowを使用してWiFi接続通知を実行する方法を説明します。

## 概要

GitHub Actions Secretsを使用することで、設定ファイルに秘匿情報（パスワードなど）を直接書き込むことなく、安全にWiFi監視を実行できます。

## メリット

- 🔒 **セキュリティ**: パスワードなどの秘匿情報がリポジトリに保存されない
- 🔄 **自動実行**: スケジュールに従って自動的に監視を実行
- 📊 **ログ管理**: GitHub Actionsでログを確認可能
- 🚀 **簡単な更新**: Secretsの値を変更するだけで設定を更新

## セットアップ手順

### ステップ1: GitHub Secretsを設定

1. GitHubリポジトリページを開く
2. `Settings` → `Secrets and variables` → `Actions` に移動
3. `New repository secret` をクリック
4. 以下のSecretsを追加:

#### 必須のSecrets

| Secret名 | 説明 | 例 |
|---------|------|-----|
| `ROUTER_IP` | ルータのIPアドレス | `192.168.10.1` |
| `ROUTER_USERNAME` | ルータの管理者ユーザー名 | `admin` |
| `ROUTER_PASSWORD` | ルータの管理者パスワード | `your_password` |
| `SMTP_SERVER` | SMTPサーバーアドレス | `smtp.gmail.com` |
| `SMTP_PORT` | SMTPポート番号 | `587` |
| `SMTP_USER` | SMTPユーザー名 | `your_email@gmail.com` |
| `SMTP_PASSWORD` | SMTPパスワード（Gmailの場合はアプリパスワード） | `abcd efgh ijkl mnop` |
| `SENDER_EMAIL` | 送信元メールアドレス | `your_email@gmail.com` |
| `RECIPIENT_EMAILS` | 受信者メールアドレス（カンマ区切り） | `user1@example.com,user2@example.com` |

#### オプションのSecrets

| Secret名 | 説明 | デフォルト値 |
|---------|------|------------|
| `MONITORED_DEVICES` | 監視対象MACアドレス（カンマ区切り、空なら全デバイス） | （空） |

#### オプションのVariables（Secretsではなく Variables として設定）

| Variable名 | 説明 | デフォルト値 |
|-----------|------|------------|
| `CHECK_INTERVAL` | チェック間隔（秒） | `60` |
| `LOG_LEVEL` | ログレベル | `INFO` |

### ステップ2: Workflowの実行スケジュールを調整（オプション）

`.github/workflows/wifi-monitor.yml` ファイルのcron設定を変更して、実行頻度を調整できます：

```yaml
on:
  schedule:
    # 毎時実行
    - cron: '0 * * * *'
    
    # 30分ごとに実行
    # - cron: '*/30 * * * *'
    
    # 毎日午前9時に実行
    # - cron: '0 9 * * *'
```

### ステップ3: Workflowを有効化

1. リポジトリの `Actions` タブに移動
2. Workflowを有効化（初回のみ）
3. `WiFi接続監視` Workflowを選択
4. `Run workflow` をクリックして手動実行し、動作を確認

## 動作の仕組み

### Workflow実行フロー

```
1. スケジュールまたは手動でトリガー
   ↓
2. Ubuntu環境をセットアップ
   ↓
3. リポジトリをチェックアウト
   ↓
4. Pythonと依存パッケージをインストール
   ↓
5. Secretsから config.yaml を生成
   ↓
6. WiFi監視を1回実行（--single-run モード）
   ↓
7. 新規デバイスがあれば通知メール送信
   ↓
8. ログをアップロード（エラー時のみ）
```

### シングルランモード

GitHub Actions用に `--single-run` フラグが実装されています：

```bash
# 通常モード（継続的に監視）
python src/wifi_notifier.py config.yaml

# シングルランモード（1回だけチェック）
python src/wifi_notifier.py config.yaml --single-run
```

シングルランモードでは：
- ルータにログイン
- 現在接続中のデバイスをチェック
- 新規デバイスがあれば通知
- 即座に終了

## トラブルシューティング

### Secretsが読み込まれない

- Secret名のスペルを確認
- Secretsページで値が正しく設定されているか確認
- Workflow実行ログで環境変数が設定されているか確認

### ルータにアクセスできない

- GitHub ActionsランナーからルータのIPアドレスにアクセス可能か確認
- ルータがインターネットからアクセス可能な場合のみ動作します
- プライベートネットワーク内のルータには**アクセスできません**

**重要**: このWorkflowは、ルータがパブリックIPを持つか、VPN経由でアクセス可能な場合のみ機能します。

### プライベートネットワークで使用する場合

プライベートネットワーク内のルータを監視する場合は、以下の選択肢があります：

#### 1. セルフホストランナーを使用する（推奨）

**セルフホストランナーとは？**

セルフホストランナーは、あなたが管理する環境（ローカルマシン、サーバー、Raspberry Piなど）でGitHub Actions Workflowを実行するための仕組みです。GitHub提供のクラウドランナーではなく、自分の環境で実行できるため、プライベートネットワーク内のルータにもアクセスできます。

**セットアップ方法:**

1. GitHubリポジトリの `Settings` → `Actions` → `Runners` に移動
2. `New self-hosted runner` をクリック
3. OSを選択（Linux、macOS、Windows）
4. 表示される手順に従ってランナーをセットアップ:
   ```bash
   # 例: Linux環境での手順
   mkdir actions-runner && cd actions-runner
   curl -o actions-runner-linux-x64-2.xxx.x.tar.gz -L https://github.com/actions/runner/releases/download/v2.xxx.x/actions-runner-linux-x64-2.xxx.x.tar.gz
   tar xzf ./actions-runner-linux-x64-2.xxx.x.tar.gz
   ./config.sh --url https://github.com/あなたのユーザー名/wifi-client-notifier --token あなたのトークン
   ./run.sh
   ```
5. `.github/workflows/wifi-monitor.yml` を編集:
   ```yaml
   runs-on: self-hosted  # ubuntu-latest から変更
   ```

**メリット:**
- プライベートネットワーク内のルータにアクセス可能
- GitHub Actionsの自動実行機能を活用できる
- ログや実行履歴をGitHubで管理可能

**デメリット:**
- ランナーを常時稼働させる必要がある
- セットアップと管理が必要

**注記:** セルフホストランナー自体はGitHub Actionsの機能であり、Workflowで利用できます。`.github/workflows/wifi-monitor.yml`でランナーの種類を指定するだけで使用できます。

#### 2. ローカル実行（シンプルな方法）

GitHub Actionsを使わず、ローカルマシンやルータ上で直接実行:
- systemdサービスやcronで定期実行
- 詳細はREADME.mdの「使用方法」セクションを参照

## セキュリティベストプラクティス

### ✅ 推奨

- Secretsを使用してすべての秘匿情報を管理
- 定期的にパスワードを変更
- Gmailの場合は必ずアプリパスワードを使用
- ログレベルを`INFO`または`WARNING`に設定（`DEBUG`は避ける）

### ❌ 避けるべきこと

- config.yamlファイルに直接パスワードを記載してコミット
- Secretsの値をログに出力
- 本番用パスワードを共有リポジトリで使用

## 参考リンク

- [GitHub Actions Documentation](https://docs.github.com/ja/actions)
- [GitHub Secrets](https://docs.github.com/ja/actions/security-guides/encrypted-secrets)
- [Cron式ジェネレーター](https://crontab.guru/)

## サポート

問題が発生した場合は、GitHubのIssueで報告してください。
