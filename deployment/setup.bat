@echo off
REM Setup script for WiFi Client Notifier (Windows)

echo === WiFi Client Notifier セットアップ ===
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

REM 設定ファイルを作成（存在しない場合）
if not exist config.json (
    echo 設定ファイルを作成中...
    copy config\config.example.json config.json
    echo √ config.json を作成しました
    echo.
    echo 次のステップ:
    echo 1. config.json を編集して、ルータとメールの設定を入力してください
    echo 2. python src\wifi_notifier.py config.json で実行してください
) else (
    echo config.json は既に存在します
    echo.
    echo 次のステップ:
    echo python src\wifi_notifier.py config.json で実行してください
)

echo.
echo === セットアップ完了 ===
pause
