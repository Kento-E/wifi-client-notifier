# ルータモデルごとのカスタマイズガイド

このドキュメントでは、お使いのWiFiルータモデルに合わせてスクリプトをカスタマイズする方法を説明します。

## 概要

WiFiルータは様々なモデルがあり、それぞれ管理画面のインターフェースが異なります。
このため、デフォルトの実装が動作しない場合は、カスタマイズが必要になることがあります。

## カスタマイズが必要な場合

以下のような場合、カスタマイズが必要です：
- ルータへのログインが失敗する
- デバイスリストが取得できない
- 空のデバイスリストが返される

## ルータの情報を調査する方法

### 1. ブラウザの開発者ツールを使用

1. ブラウザでルータの管理画面にアクセス
2. F12キーを押して開発者ツールを開く
3. 「ネットワーク」タブを選択
4. ルータにログインする
5. 無線LAN接続状態のページに移動
6. 送信されたリクエストとレスポンスを確認

### 2. 重要な情報

以下の情報を記録してください：

- **ログインURL**: 例 `/index.cgi/login`, `/cgi-bin/login.cgi`
- **ログインパラメータ**: フォームに送信されるデータ
- **認証方法**: パスワードのハッシュ化方法（MD5, SHA256など）
- **デバイスリストURL**: 例 `/index.cgi/wireless_client_list`, `/wlmaclist.cgi`
- **レスポンス形式**: HTML、JSON、XMLなど

## wifi_notifier.pyのカスタマイズ方法

### WiFiRouterクラスの修正

`src/wifi_notifier.py`の`WiFiRouter`クラスを修正します。

#### 例1: ログイン方法の変更

```python
def login(self) -> bool:
    """ルータにログイン"""
    try:
        # あなたのルータに合わせて変更
        login_url = f"{self.base_url}/cgi-bin/login.cgi"  # URLを変更
        
        # パスワードハッシュ化なしの場合
        login_data = {
            'username': self.username,  # パラメータ名を変更
            'password': self.password    # パラメータ名を変更
        }
        
        response = self.session.post(login_url, data=login_data, timeout=10)
        
        # 成功判定を変更
        return 'success' in response.text.lower()  # レスポンス内容で判定
        
    except Exception as e:
        logging.error(f"Login failed: {e}")
        return False
```

#### 例2: SHA256ハッシュを使用する場合

```python
import hashlib

def login(self) -> bool:
    """ルータにログイン (SHA256版)"""
    try:
        login_url = f"{self.base_url}/index.cgi/login"
        
        # SHA256でパスワードをハッシュ化
        password_hash = hashlib.sha256(self.password.encode()).hexdigest()
        
        login_data = {
            'user': self.username,
            'passwd': password_hash
        }
        
        response = self.session.post(login_url, data=login_data, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logging.error(f"Login failed: {e}")
        return False
```

#### 例3: Basic認証を使用する場合

```python
from requests.auth import HTTPBasicAuth

def login(self) -> bool:
    """ルータにログイン (Basic認証版)"""
    try:
        # Basic認証を設定
        self.session.auth = HTTPBasicAuth(self.username, self.password)
        
        # 認証が必要なページにアクセスして確認
        response = self.session.get(f"{self.base_url}/index.html", timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logging.error(f"Login failed: {e}")
        return False
```

### デバイスリスト取得の変更

#### 例1: 異なるエンドポイントを使用

```python
def get_connected_devices(self) -> List[Dict[str, str]]:
    """接続デバイスリストを取得"""
    try:
        # エンドポイントを変更
        devices_url = f"{self.base_url}/wlmaclist.cgi"  # 例
        response = self.session.get(devices_url, timeout=10)
        
        if response.status_code != 200:
            logging.warning(f"Failed to get device list: {response.status_code}")
            return []
        
        # パースメソッドを呼び出し
        devices = self._parse_device_list(response.text)
        return devices
        
    except Exception as e:
        logging.error(f"Error getting connected devices: {e}")
        return []
```

#### 例2: JSON APIを使用

```python
import json

def get_connected_devices(self) -> List[Dict[str, str]]:
    """接続デバイスリストを取得 (JSON API版)"""
    try:
        devices_url = f"{self.base_url}/api/wireless/clients"
        response = self.session.get(devices_url, timeout=10)
        
        if response.status_code != 200:
            return []
        
        # JSONレスポンスをパース
        data = response.json()
        devices = []
        
        for client in data.get('clients', []):
            device = {
                'mac': client.get('mac', '').upper(),
                'ip': client.get('ip', ''),
                'hostname': client.get('name', '')
            }
            devices.append(device)
        
        return devices
        
    except Exception as e:
        logging.error(f"Error getting connected devices: {e}")
        return []
```

## HTMLパース方法のカスタマイズ

`aterm_scraper.py`の`parse_wireless_lan_status()`関数をカスタマイズします。

### 例: 特定のテーブル構造をパース

```python
def parse_wireless_lan_status(html_content: str) -> List[Dict[str, str]]:
    """無線LAN状態ページをパース"""
    devices = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 特定のIDを持つテーブルを検索
        table = soup.find('table', {'id': 'wlan_client_table'})
        
        if table:
            rows = table.find_all('tr')[1:]  # ヘッダー行をスキップ
            
            for row in rows:
                cells = row.find_all('td')
                
                if len(cells) >= 3:  # 最低3列必要と仮定
                    device = {
                        'mac': cells[0].get_text(strip=True),
                        'ip': cells[1].get_text(strip=True),
                        'hostname': cells[2].get_text(strip=True)
                    }
                    devices.append(device)
        
        return devices
        
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []
```

## デバッグ方法

### 1. ログレベルをDEBUGに設定

`config.json`:
```json
{
  "log_level": "DEBUG"
}
```

### 2. レスポンス内容をログに出力

```python
def get_connected_devices(self) -> List[Dict[str, str]]:
    """接続デバイスリストを取得"""
    try:
        devices_url = f"{self.base_url}/index.cgi/wireless_client_list"
        response = self.session.get(devices_url, timeout=10)
        
        # レスポンス内容をログに出力（デバッグ用）
        logging.debug(f"Response status: {response.status_code}")
        logging.debug(f"Response headers: {response.headers}")
        logging.debug(f"Response content: {response.text[:500]}")  # 最初の500文字
        
        devices = self._parse_device_list(response.text)
        return devices
        
    except Exception as e:
        logging.error(f"Error getting connected devices: {e}")
        return []
```

### 3. Pythonインタラクティブシェルでテスト

```python
python3
>>> from wifi_notifier import WiFiRouter
>>> router = WiFiRouter('192.168.10.1', 'admin', 'password')
>>> router.login()
>>> devices = router.get_connected_devices()
>>> print(devices)
```

## 主要なルータモデルの既知の設定

### WG2600シリーズ

```python
# ログインURL: /index.cgi/login
# デバイスリストURL: /index.cgi/wireless_client_list
# 認証: MD5ハッシュ
```

### WF1200シリーズ

```python
# ログインURL: /cgi-bin/login.cgi
# デバイスリストURL: /cgi-bin/wireless_list.cgi
# 認証: プレーンテキスト
```

（注：これらは例です。実際のルータで確認してください）

## サポート

カスタマイズに困った場合は、以下の情報と共にIssueを作成してください：

1. ルータのモデル名
2. ファームウェアバージョン
3. ブラウザの開発者ツールで確認したリクエスト/レスポンスのスクリーンショット
4. エラーログ（`log_level: "DEBUG"`で取得）

## 参考リンク

- [BeautifulSoup ドキュメント](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Requests ドキュメント](https://requests.readthedocs.io/)
