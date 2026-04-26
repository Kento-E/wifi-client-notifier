---
applyTo: "config/config.example.yaml,config/config.yaml,README.md,src/wifi_notifier.py"
description: "設定キー変更時に、設定例・実運用設定・README・実装バリデーションを同期更新して整合性を保つ。"
---

# 設定同期指示

`config/config.example.yaml` を更新する場合は、以下を必ず同時に確認・更新すること。

1. `config/config.yaml` が存在する場合は、同じキー構造を反映する
2. `README.md` の設定説明・サンプル値・手順を実装と一致させる
3. `src/wifi_notifier.py` のバリデーション条件・エラーメッセージを設定仕様と一致させる

## 反映対象

- キーの追加・削除
- ネスト構造の変更
- 必須/任意の変更
- 推奨設定方針の変更

## 反映時の注意

- `config/config.yaml` のローカル固有値（SMTP認証情報、端末MAC、IPなど）は上書きしない
- 説明文だけ変更した場合でも、関連する設定項目の整合性を確認する
- 後方互換を残す場合は、READMEに理由を明記する
