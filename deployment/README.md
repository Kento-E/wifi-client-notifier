# デプロイメントガイド

このディレクトリには、WiFi Client Notifierのデプロイと開発環境のセットアップに関するファイルが含まれています。

## ファイル構成

- `setup.sh` - 自動セットアップスクリプト
- `setup_raspberrypi.sh` - Raspberry Piへのリモート自動セットアップスクリプト
- `Dockerfile` - Dockerイメージのビルド設定
- `docker-compose.yml` - Docker Composeの設定

## 開発環境のセットアップ

コード品質を維持するため、linterとフォーマッターを使用しています。

### 自動セットアップ（推奨）

```bash
# セットアップスクリプトで自動的にインストール・設定
./deployment/setup.sh
```

このスクリプトは以下を自動で行います：

- 依存パッケージのインストール
- pre-commitフックの設定（コミット時に自動整形）

### 手動セットアップ

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

## Dockerでのデプロイ

### 前提条件

- Docker
- Docker Compose

### 手順

1. 設定ファイルを作成:

```bash
cp config/config.example.yaml config.yaml
# config.yamlを編集して設定を入力
```

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

## その他のデプロイ方法

詳細は [メインREADME](../README.md) を参照してください：

- systemdサービスとして実行（Linux）
- バックグラウンドで実行
- GitHub Actionsで自動実行

## Raspberry Piセットアップ手順

以下は、Raspberry Pi 実機に対して今回実施したセットアップ手順です。
ローカルPCから `PI_HOST`（例: `user@hostname.local`）で接続できる前提です。

### 自動セットアップ（推奨）

手順をまとめたスクリプトを追加しています。

```bash
PI_HOST=user@hostname.local ./deployment/setup_raspberrypi.sh
```

このスクリプトは以下を自動で実行します。

- Raspberry PiへのSSH接続確認
- `git` と `python3-venv` のインストール
- リポジトリ clone/update（現在ブランチ）
- `.venv` 作成と `requirements.txt` インストール
- `config/config.yaml` 転送（デフォルト）
- ARPモード設定補完（`detection_method: arp`, `interface: wlan0`）
- `test_config.py` 実行
- `wifi_notifier.py --single-run` 実行

主なオプション:

```bash
export PI_HOST=user@hostname.local
./deployment/setup_raspberrypi.sh --host pi@192.168.10.50 --branch main
./deployment/setup_raspberrypi.sh --no-config-copy --skip-test --skip-single-run
```

手動で1ステップずつ実行したい場合は、以下の手順を使用してください。

### 1. Raspberry Pi側の作業ディレクトリを作成

```bash
export PI_HOST=user@hostname.local
ssh "$PI_HOST" 'mkdir -p ~/work && cd ~/work && pwd'
```

### 2. 必要パッケージをインストールし、リポジトリを取得

```bash
ssh "$PI_HOST" '
set -e
sudo apt-get update
sudo apt-get install -y git python3-venv
cd ~/work
git clone --branch copilot/feature-monitor-local-network-connection https://github.com/Kento-E/wifi-client-notifier.git
cd wifi-client-notifier
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
'
```

既にクローン済みの場合は、以下で更新できます。

```bash
ssh "$PI_HOST" '
set -e
cd ~/work/wifi-client-notifier
git fetch origin
git checkout main
git pull --ff-only origin main
'
```

### 3. ローカルの設定ファイルを Raspberry Pi に転送

```bash
cat config/config.yaml | ssh "$PI_HOST" 'cat > ~/work/wifi-client-notifier/config/config.yaml'
```

### 4. Raspberry Pi向けに ARP モード設定を反映

```bash
ssh "$PI_HOST" '
set -e
cd ~/work/wifi-client-notifier
. .venv/bin/activate
python - <<"PY"
import yaml
from pathlib import Path

p = Path("config/config.yaml")
cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
cfg["detection_method"] = "arp"
cfg.setdefault("arp", {})
cfg["arp"].setdefault("interface", "wlan0")
cfg["arp"].setdefault("timeout", 2)
p.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("updated")
PY
'
```

### 5. 設定テストを実行

ARP スキャンは root 権限が必要なため、`sudo` で実行します。

```bash
ssh "$PI_HOST" '
set -e
cd ~/work/wifi-client-notifier
printf "n\n" | sudo .venv/bin/python src/test_config.py config/config.yaml
'
```

### 6. 本体を single-run で実行して確認

```bash
ssh "$PI_HOST" '
set -e
cd ~/work/wifi-client-notifier
sudo .venv/bin/python src/wifi_notifier.py config/config.yaml --single-run
'
```

### 7. 常時実行する場合

```bash
ssh "$PI_HOST"
cd ~/work/wifi-client-notifier
sudo .venv/bin/python src/wifi_notifier.py config/config.yaml
```

### 補足

- ARP スキャンは root 権限が必須です。
- `arp.interface` は Raspberry Pi Zero 2 W を想定して `wlan0` を設定しています。
- サブネットは自動検出で `/24` を仮定するため、異なるサブネットマスク環境では `config/config.yaml` の `arp.subnet` を明示してください。
