FROM python:3.11-slim

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコピー
COPY src/ src/

# 設定ファイル用のボリュームマウントポイントを作成
VOLUME /config

# アプリケーションを実行
CMD ["python", "src/wifi_notifier.py", "/config/config.json"]
