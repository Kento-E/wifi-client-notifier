# Python バージョン管理

## 概要

このプロジェクトのPython最小バージョン要件は **`python-version.sh`** で一元管理されています。

## バージョン変更時の手順

Python最小バージョンを変更する場合は、以下の手順に従ってください：

### 1. python-version.shを更新

```bash
# deployment/python-version.sh を編集
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11  # ← この値を変更
```

### 2. 関連ファイルを更新

以下のファイルも手動で更新する必要があります：

- **pyproject.toml**: `target-version = ['py311']` を変更（例: py312）
- **Dockerfile**: `ARG PYTHON_VERSION=3.11` を変更（例: 3.12）

### 3. README.mdの確認

`README.md`の必要要件セクションは自動的に`python-version.sh`を参照しているため、手動更新は不要です。

## ファイル一覧

| ファイル | 用途 | 更新方法 |
|---------|------|---------|
| `python-version.sh` | バージョン定義（一元管理） | 手動更新 |
| `setup.sh` | セットアップスクリプト | 自動（python-version.shを参照） |
| `pyproject.toml` | Black設定 | 手動更新（コメント参照） |
| `Dockerfile` | Dockerイメージ | 手動更新（コメント参照） |
| `README.md` | ドキュメント | 自動（python-version.shを参照） |
