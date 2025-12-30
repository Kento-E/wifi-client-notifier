#!/bin/bash
# Setup script for WiFi Client Notifier

echo "=== WiFi Client Notifier セットアップ ==="
echo ""

# Check Python version
echo "Pythonバージョンを確認中..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "検出されたバージョン: Python $python_version"

# Check if Python 3.7+
major=$(echo $python_version | cut -d. -f1)
minor=$(echo $python_version | cut -d. -f2)

if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 7 ]); then
    echo "エラー: Python 3.7以上が必要です"
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

# 設定ファイルを作成（存在しない場合）
if [ ! -f config.json ]; then
    echo "設定ファイルを作成中..."
    cp config/config.example.json config.json
    echo "✓ config.json を作成しました"
    echo ""
    echo "次のステップ:"
    echo "1. config.json を編集して、ルータとメールの設定を入力してください"
    echo "2. python3 src/wifi_notifier.py config.json で実行してください"
else
    echo "config.json は既に存在します"
    echo ""
    echo "次のステップ:"
    echo "python3 src/wifi_notifier.py config.json で実行してください"
fi

echo ""
echo "=== セットアップ完了 ==="
