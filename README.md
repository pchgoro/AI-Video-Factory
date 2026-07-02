# AI Video Factory

AI Video Factory は、ショート動画制作をローカルPCで進めるためのWindows用デスクトップアプリです。

Phase4では **動画制作の自動化率を上げる** ため、ChatGPT出力のJSON化、VOICEVOX音声生成、FFmpeg動画生成、完成動画プレビューを追加しました。OpenAI APIや画像生成APIは使わず、ChatGPTにはユーザーが手動で貼り付けます。

## セットアップ

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory
python -m pip install -r requirements.txt
```

## 起動

```powershell
python app\main.py
```

または `run_app.bat` をダブルクリックします。

## ChatGPT JSON出力形式

Phase4のプロンプトは、ChatGPTに以下のJSONだけを返すよう指示します。

```json
{
  "title": "",
  "script": "",
  "voice_text": "",
  "image_prompts": [
    "",
    "",
    ""
  ],
  "subtitles": [
    {
      "text": "",
      "start": "",
      "end": ""
    }
  ],
  "hashtags": [
    ""
  ]
}
```

JSON以外の説明文やMarkdownコードブロックは不要です。画像プロンプトは英語、9:16、文字なし、TikTok / YouTube Shorts向けになるように指定しています。

## JSON貼り付けインポート

「JSON回答貼り付け」へChatGPTの回答を貼ると、0.5秒後に自動解析します。

成功すると以下へ保存します。

- `title.txt`
- `script.txt`
- `voice.txt`
- `image_prompts.txt`
- `subtitles.txt`
- `hashtags.txt`
- `raw_chatgpt.txt`

旧形式の「タイトル：」「ナレーション：」「画像プロンプト1：」にも一応対応しています。

## VOICEVOX連携

VOICEVOX Engineが起動している前提で、ローカルAPIから音声を生成します。

デフォルト設定:

- URL: `http://127.0.0.1:50021`
- speaker id: `3`

手順:

1. VOICEVOXを起動します。
2. アプリでChatGPT回答を解析し、`voice.txt` を作ります。
3. 「VOICEVOX音声生成」を押します。
4. `audio/voice.wav` が生成されます。

設定画面で VOICEVOX Engine URL と speaker id を変更できます。

## FFmpeg導入

FFmpegをインストールし、`ffmpeg` がPowerShellから実行できるようPATHを設定してください。

確認:

```powershell
ffmpeg -version
```

PATHを通さない場合は、設定画面の `FFmpeg path` に `ffmpeg.exe` のフルパスを指定します。

## 動画生成

入力:

- `images` フォルダ内の画像
- `audio/voice.wav`

出力:

- `video/final.mp4`

条件:

- 1080x1920 縦動画
- 音声がある場合は音声の長さに合わせて画像尺を自動配分
- 音声がない場合は1画像あたり5秒
- Ken Burns風のゆっくりズーム
- 字幕焼き込み、BGM、自動投稿は今回は未実装

設定画面で以下を変更できます。

- FFmpeg path
- 出力幅
- 出力高さ
- 1画像あたりの秒数
- ズーム有無

## 完成動画プレビュー

`video/final.mp4` が存在する場合、「完成動画プレビュー」タブで再生できます。

最低限の操作:

- 再生
- 一時停止
- 最初に戻る
- 動画フォルダを開く

環境によってQt Multimediaで再生できない場合は、動画フォルダを開いて確認してください。

## 画像プロンプト管理

`image_prompts.txt` を読み込み、画像ごとに表示します。

各画像でできること:

- プロンプトをコピー
- 画像フォルダを開く
- 生成済みにする

生成済み判定:

- 画像1: `images/001.png` / `001.jpg` / `001.webp`
- 画像2: `images/002.png` / `002.jpg` / `002.webp`
- 画像3以降も同様

「生成済みにする」は管理用の仮 `001.png` を作成します。あとで本物の画像に差し替えてください。

## 進捗チェック

- 台本: `script.txt` に内容がある
- 画像: `images` に画像枚数分の `001.png` 形式の画像がある
- 音声: `audio/voice.wav` がある
- 動画: `video/final.mp4` がある
- 投稿: `posted.txt` がある

## よくあるエラー

### JSON解析エラー

ChatGPTの回答に説明文、Markdownコードブロック、余分なカンマ、閉じ忘れがある可能性があります。JSONだけを貼り付けてください。

### VOICEVOXエラー

VOICEVOXが起動していない可能性があります。VOICEVOXを起動してから再実行してください。

### FFmpegエラー

FFmpegが見つからない可能性があります。`ffmpeg -version` を確認し、必要なら設定画面で `ffmpeg.exe` のパスを指定してください。

### 動画プレビューできない

Qt Multimediaが環境側で再生できない場合があります。「動画フォルダを開く」から `final.mp4` を直接確認してください。

## アーキテクチャ

UIと処理を分離するため、MVCに近い構成を維持しています。

```text
app
├─ main.py
├─ config.py
├─ models.py
├─ dialogs
│  └─ settings_dialog.py
├─ services
│  ├─ dashboard_service.py
│  ├─ parser.py
│  ├─ project_service.py
│  ├─ prompt_builder.py
│  ├─ settings_service.py
│  ├─ template_service.py
│  ├─ topic_service.py
│  ├─ video_render_service.py
│  └─ voicevox_service.py
├─ video_editors
│  ├─ base.py
│  ├─ factory.py
│  ├─ ffmpeg_editor.py
│  ├─ video_use_editor.py
│  └─ future_editor.py
└─ views
   └─ main_window.py
```

## 今回は実装しないもの

- 画像生成API連携
- 自動投稿
- BGM自動選択
- 字幕焼き込み
- video-use本実装

自動投稿は今回は行いません。
