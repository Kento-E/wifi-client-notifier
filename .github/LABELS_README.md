# ラベル管理について

このディレクトリには、GitHubリポジトリのラベル定義と同期ワークフローが含まれています。

## ファイル構成

- `labels.yml`: リポジトリで使用するラベルの定義ファイル
- `workflows/sync-labels.yml`: ラベルを自動同期するGitHub Actionsワークフロー

## ラベル一覧

現在定義されているラベル：

| ラベル名 | 色 | 説明 |
|---------|-----|------|
| バグ | 🔴 赤 | バグレポート |
| 機能追加 | 🔵 水色 | 新機能のリクエスト |
| 質問 | 🟣 紫 | 仕様や動作に関する質問 |
| 一般 | 🟢 緑 | 一般的な問題や提案 |
| ドキュメント | 🔵 青 | ドキュメントの改善 |
| ヘルプ募集 | 🟢 深緑 | 助けを求めています |
| 重複 | ⚪ グレー | 重複したissue |
| 無効 | 🟡 黄 | 無効なissue |
| 対応中 | 🟠 オレンジ | 現在対応中 |
| 対応済み | 🟣 紫 | 対応が完了しました |

## イシューテンプレートとの対応

各イシューテンプレートには、以下のラベルが自動的に付与されます：

- **Bug Report** (`bug_report.yml`): `バグ`
- **Feature Request** (`feature_request.yml`): `機能追加`
- **Question** (`question.yml`): `質問`
- **General Issue** (`general.yml`): `一般`

## ラベルの追加・変更方法

1. `.github/labels.yml` ファイルを編集
2. 変更をコミットして `main` ブランチにプッシュ
3. GitHub Actionsが自動的にラベルを同期

### 手動でラベルを同期する場合

GitHub Actionsの画面から「ラベル同期」ワークフローを手動実行できます：

1. リポジトリの「Actions」タブに移動
2. 「ラベル同期」ワークフローを選択
3. 「Run workflow」ボタンをクリック

## ラベルの形式

```yaml
- name: "ラベル名"
  color: "カラーコード（6桁の16進数）"
  description: "ラベルの説明"
```

### カラーコード例

- 赤: `d73a4a`
- 青: `0075ca`
- 緑: `0e8a16`
- 黄: `fbca04`
- 紫: `d876e3`
- グレー: `cfd3d7`

## 参考

- [GitHub Labels APIドキュメント](https://docs.github.com/en/rest/issues/labels)
- [action-label-syncer](https://github.com/micnncim/action-label-syncer)
