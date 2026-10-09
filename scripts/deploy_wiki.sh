#!/usr/bin/env bash
# Deploy docs/wiki/*.md to GitHub Wiki repository (Aiccountant007.wiki.git)
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WIKI_DIR="$DIR/docs/wiki"
TMP_WIKI="/tmp/aiccountant007_wiki"

TOKEN=$(gh auth token 2>/dev/null || echo "")
if [ -n "$TOKEN" ]; then
  WIKI_REMOTE="https://x-access-token:${TOKEN}@github.com/chotamode/Aiccountant007.wiki.git"
else
  WIKI_REMOTE="https://github.com/chotamode/Aiccountant007.wiki.git"
fi

echo "==> Preparing GitHub Wiki deployment..."
rm -rf "$TMP_WIKI"
mkdir -p "$TMP_WIKI"

# Copy markdown files only
cp "$WIKI_DIR"/*.md "$TMP_WIKI/"

cd "$TMP_WIKI"
git init
git checkout -b master || git checkout -b main
git config user.name "Eduard (Aiccountant007)"
git config user.email "bot@aiccountant007.ai"

git add .
git commit -m "docs: sync wiki knowledge base"

echo "==> Pushing to $WIKI_REMOTE..."
if git push -f "$WIKI_REMOTE" master:master 2>/dev/null || git push -f "$WIKI_REMOTE" main:main 2>/dev/null; then
  echo "==> Wiki successfully deployed to GitHub!"
else
  echo "==> [NOTICE] Could not push automatically (GitHub Wiki may need to be initialized in repository settings first)."
  echo "==> All files are saved and ready in docs/wiki/"
fi

rm -rf "$TMP_WIKI"
