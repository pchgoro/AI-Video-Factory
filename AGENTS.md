# AGENTS.md

# CosmicVideoFactory

## Project

ローカルでYouTube Shortsを半自動制作するWindowsアプリ。

目的は

Story
↓
画像生成
↓
VOICEVOX
↓
字幕
↓
動画生成
↓
YouTube/TikTok

までを自動化すること。

現在 Phase8 まで実装済み。

---

## Source of Truth

README.md
ROADMAP.md
CHANGELOG.md

を先に読んでから作業すること。

---

## Architecture

Story Composer
↓
Export to Factory
↓
Image Generation
↓
VOICEVOX
↓
Subtitle
↓
Video Render
↓
Upload

既存Serviceを再利用すること。

ロジックを重複実装しない。

---

## Rules

・無関係なコードを変更しない
・小さい差分で実装する
・既存UIを壊さない
・既存APIを壊さない
・後方互換を維持する
・既存テストを削除しない

---

## Safety

実APIは勝手に呼ばない。

画像生成
YouTube
TikTok
Gemini
OpenAI

はMockで実装する。

---

## Git

commitしない
pushしない
mergeしない

---

## Test

python -m compileall app tests

pytestを実行すること。

---

## Before Coding

まず

1. リポジトリを調査
2. 実装計画を提示
3. 承認後に実装

を徹底すること。