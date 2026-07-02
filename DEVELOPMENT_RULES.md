# DEVELOPMENT_RULES

## 基本方針

このプロジェクトは AI Video Factory です。
Windows用ローカルデスクトップアプリとして、ショート動画制作を半自動化します。

最優先は以下です。

1. 既存機能を壊さない
2. 新機能は小さく追加する
3. UIと処理を分離する
4. READMEを必ず更新する
5. 動作確認してからコミットする

## Git運用

main ブランチへ直接コミットしないでください。

作業時は必ず feature ブランチを作成してください。

例:

```bash
git checkout -b feature/bgm

バグ修正の場合:

git checkout -b fix/parser-error

コミット前チェック

コミット前に必ず以下を実行してください。

git status
python -m pytest
python app/main.py

python app/main.py は起動確認です。自動実行が難しい場合は、起動確認手順をレポートしてください。

コミットルール

コミットメッセージは分かりやすく書いてください。

例:
Add BGM mixing support
Fix JSON parser error handling
Improve FFmpeg error messages

Pushルール

作業ブランチへpushしてください。

git push -u origin feature/bgm

mainへ直接pushしないでください。

README更新

新機能を追加した場合は README.md を必ず更新してください。

更新内容:

使い方
設定項目
よくあるエラー
必要な外部ツール
動作確認方法
コーディング方針
Python + PySide6
UIと処理を分離
services に処理を書く
views にUIを書く
video_editors に動画編集エンジンを書く
型ヒントを使う
日本語コメントを適度に入れる
例外処理は日本語メッセージにする
禁止事項
OpenAI APIなど有料APIを勝手に追加しない
画像生成APIを勝手に追加しない
mainブランチへ直接pushしない
大規模な設計変更を勝手にしない
不要な新機能を追加しない
実装後レポート

実装後に以下を報告してください。

実装内容
変更ファイル
動作確認結果
テスト結果
コミットメッセージ
pushしたブランチ名
注意点