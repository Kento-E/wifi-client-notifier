# GitHub Copilot指示書

このディレクトリには、GitHub Copilotに対する指示書が含まれています。

## 目的

このリポジトリはWiFiルータユーザー向けのプロジェトです。
すべての出力（コード、コメント、ドキュメント、コミットメッセージなど）を**日本語で統一する**ため、
GitHub Copilotに対する明確な指示を提供します。

## 指示書一覧

### [`instructions/default.instructions.md`](instructions/default.instructions.md)
基本的な指示書です。

**主な内容：**
- 言語設定（すべて日本語で出力）
- コーディング規約
- コミットメッセージの形式
- ドキュメントの記述方法

### [`instructions/code-review.instructions.md`](instructions/code-review.instructions.md)
コードレビュー時の指示書です。

**主な内容：**
- レビューコメントを日本語で記述
- レビュー項目と優先度
- コメント形式の例

### [`instructions/pull-request.instructions.md`](instructions/pull-request.instructions.md)
Pull Request作成・管理時の指示書です。

**主な内容：**
- PRタイトル・説明を日本語で記述
- 変更履歴の記述方法
- マージ前の確認事項

### [`instructions/issue.instructions.md`](instructions/issue.instructions.md)
Issue作成・管理時の指示書です。

**主な内容：**
- Issueタイトル・説明を日本語で記述
- バグ報告テンプレート
- 機能リクエストテンプレート

## 使用方法

これらの指示書は、GitHub Copilotが自動的に参照し、
適切な言語と形式で出力を生成するために使用されます。

### 開発者向け

手動で作業する際も、これらのガイドラインに従ってください：

1. **すべて日本語で記述**
   - コミットメッセージ
   - コードコメント
   - ドキュメント
   - Issue/PR

2. **例外的に英語を使用できる場合**
   - 変数名、関数名（Pythonの命名規則）
   - 技術用語で日本語訳が不自然な場合

3. **ユーザー目線**
   - WiFiルータユーザーがわかりやすい説明
   - 具体的な例を含める

## 更新

指示書の内容は、プロジェクトの進化に合わせて適宜更新してください。
更新時は、既存のガイドラインとの一貫性を保つよう注意してください。
