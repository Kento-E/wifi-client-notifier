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

## 9. 死活監視（ハートビート）を設定する

Pi はスキャン成功のたびに Firestore の `heartbeats/<ホスト名>` へ `last_seen` と、
接続が途切れた後に復帰した時刻 `online_since` を書き込みます。
GitHub Actions（`.github/workflows/raspberrypi-heartbeat.yml`、15分間隔）が途絶を検知し、
FCM で通知します。復帰時は復帰通知を送ります。外向き HTTPS のみで動作します。

1. Firebase コンソールの「Firestore Database」でデータベース（`(default)`）を作成する
2. サービスアカウントに Firestore の読み書き権限（IAM ロール `Cloud Datastore User`）を付与する
3. GitHub リポジトリの Secrets に以下を登録する。サービスアカウント JSON は
   JSON ごとではなく項目ごとに分けて登録する（`raspberrypi-image` と同じ構成）
   - `GOOGLE_SA_PRIVATE_KEY`: `private_key`（PEM）
   - `GOOGLE_SA_PRIVATE_KEY_ID`: `private_key_id`
   - `GOOGLE_SA_PROJECT_ID`: `project_id`（Firebase プロジェクト ID としても使用）
   - `GOOGLE_SA_CLIENT_EMAIL`: `client_email`
   - `GOOGLE_SA_CLIENT_ID`: `client_id`
   - `FIREBASE_REGISTRATION_TOKENS`: 通知先 token（カンマ区切り）

   ```bash
   key=/path/to/service-account.json
   for item in private_key private_key_id project_id client_email client_id; do
     jq -j ".$item" "$key" | gh secret set "GOOGLE_SA_$(echo "$item" | tr a-z A-Z)"
   done
   ```

4. 必要に応じて Variables を設定する
   - `HEARTBEAT_TIMEOUT_MINUTES`: 途絶とみなす分数（既定 30）
   - `HEARTBEAT_HOSTS`: 監視対象の Pi のホスト名（カンマ区切り、既定 `raspberrypi`）。
     ハートビートが一度も届いていないホストも途絶として通知する

5. Pi の接続断を Google カレンダーに予定として残す場合は、Secrets に `GOOGLE_CALENDAR_ID`
   （登録先カレンダーID）を登録する。未登録なら予定登録は行わない。
   カレンダーには、上記サービスアカウントの `client_email` を「予定の変更」権限で共有しておく

   ```bash
   printf '%s' "<カレンダーID>" | gh secret set GOOGLE_CALENDAR_ID
   ```

Pi の接続断は、次のとおり 1 件の予定として記録されます。

- 途絶を検知すると、最後にハートビートを確認できた時刻を開始とする
  「🛜 Pi接続断 (ホスト名)」を登録する（終了は検知時刻の仮置き）
- 復帰を検知すると、その予定の終了時刻を Pi が再接続した時刻（`online_since`）に更新する。
  予定は「接続が切れていた時間」になる
- 登録・更新に失敗した場合は、次回の実行で再試行する
- 途絶と判定するのは `HEARTBEAT_TIMEOUT_MINUTES` を超えた場合のため、それより短い断は記録されない

注意:

- GitHub Actions の cron は混雑時に遅延・スキップされるため、通知は数十分遅れることがある
- 旧 SSH ベースの `raspberrypi-healthcheck.yml` と、関連する Secrets/Variables
  （`HEALTH_CHECK_ENABLED` など）は不要なので削除してよい

## トラブルシュート

- `環境変数 FIREBASE_CREDENTIALS_FILE が未設定です`
  - systemd とシェルで別環境になっていないか確認する
- `FirebaseサービスアカウントJSONが見つかりません`
  - パスと権限を確認する
- `registration_tokens が未設定です`
  - Android 側で取得した token を設定する
- FCM API の 401 / 403 が出る
  - Firebase Cloud Messaging API の有効化とプロジェクト ID の一致を確認する
