# Firebase Cloud Messaging 手動セットアップ手順

この手順では、WiFi Client Notifier から特定の Android 端末へ Firebase Cloud Messaging
で通知するための最低限の準備をまとめます。

## 前提

- Firebase プロジェクトを作成できる Google アカウントを持っている
- このリポジトリの `config/config.yaml` を編集できる
- Android 端末への通知受信アプリは
  [MCPTokenViewer](https://github.com/Kento-E/MCPTokenViewer) を使用します
  - ビルド・インストール・token 取得手順は MCPTokenViewer の README を参照してください

## 1. Firebase プロジェクトを作成する

1. Firebase コンソールを開く
   - <https://console.firebase.google.com/>
2. 「プロジェクトを追加」を選択する
3. 任意のプロジェクト名を設定して作成する
4. 作成後、プロジェクト設定でプロジェクト ID を控える

## 2. Firebase Cloud Messaging API を有効化する

1. Google Cloud コンソールで対象プロジェクトを開く
2. 「API とサービス」→「ライブラリ」を開く
3. 「Firebase Cloud Messaging API」を検索して有効化する

## 3. サービスアカウント JSON を作成する

1. Google Cloud コンソールで「IAM と管理」→「サービスアカウント」を開く
2. 通知用のサービスアカウントを作成する
3. 「キー」→「キーを追加」→「新しいキーを作成」から JSON をダウンロードする
4. 実行ホスト上の安全な場所へ配置する

例:

```bash
mkdir -p /home/pi/secrets
chmod 700 /home/pi/secrets
cp firebase-service-account.json /home/pi/secrets/
chmod 600 /home/pi/secrets/firebase-service-account.json
```

## 4. Android 端末の registration token を取得する

[MCPTokenViewer](https://github.com/Kento-E/MCPTokenViewer) を使用して token を取得します。
ビルド・インストール・token 確認の手順は MCPTokenViewer の README を参照してください。

取得した token を `firebase.registration_tokens` に設定します。

```yaml
firebase:
  enabled: true
  registration_tokens:
    - "ここに取得したtokenを貼り付け"
```

複数端末へ送る場合は token を行追加してください。

```yaml
firebase:
  registration_tokens:
    - "token_1"
    - "token_2"
```

運用上の注意:

- token は再生成されることがある
- アプリ再インストールや端末移行で token が変わることがある
- 古い token は送信失敗の原因になるので定期的に更新する

## 5. 環境変数を設定する

シェル実行の場合:

```bash
export FIREBASE_CREDENTIALS_FILE=/home/pi/secrets/firebase-service-account.json
```

systemd サービスの場合は [Service] セクションに追加します。

```ini
Environment="FIREBASE_CREDENTIALS_FILE=/home/pi/secrets/firebase-service-account.json"
```

## 6. config/config.yaml を更新する

例:

```yaml
firebase:
  enabled: true
  credentials_file_env: FIREBASE_CREDENTIALS_FILE
  project_id: your-firebase-project-id
  notification_title_prefix: WiFi通知
  timeout_seconds: 10
  registration_tokens:
    - your_android_device_registration_token
```

補足:

- メール通知も使うなら `email.enabled: true` のままでよい
- Firebase のみで運用するなら `email.enabled: false` にできる

## 7. 設定テストを実行する

```bash
FIREBASE_CREDENTIALS_FILE=/home/pi/secrets/firebase-service-account.json \
python src/test_config.py config/config.yaml
```

ARP モードで同時に確認する場合は `sudo` を付けてください。

```bash
FIREBASE_CREDENTIALS_FILE=/home/pi/secrets/firebase-service-account.json \
sudo -E python src/test_config.py config/config.yaml
```

このテストでは以下を確認します。

- 設定ファイルが読めるか
- ARP またはルータ接続が通るか
- メール通知を有効化している場合は SMTP 接続できるか
- Firebase 通知を有効化している場合はアクセストークンを取得できるか

## 8. systemd サービスへ反映する

既存の systemd サービスで動かしている場合は、環境変数を追加した後に再起動します。

```bash
sudo systemctl daemon-reload
sudo systemctl restart wifi-notifier
sudo systemctl status wifi-notifier
```

## トラブルシュート

- `環境変数 FIREBASE_CREDENTIALS_FILE が未設定です`
  - systemd とシェルで別環境になっていないか確認する
- `FirebaseサービスアカウントJSONが見つかりません`
  - パスと権限を確認する
- `registration_tokens が未設定です`
  - Android 側で取得した token を設定する
- FCM API の 401 / 403 が出る
  - Firebase Cloud Messaging API の有効化とプロジェクト ID の一致を確認する
