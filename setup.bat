@echo off
REM Setup script for Aterm WiFi Client Notifier (Windows)

echo === Aterm WiFi Client Notifier セットアップ ===
echo.

REM Check Python version
echo Pythonバージョンを確認中...
python --version
if errorlevel 1 (
    echo エラー: Pythonがインストールされていません
    pause
    exit /b 1
)

echo.

REM Install dependencies
echo 依存パッケージをインストール中...
pip install -r requirements.txt

if errorlevel 1 (
    echo エラー: 依存パッケージのインストールに失敗しました
    pause
    exit /b 1
)

echo √ 依存パッケージのインストール完了
echo.

REM Create config file from example if it doesn't exist
if not exist config.json (
    echo 設定ファイルを作成中...
    copy config.example.json config.json
    echo √ config.json を作成しました
    echo.
    echo 次のステップ:
    echo 1. config.json を編集して、ルータとメールの設定を入力してください
    echo 2. python wifi_notifier.py config.json で実行してください
) else (
    echo config.json は既に存在します
    echo.
    echo 次のステップ:
    echo python wifi_notifier.py config.json で実行してください
)

echo.
echo === セットアップ完了 ===
pause
