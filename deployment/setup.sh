#!/usr/bin/env bash
set -euo pipefail

# Setup script for WiFi Client Notifier

# Python version requirements
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=11

echo "=== WiFi Client Notifier セットアップ ==="
echo ""

# Check Python version
echo "Pythonバージョンを確認中..."

find_compatible_python() {
    for cmd in python3.13 python3.12 python3.11 python3; do
        if command -v "$cmd" >/dev/null 2>&1; then
            version=$("$cmd" --version 2>&1 | awk '{print $2}')
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)

            if [ "$major" -gt "$PYTHON_MIN_MAJOR" ] || ([ "$major" -eq "$PYTHON_MIN_MAJOR" ] && [ "$minor" -ge "$PYTHON_MIN_MINOR" ]); then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

if ! PYTHON_CMD=$(find_compatible_python); then
    echo "エラー: Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}以上が必要です"
    echo "ヒント: macOS では 'brew install python@3.11' でインストールできます"
    exit 1
fi

python_version=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "使用するPython: $PYTHON_CMD ($python_version)"

echo "✓ Pythonバージョン確認完了"
echo ""

# Install dependencies
echo "依存パッケージをインストール中..."
$PYTHON_CMD -m pip install -r requirements.txt

echo "✓ 依存パッケージのインストール完了"
echo ""

# pre-commitフックをインストール（開発環境用）
declare -a pre_commit_cmd=()

if command -v pre-commit >/dev/null 2>&1 && pre-commit --version >/dev/null 2>&1; then
    pre_commit_cmd=(pre-commit)
elif "$PYTHON_CMD" -m pre_commit --version >/dev/null 2>&1; then
    pre_commit_cmd=("$PYTHON_CMD" -m pre_commit)
elif command -v python3 >/dev/null 2>&1 && python3 -m pre_commit --version >/dev/null 2>&1; then
    pre_commit_cmd=(python3 -m pre_commit)
fi

if [[ ${#pre_commit_cmd[@]} -gt 0 ]]; then
    echo "pre-commitフックをインストール中..."
    "${pre_commit_cmd[@]}" install
    echo "✓ pre-commitフックのインストール完了（コミット時に自動整形されます）"
    echo ""
else
    echo "⚠ pre-commit の実行環境が見つかりませんでした（任意）。"
    echo "  必要に応じて '$PYTHON_CMD -m pip install -r requirements.txt' を再実行してください。"
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
    echo "2. $PYTHON_CMD src/wifi_notifier.py config.yaml で実行してください"
else
    echo "config.yaml は既に存在します"
    echo ""
    echo "次のステップ:"
    echo "$PYTHON_CMD src/wifi_notifier.py config.yaml で実行してください"
fi

echo ""
echo "=== セットアップ完了 ==="
