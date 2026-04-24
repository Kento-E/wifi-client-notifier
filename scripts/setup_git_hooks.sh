#!/usr/bin/env bash

set -euo pipefail

git config core.hooksPath .githooks
echo "Git hook を .githooks に設定しました。次回以降のコミット前に品質チェックを実行します。"
