# Python version is centrally managed in deployment/python-version.sh
# Update PYTHON_VERSION when changing minimum requirements
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコピー
COPY src/ src/

# 設定ファイル用のボリュームマウントポイントを作成
VOLUME /config

# アプリケーションを実行
CMD ["python", "src/wifi_notifier.py", "/config/config.yaml"]
