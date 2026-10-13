# scripts

運用・開発用のスクリプト集です。

| スクリプト | 用途 |
| --- | --- |
| `pi_devices.sh` | Raspberry Pi 上で現在接続中の端末一覧をARPスキャンして表示する |
| `run_quality_checks.sh` | コミット前の品質チェックを実行する |
| `setup_git_hooks.sh` | Git hook（`.githooks`）を有効化する |

## pi_devices.sh

現在ネットワークに接続している端末を ARP スキャンし、JSON で出力します。
`config/config.yaml` の `arp` 設定（`subnet` / `interface` / `timeout`）を使用します。

```sh
# 検出した全端末を表示
sh ~/wifi-client-notifier/scripts/pi_devices.sh

# repeat_notification_devices に登録した端末のみ表示
sh ~/wifi-client-notifier/scripts/pi_devices.sh --repeat-only
```

### オプション

| オプション | 説明 |
| --- | --- |
| `--repeat-only` | `repeat_notification_devices` の端末のみ出力する |

`--repeat-only` の動作:

- 出力対象を `config/config.yaml` の `repeat_notification_devices` に含まれる端末に限定します。
- MAC アドレスは前後の空白を除き、大文字小文字を区別せずに照合します（通知本体と同じ扱い）。
- `repeat_notification_devices` が未設定または空の場合は、空の配列（`[]`）を出力します。
- 未知のオプションを指定すると使い方を表示して終了コード 1 で終了します。

### 前提条件

- Raspberry Pi 上で実行します（ARP スキャンのため）。
- ARP スキャンには root 権限または `CAP_NET_RAW` ケーパビリティが必要です。
  `sudo` なしで実行するには、`CAP_NET_RAW` を付与した Python の専用コピーを用意します。

  ```sh
  cd ~/wifi-client-notifier
  cp "$(readlink -f .venv/bin/python3)" .venv/bin/python3-netraw
  sudo setcap cap_net_raw+eip .venv/bin/python3-netraw
  ```

  `.venv/bin/python3-netraw` が存在し実行可能であれば、スクリプトは自動的にそれを使用します。
  存在しない場合は `.venv/bin/python3` を使用するため、`sudo` が必要です。

- システムの `python3` 自体には `setcap` を付与しないでください（全ユーザーの `python3` に影響します）。

### パスの解決

プロジェクトディレクトリは次の順で探します。

1. 環境変数 `WIFI_NOTIFIER_PROJECT_DIR`（既定値は `$HOME/work/wifi-client-notifier`）
2. `$HOME/wifi-client-notifier`（上記が存在しない場合。イメージ版の Pi はこちら）

### 出力例

```json
[
  {
    "hostname": "...",
    "ip": "192.168.10.xx",
    "mac": "2E:F0:7D:4A:D9:32",
    "vendor": "...",
    "...": "..."
  }
]
```
