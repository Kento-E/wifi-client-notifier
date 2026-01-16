# デプロイメントガイド

このディレクトリには、WiFi Client Notifierのデプロイと開発環境のセットアップに関するファイルが含まれています。

## ファイル構成

- `setup.sh` - 自動セットアップスクリプト
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
