# VPN経由でのGitHub Actions実行ガイド

このドキュメントでは、VPN接続を使用してGitHub ActionsからプライベートネットワークのWiFiルータにアクセスする方法について説明します。

## 質問への回答

**Q: ルータでVPN接続を許可して、そこを経由してGitHub Actionsから監視処理を接続させることはできるか？**

**A: はい、技術的には可能ですが、いくつかの制約と考慮事項があります。**

## 概要

GitHub ActionsのホストランナーはGitHub管理下のクラウド環境で実行されるため、デフォルトではプライベートネットワーク内のルータに直接アクセスできません。しかし、以下の方法でVPN経由のアクセスを実現できます：

### 実現可能な方法

1. **VPNクライアント統合アプローチ**（GitHub Actionsワークフロー内でVPN接続）
2. **セルフホストランナーアプローチ**（推奨）

## 方法1: VPNクライアント統合アプローチ

### 概要

GitHub Actionsワークフロー内でVPNクライアントを起動し、VPN経由でルータに接続する方法です。

### 実装手順

#### ステップ1: VPN接続の準備

ルータまたはネットワークでVPNサーバーを設定します：

**オプションA: ルータのVPN機能を使用**
- NECなどの多くのルータはVPNサーバー機能を内蔵
- L2TP/IPsec、PPTP、OpenVPNなどのプロトコルをサポート
- ルータの管理画面でVPN接続を有効化し、認証情報を設定

**オプションB: 別のVPNサーバーを使用**
- WireGuard、OpenVPN、SoftEther VPNなどをローカルネットワーク内のサーバーにインストール
- より柔軟な設定とセキュリティが可能

#### ステップ2: GitHub Actions Workflowを修正

`.github/workflows/wifi-monitor.yml`に以下のようなステップを追加します：

```yaml
name: WiFi接続監視（VPN経由）

on:
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    
    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4
      
      # VPN接続を確立
      - name: VPN接続を確立
        run: |
          # OpenVPN接続例
          sudo apt-get update
          sudo apt-get install -y openvpn
          
          # VPN設定ファイルをSecretsから作成
          echo "${{ secrets.VPN_CONFIG }}" > vpn-config.ovpn
          
          # VPN接続を開始（バックグラウンド）
          sudo openvpn --config vpn-config.ovpn --daemon
          
          # 接続確立を待機（最大30秒）
          for i in {1..30}; do
            if ip addr show tun0 2>/dev/null; then
              echo "VPN接続が確立されました"
              break
            fi
            sleep 1
          done
      
      - name: VPN接続を確認
        run: |
          # VPNインターフェースが存在するか確認
          ip addr show tun0
          
          # ルータにpingが通るか確認
          ping -c 3 ${{ secrets.ROUTER_IP }}
      
      - name: Pythonをセットアップ
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: 依存パッケージをインストール
        run: |
          pip install -r requirements.txt
      
      - name: Secretsから設定ファイルを生成
        env:
          ROUTER_IP: ${{ secrets.ROUTER_IP }}
          ROUTER_USERNAME: ${{ secrets.ROUTER_USERNAME }}
          ROUTER_PASSWORD: ${{ secrets.ROUTER_PASSWORD }}
          SMTP_SERVER: ${{ secrets.SMTP_SERVER }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          SENDER_EMAIL: ${{ secrets.SENDER_EMAIL }}
          RECIPIENT_EMAILS: ${{ secrets.RECIPIENT_EMAILS }}
          MONITORED_DEVICES: ${{ secrets.MONITORED_DEVICES }}
          USE_TLS: ${{ vars.USE_TLS || 'true' }}
          CHECK_INTERVAL: ${{ vars.CHECK_INTERVAL || '60' }}
          LOG_LEVEL: ${{ vars.LOG_LEVEL || 'INFO' }}
        run: |
          python scripts/generate_config.py
      
      - name: WiFi監視を実行（1回のみチェック）
        run: |
          python src/wifi_notifier.py config.yaml --single-run
      
      - name: VPN接続を切断
        if: always()
        run: |
          sudo killall openvpn || true
      
      - name: ログをアップロード（エラー時）
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: wifi-notifier-logs
          path: wifi_notifier.log
          retention-days: 7
```

#### ステップ3: GitHub Secretsを設定

以下のSecretsを追加で設定：

| Secret名 | 説明 | 例 |
|---------|------|-----|
| `VPN_CONFIG` | VPN設定ファイルの内容（OpenVPN .ovpnファイル全体） | `client\ndev tun\n...` |
| `VPN_USERNAME` | VPN認証用ユーザー名（必要な場合） | `vpnuser` |
| `VPN_PASSWORD` | VPN認証用パスワード（必要な場合） | `vpnpassword` |

### WireGuardを使用する場合

WireGuardはより軽量で高速なVPNプロトコルです：

```yaml
      - name: WireGuard VPN接続を確立
        run: |
          sudo apt-get update
          sudo apt-get install -y wireguard-tools
          
          # WireGuard設定ファイルを作成
          echo "${{ secrets.WIREGUARD_CONFIG }}" | sudo tee /etc/wireguard/wg0.conf
          sudo chmod 600 /etc/wireguard/wg0.conf
          
          # VPN接続を開始
          sudo wg-quick up wg0
          
          # 接続を確認
          sudo wg show
      
      # ... 他のステップ ...
      
      - name: VPN接続を切断
        if: always()
        run: |
          sudo wg-quick down wg0 || true
```

### メリットとデメリット

**メリット：**
- ✅ 追加のインフラ不要（GitHub Actionsのホストランナーをそのまま使用）
- ✅ セットアップが比較的簡単
- ✅ 無料（GitHub Actionsの無料枠内で使用可能）

**デメリット：**
- ❌ VPN接続の確立に時間がかかる（ワークフロー実行時間が増加）
- ❌ VPN接続が不安定な場合、ワークフローが失敗する可能性
- ❌ セキュリティリスク（VPN認証情報をGitHub Secretsに保存する必要）
- ❌ 複雑な設定が必要
- ❌ 各実行ごとにVPN接続を確立・切断する必要がある

## 方法2: セルフホストランナーアプローチ（推奨）

### 概要

ローカルネットワーク内にGitHub Actions Self-hosted Runnerをセットアップする方法です。これが**最も推奨される方法**です。

### 実装手順

#### ステップ1: セルフホストランナーをセットアップ

1. GitHubリポジトリの `Settings` → `Actions` → `Runners` に移動
2. `New self-hosted runner` をクリック
3. OSを選択（Linux、macOS、Windowsなど）
4. 表示される指示に従ってランナーをインストール

**Linuxの例：**
```bash
# ランナー用のディレクトリを作成
mkdir actions-runner && cd actions-runner

# ランナーをダウンロード
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

# 展開
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# 設定（GitHubから表示されるトークンを使用）
./config.sh --url https://github.com/YOUR_USERNAME/wifi-client-notifier --token YOUR_TOKEN

# サービスとして起動
sudo ./svc.sh install
sudo ./svc.sh start
```

#### ステップ2: Workflowを修正

`.github/workflows/wifi-monitor.yml`の`runs-on`を変更：

```yaml
jobs:
  monitor:
    runs-on: self-hosted  # ubuntu-latest から変更
    
    steps:
      # VPN接続は不要（ランナーが既にローカルネットワーク内にあるため）
      
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4
      
      - name: Pythonをセットアップ
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      # ... 残りは同じ ...
```

### メリットとデメリット

**メリット：**
- ✅ **最もシンプルで信頼性が高い**
- ✅ VPN設定不要（ランナーが既にローカルネットワーク内にある）
- ✅ 高速（VPN接続の確立時間が不要）
- ✅ セキュリティが高い（VPN認証情報を外部に保存する必要がない）
- ✅ 安定性が高い（ネットワーク接続が安定）

**デメリット：**
- ❌ 追加のハードウェアが必要（常時稼働するマシン）
- ❌ 電気代がかかる
- ❌ メンテナンスが必要（OSアップデート、セキュリティパッチなど）

### 推奨環境

セルフホストランナーに適した環境：
- Raspberry Pi 4（低消費電力、安価）
- 使用していない古いPC/ノートPC
- NAS（QNAPやSynologyなどのDockerをサポートするモデル）
- 既存のホームサーバー

## 方法3: 従来のローカル実行（最もシンプル）

GitHub Actionsを使わず、ローカルネットワーク内のマシンで直接実行する方法です。

### 実装方法

**systemdサービスとして実行（Linux）：**

`README.md`の「systemdサービスとして実行」セクションを参照してください。

**cronで定期実行（Linux/Mac）：**

```bash
# crontabを編集
crontab -e

# 毎時実行
0 * * * * cd /path/to/wifi-client-notifier && python src/wifi_notifier.py config.yaml --single-run
```

**タスクスケジューラで実行（Windows）：**

Windowsタスクスケジューラを使用して定期実行を設定できます。

### メリットとデメリット

**メリット：**
- ✅ 最もシンプル
- ✅ 設定が簡単
- ✅ GitHub Actionsの知識不要
- ✅ 安定性が高い

**デメリット：**
- ❌ GitHub Actionsの機能（ログ管理、通知など）が使えない
- ❌ リモートからの管理が難しい

## 比較表

| 方法 | 複雑さ | コスト | 安定性 | セキュリティ | 推奨度 |
|-----|-------|-------|--------|------------|-------|
| VPNクライアント統合 | 高 | 無料 | 中 | 中 | ⭐⭐ |
| セルフホストランナー | 中 | 低 | 高 | 高 | ⭐⭐⭐⭐⭐ |
| ローカル実行（systemd/cron） | 低 | 低 | 高 | 高 | ⭐⭐⭐⭐ |

## セキュリティ上の考慮事項

### VPNクライアント統合を使用する場合

1. **VPN認証情報の保護**
   - GitHub Secretsは暗号化されていますが、完全に安全とは限りません
   - 可能であれば証明書ベースの認証を使用
   - VPN接続に使用するユーザーには最小限の権限のみを付与

2. **VPN設定ファイルの管理**
   - VPN設定ファイルに秘密鍵が含まれる場合、特に注意が必要
   - 定期的に認証情報をローテーション

3. **ネットワークセグメンテーション**
   - VPN経由で接続できる範囲をルータのみに制限
   - ファイアウォールルールで不要なアクセスをブロック

### セルフホストランナーを使用する場合

1. **ランナーのセキュリティ**
   - 最新のセキュリティパッチを適用
   - 不要なサービスを無効化
   - ファイアウォールを設定

2. **ネットワーク分離**
   - 可能であれば、ランナーを専用のVLANに配置
   - ルータ以外へのアクセスを制限

## トラブルシューティング

### VPN接続が確立できない

```bash
# VPNログを確認
sudo journalctl -u openvpn -n 50

# ネットワークインターフェースを確認
ip addr show

# ルーティングテーブルを確認
ip route show
```

### ルータにアクセスできない

```bash
# VPN経由でpingが通るか確認
ping -c 3 192.168.10.1

# tracerouteでルーティングを確認
traceroute 192.168.10.1

# ファイアウォールルールを確認
sudo iptables -L -n -v
```

### セルフホストランナーが起動しない

```bash
# ランナーのステータスを確認
sudo ./svc.sh status

# ログを確認
sudo journalctl -u actions.runner.* -n 50
```

## 推奨アプローチ

ユースケースに応じた推奨：

### 1. テスト・開発環境
- **推奨**: ローカル実行（systemd/cron）
- **理由**: シンプルで、迅速にセットアップ可能

### 2. 本番環境（小規模）
- **推奨**: セルフホストランナー
- **理由**: GitHub Actionsの管理機能を活用でき、安定性が高い

### 3. 本番環境（複数拠点）
- **推奨**: セルフホストランナー + 集中管理
- **理由**: 各拠点にランナーを配置し、GitHub Actionsで一元管理

### 4. クラウド環境からアクセスしたい場合
- **推奨**: VPNクライアント統合
- **理由**: 他に選択肢がない場合のみ（セキュリティリスクを理解した上で）

## まとめ

**質問への最終回答:**

はい、VPN経由でGitHub Actionsから監視処理を接続することは可能です。主な実現方法は以下の通りです：

1. **VPNクライアント統合**: GitHub Actionsワークフロー内でVPN接続を確立（可能だが複雑）
2. **セルフホストランナー**: ローカルネットワーク内にランナーを配置（推奨）
3. **ローカル実行**: GitHub Actionsを使わず直接実行（最もシンプル）

**最も推奨される方法は「セルフホストランナー」です。**理由は、設定がシンプルで、安定性とセキュリティが高く、メンテナンスも容易だからです。

VPNクライアント統合も技術的には可能ですが、設定が複雑で、セキュリティリスクもあるため、特別な理由がない限りセルフホストランナーまたはローカル実行を推奨します。

## 参考リンク

- [GitHub Actions Self-hosted Runners](https://docs.github.com/ja/actions/hosting-your-own-runners)
- [OpenVPN Documentation](https://openvpn.net/community-resources/)
- [WireGuard Quick Start](https://www.wireguard.com/quickstart/)
- [systemd Service Units](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

## サポート

この方法を試して問題が発生した場合は、GitHubのIssueで報告してください。以下の情報を含めてください：

- 使用している方法（VPN統合、セルフホストランナー、など）
- ルータのモデル名
- VPNの種類（OpenVPN、WireGuard、など）
- エラーメッセージやログ
- 実行環境（OS、Pythonバージョン）
