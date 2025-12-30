# コードレビューエージェント指示

## 言語設定

**すべてのコードレビューコメントは日本語で出力してください。**

## レビュー方針

このリポジトリは日本のAtermルータユーザー向けです。レビューコメントは日本語で、わかりやすく説明してください。

### コメント形式

#### 良い例（日本語）

```markdown
**提案**: この関数ではエラーハンドリングが不足しています。

ネットワーク接続エラーが発生した場合の処理を追加することをお勧めします：

\`\`\`python
try:
    response = requests.get(url)
except requests.exceptions.ConnectionError as e:
    logging.error(f"接続エラー: {e}")
    return None
\`\`\`

これにより、ユーザーに適切なエラーメッセージを表示できます。
```

#### 悪い例（英語）

```markdown
**Suggestion**: This function lacks error handling.

Consider adding error handling for network connection errors:

\`\`\`python
try:
    response = requests.get(url)
except requests.exceptions.ConnectionError as e:
    logging.error(f"Connection error: {e}")
    return None
\`\`\`
```

### レビュー項目

1. **コードの正確性**: ロジックが正しいか
2. **エラーハンドリング**: 適切な例外処理があるか
3. **日本語化**: コメント、ログメッセージが日本語か
4. **ドキュメント**: docstringが日本語で記述されているか
5. **セキュリティ**: 認証情報の取り扱いが適切か

### コメントの優先度

- **重要**: セキュリティ、バグ、クリティカルな問題
- **推奨**: パフォーマンス、可読性の改善
- **提案**: より良い実装方法、ベストプラクティス

### 具体的な指摘例

```markdown
**重要**: パスワードがプレーンテキストでログ出力されています。

line 45:
\`logging.debug(f"Password: {password}")\`

セキュリティ上の理由から、パスワードのログ出力は削除してください。
```

```markdown
**推奨**: ログメッセージを日本語化してください。

line 78:
\`logging.error("Failed to connect")\`

以下のように変更することをお勧めします：
\`logging.error("接続に失敗しました")\`
```

## レビュー完了時のコメント

レビュー完了時は、日本語で総評を提供してください：

```markdown
## レビュー結果

全体的に良好な実装です。以下の点を確認しました：

✓ エラーハンドリングが適切に実装されています
✓ ログ出力が日本語化されています
✓ セキュリティ上の問題はありません

軽微な改善提案をいくつかコメントしましたが、すべてオプショナルです。
```

このガイドラインに従って、すべてのレビューコメントを日本語で記述してください。
