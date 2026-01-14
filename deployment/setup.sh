#!/bin/bash
# Setup script for WiFi Client Notifier

# Python version requirements
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

echo "=== WiFi Client Notifier セットアップ ==="
echo ""

# Check Python version
echo "Pythonバージョンを確認中..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "検出されたバージョン: Python $python_version"

# Check if Python version meets minimum requirements
major=$(echo $python_version | cut -d. -f1)
minor=$(echo $python_version | cut -d. -f2)

if [ "$major" -lt "$PYTHON_MIN_MAJOR" ] || ([ "$major" -eq "$PYTHON_MIN_MAJOR" ] && [ "$minor" -lt "$PYTHON_MIN_MINOR" ]); then
    echo "エラー: Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}以上が必要です"
    exit 1
fi

echo "✓ Pythonバージョン確認完了"
echo ""

# Install dependencies
echo "依存パッケージをインストール中..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "エラー: 依存パッケージのインストールに失敗しました"
    exit 1
fi

echo "✓ 依存パッケージのインストール完了"
echo ""

# pre-commitフックをインストール（開発環境用）
if command -v pre-commit &> /dev/null; then
    echo "pre-commitフックをインストール中..."
    pre-commit install
    if [ $? -eq 0 ]; then
        echo "✓ pre-commitフックのインストール完了（コミット時に自動整形されます）"
    else
        echo "⚠ pre-commitフックのインストールに失敗しました（任意）"
    fi
    echo ""
fi

# 設定ファイルを作成（存在しない場合）
if [ ! -f config.yaml ]; then
    echo "設定ファイルを作成中..."
    cp config/config.example.yaml config.yaml
    echo "✓ config.yaml を作成しました"
    echo ""
    echo "次のステップ:"
    echo "1. config.yaml を編集して、ルータとメールの設定を入力してください"
    echo "2. python3 src/wifi_notifier.py config.yaml で実行してください"
else
    echo "config.yaml は既に存在します"
    echo ""
    echo "次のステップ:"
    echo "python3 src/wifi_notifier.py config.yaml で実行してください"
fi

echo ""
echo "=== セットアップ完了 ==="
