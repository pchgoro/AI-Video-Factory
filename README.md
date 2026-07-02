# AI Video Factory

AI Video Factory は、ショート動画制作をローカルPCで整理・半自動化するWindows用デスクトップアプリです。

Version: `0.5.0`  
Phase: `Phase5`

Phase5では、ChatGPT JSONの時間付き字幕からASS字幕を生成し、FFmpegで動画へ焼き込めるようにしました。

## 環境構築

推奨:

- Windows
- Python 3.10以上
- VOICEVOX Engine
- FFmpeg

セットアップ:

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory
python -m pip install -r requirements.txt
```

起動:

```powershell
python app\main.py
```

または `run_app.bat` をダブルクリックします。

## 初回セットアップ

1. アプリを起動します。
2. 「設定」を開きます。
3. 「環境チェック」を押します。
4. Python、FFmpeg、VOICEVOX、projects / exports / assets、書き込み権限を確認します。
5. FFmpegがWARNINGの場合はFFmpegをインストールするか、`FFmpeg path` に `ffmpeg.exe` のパスを入れます。
6. VOICEVOXがWARNINGの場合はVOICEVOXを起動してから再確認します。

## 5分で試す方法

1. 新規プロジェクトを作成します。
2. `samples/space.json` の内容をコピーします。
3. アプリの「JSON回答貼り付け」に貼り付けます。
4. `sample_images/001.png`、`002.png`、`003.png` をプロジェクトの `images` フォルダへコピーします。
5. VOICEVOXを起動して「VOICEVOX音声生成」を押します。
6. FFmpegを使える状態にして「FFmpeg動画生成」を押します。
7. `video/final.mp4` を「完成動画プレビュー」またはExplorerで確認します。

サンプル:

- `samples/space.json`
- `samples/stock.json`
- `samples/history.json`
- `samples/cat.json`
- `samples/ai.json`
- `sample_images/001.png`
- `sample_images/002.png`
- `sample_images/003.png`

## ChatGPT JSON出力形式

ChatGPTにはJSONだけを返すよう指示します。

```json
{
  "title": "",
  "script": "",
  "voice_text": "",
  "image_prompts": ["", "", ""],
  "subtitles": [
    {
      "text": "",
      "start": "",
      "end": ""
    }
  ],
  "hashtags": [""]
}
```

JSON以外の説明文やMarkdownコードブロックは不要です。

## ログ

ログは `logs/YYYY-MM-DD.log` に保存されます。

記録対象:

- 起動
- 終了
- JSON解析
- VOICEVOX
- FFmpeg
- エラー

ログレベル:

- INFO
- WARNING
- ERROR

## VOICEVOX

デフォルト:

- URL: `http://127.0.0.1:50021`
- speaker id: `3`

VOICEVOXを起動してから「VOICEVOX音声生成」を押すと、`audio/voice.wav` を作成します。
`subtitles.txt` が存在する場合、字幕キューごとに音声を個別に生成・結合し、実際の音声の長さに合わせて字幕のタイミング（秒数）を自動的に補正・同期します。これにより、音声と字幕のズレが発生しません。

## FFmpeg

確認:

```powershell
ffmpeg -version
```

動画生成の入力:

- `images/001.png` などの画像
- `audio/voice.wav`
- `assets/bgm` 内のBGM（任意）
- `subtitles.txt` の時間付き字幕（任意）

出力:

- `video/final.mp4`

## BGM

`assets/bgm` に `mp3` または `wav` を入れるだけで、動画生成時に自動で使用されます。

デフォルト:

- BGMを使用する: ON
- ナレーション音量: 100%
- BGM音量: 20%
- BGMの開始: 約0.5秒フェードイン
- BGMの終了: 動画終了時にBGMだけ1秒フェードアウト

`assets/bgm` に複数ファイルがある場合は、ファイル名順で最初の1曲を使用します。BGMが動画より短い場合は自動でループし、動画より長い場合は動画の終了位置で切ります。

BGMが無い場合は、従来通りナレーションのみで動画を生成します。エラーにはなりません。

設定画面では「BGMを使用する」と「BGM音量」を変更できます。「BGMフォルダを開く」から `assets/bgm` を直接開けます。

## 字幕焼き込み

ChatGPT JSONの `subtitles` に時間付き字幕が含まれている場合、動画生成時に `video/subtitles.ass` を作成し、FFmpegで `video/final.mp4` に焼き込みます。

字幕形式:

```json
"subtitles": [
  {
    "start": 0.0,
    "end": 2.8,
    "text": "ブラックホールは宇宙で最も謎の天体です"
  }
]
```

ルール:

- `start` と `end` は秒数の数値
- 1字幕は1〜2行程度
- 1字幕の表示時間は約2〜4秒
- スマホ縦動画で読みやすい短い文章
- JSON以外の説明文やMarkdownコードブロックは不要

字幕設定:

- 字幕を使用する: ON/OFF
- 字幕フォントサイズ: デフォルト64
- 字幕位置: 下 / 中央 / 上
- 字幕アウトライン太さ: デフォルト4
- 字幕影: ON/OFF

字幕が無い場合は、従来通り字幕なしで動画を生成します。壊れた字幕データがある場合は、日本語のエラーメッセージを表示して動画生成を止めます。

## 進捗判定

- 台本: `script.txt` に内容がある
- 画像: 画像枚数分の `001.png` / `001.jpg` / `001.webp` がある
- 音声: `audio/voice.wav` がある
- 字幕: `video/subtitles.ass` がある
- 動画: `video/final.mp4` がある
- 投稿: `posted.txt` がある

## テスト

pytestで実行できます。

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory
python -m pytest tests -q --basetemp .pytest_tmp -o cache_dir=.pytest_cache
```

対象:

- parser
- project
- voicevox
- ffmpeg
- settings

## トラブルシューティング

### ChatGPTのJSON形式が正しくありません

JSON以外の説明文、Markdownコードブロック、余分なカンマ、閉じ忘れがないか確認してください。

### VOICEVOXが起動していません

VOICEVOXを起動してから再実行してください。URLやspeaker idも設定画面で確認できます。

### FFmpegが見つかりません

FFmpegをインストールし、PATHを通してください。PATHを通さない場合は設定画面で `FFmpeg path` を指定してください。

### BGMが入りません

`assets/bgm` に `mp3` または `wav` が入っているか確認してください。設定画面で「BGMを使用する」がONになっているかも確認してください。

### 字幕が表示されません

`subtitles.txt` に `start` / `end` / `text` を持つJSON配列が保存されているか確認してください。動画生成後に `video/subtitles.ass` が作成されているか、設定画面で「字幕を使用する」がONになっているかも確認してください。

### 字幕焼き込みに失敗します

FFmpegの字幕フィルターで失敗している可能性があります。`subtitles.ass` の形式、FFmpegの導入状況、フォントが見つからない可能性を確認してください。Windows標準の `Yu Gothic` を優先して使用します。

### 画像が1枚もありません

プロジェクトの `images` フォルダに `001.png` などの画像を入れてください。

### 動画プレビューできません

環境によってQt Multimediaで再生できない場合があります。「動画フォルダを開く」から `final.mp4` を直接確認してください。

## FAQ

### OpenAI APIは使いますか？

使いません。ChatGPTにはユーザーが手動で貼り付けます。

### 自動投稿しますか？

しません。Phase4.5では自動投稿は実装していません。

### 画像生成APIは使いますか？

使いません。画像プロンプトをコピーして、任意の画像生成ツールで使う前提です。

### JSONが壊れているとどうなりますか？

日本語のエラーメッセージを表示し、ファイル保存は行いません。

## アップデート履歴

- 0.5.0 Phase5: ASS字幕生成、FFmpeg字幕焼き込み、字幕設定、ChatGPT JSON字幕形式改善
- 0.4.6 Phase4.6: BGM自動追加、BGM音量設定、BGMフェードイン/フェードアウト
- 0.4.5 Phase4.5: 品質改善、ログ、サンプル、環境チェック、pytest追加
- 0.4.0 Phase4: JSON解析、VOICEVOX、FFmpeg、動画プレビュー
- 0.3.0 Phase3: 制作ウィザード、Dashboard、テンプレート
- 0.2.0 Phase2: PySide6化、プロジェクト管理、ネタ管理
- 0.1.0 Phase1: Tkinter MVP

## 今後のロードマップ

- 画像生成API連携
- 字幕焼き込み
- video-use本実装
- SQLite保存
- 投稿履歴管理
- 自動投稿

Phase5では、画像生成API、OpenAI API、Claude API、Gemini API、自動投稿、自動字幕生成AI、Whisper連携、字幕アニメーション、複数BGM、ジャンル別BGM、効果音は行っていません。
