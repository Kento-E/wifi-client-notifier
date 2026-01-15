# イシューテンプレートのラベル自動付与機能の実装

## 実装内容

このPRでは、イシューテンプレートから作成されたイシューに自動的にラベルが付与されるようにする機能を実装しました。

## 変更内容

### 1. ラベル定義ファイルの作成 (`.github/labels.yml`)

リポジトリで使用する全ラベルを定義しました：

- **バグ** (赤): バグレポート
- **機能追加** (水色): 新機能のリクエスト
- **質問** (紫): 仕様や動作に関する質問
- **一般** (緑): 一般的な問題や提案
- **ドキュメント** (青): ドキュメントの改善
- **ヘルプ募集** (深緑): 助けを求めています
- **重複** (グレー): 重複したissue
- **無効** (黄): 無効なissue
- **対応中** (オレンジ): 現在対応中
- **対応済み** (紫): 対応が完了しました

### 2. ラベル同期ワークフローの作成 (`.github/workflows/sync-labels.yml`)

GitHub Actionsを使用して、ラベル定義ファイルに基づいてリポジトリのラベルを自動的に同期します。

**トリガー条件:**
- `main`ブランチに`.github/labels.yml`または`.github/workflows/sync-labels.yml`がプッシュされたとき
- 手動実行（workflow_dispatch）

### 3. general.ymlの更新

`general.yml`テンプレートに「一般」ラベルを追加しました。

**変更前:**
```yaml
labels: []
```

**変更後:**
```yaml
labels: ["一般"]
```

### 4. ドキュメントの作成 (`.github/LABELS_README.md`)

ラベル管理システムの使い方をドキュメント化しました。

## イシューテンプレートとラベルの対応

| テンプレート | ファイル名 | ラベル |
|------------|-----------|--------|
| Bug Report | bug_report.yml | バグ |
| Feature Request | feature_request.yml | 機能追加 |
| Question | question.yml | 質問 |
| General Issue | general.yml | 一般 |

## 動作確認方法

### 1. このPRがマージされた後

1. GitHub Actionsが自動的に実行され、`.github/labels.yml`に定義されたラベルがリポジトリに作成/更新されます
2. Actionsタブで「ラベル同期」ワークフローの実行状態を確認できます

### 2. イシュー作成時のラベル自動付与を確認

1. リポジトリの「Issues」タブに移動
2. 「New issue」をクリック
3. 任意のテンプレート（Bug Report、Feature Request、Question、General Issue）を選択
4. イシュー作成画面の右サイドバーで、該当するラベルが自動的に選択されていることを確認

### 3. 手動でラベル同期を実行する場合

1. リポジトリの「Actions」タブに移動
2. 左サイドバーから「ラベル同期」ワークフローを選択
3. 「Run workflow」ボタンをクリック
4. `main`ブランチを選択して実行

## 技術詳細

### 使用しているGitHub Action

- **micnncim/action-label-syncer@v1**: ラベル定義ファイルに基づいてGitHubリポジトリのラベルを同期

### 設定

- `manifest: .github/labels.yml`: ラベル定義ファイルのパス
- `prune: false`: 既存のラベルを削除しない（定義ファイルにないラベルも保持）

## 今後のラベル管理

新しいラベルを追加したい場合は、以下の手順で実施できます：

1. `.github/labels.yml`を編集して新しいラベルを追加
2. 変更を`main`ブランチにマージ
3. GitHub Actionsが自動的にラベルを同期

## 参考資料

- [GitHub Issue Templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
- [GitHub Labels API](https://docs.github.com/en/rest/issues/labels)
- [action-label-syncer](https://github.com/micnncim/action-label-syncer)
