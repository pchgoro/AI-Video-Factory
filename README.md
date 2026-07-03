# AI Video Factory

AI Video Factory は、ショート動画制作をローカルPCで整理・半自動化するWindows用デスクトップアプリです。

Version: `0.5.2`  
Phase: `Phase5.2`

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

## 画像生成プロンプト一括コピー

Phase5.1では、`image_prompts.txt` または画面上の画像プロンプト一覧から、ChatGPTへ1回貼るだけで複数画像をまとめて生成できるプロンプトを作成できます。

使い方:

1. ChatGPT JSON回答を貼り付けて `image_prompts.txt` を保存します。
2. 「一括画像生成」タブで生成内容をプレビューします。
3. 必要なら内容を編集します。
4. 「画像生成プロンプトをコピー」を押します。
5. ChatGPTへ貼り付けて、まとめて画像生成します。

対応画像枚数:

- 3枚
- 4枚
- 5枚
- 6枚
- 8枚

設定画面の「画像共通条件」で、全画像に共通する条件を自由に編集できます。デフォルトは `9:16`、`4K`、`文字なし`、`リアル`、`映画風`、`ドキュメンタリー風` です。

テンプレート別画像条件:

- 宇宙: 映画風、NASA風、リアルな宇宙ドキュメンタリー
- 株: 近未来、ビジネス、シンプル
- AIニュース: 近未来、テクノロジー、ドキュメンタリー
- 歴史: 映画風、リアル、歴史ドキュメンタリー
- 猫: 暖かい、柔らかい光、かわいい

生成プロンプトの末尾には、構図・距離・アングル・演出を画像ごとに変える指示、文字・ロゴ・ウォーターマークを入れない指示、世界観を統一する指示が自動で追加されます。

この機能はChatGPTへ手動で貼り付けるためのテキストを作るだけです。画像生成APIや自動画像生成は追加していません。

## 画像一括取り込み

Phase5.2では、ChatGPTなどで生成した複数画像をまとめて取り込み、プロジェクトの `images` フォルダへ `001.png`, `002.png`, `003.png` の形式で自動保存できます。

取り込み方法:

- 素材管理タブのドラッグ＆ドロップ領域へ画像をドロップ
- 「画像ファイルを選択」から複数画像を選択
- エクスプローラーで画像ファイルをコピーして、アプリ上で Ctrl+V
- クリップボード内の画像データを Ctrl+V で貼り付け

対応形式:

- `png`
- `jpg`
- `jpeg`
- `webp`

保存時は必ずPNGへ変換され、`projects/<project>/images/001.png` から連番で保存されます。既存画像がある場合は、「上書きする」「追加する」「キャンセル」を選べます。

取り込み済み画像はサムネイル一覧で確認できます。各画像にはファイル名、削除ボタン、上へ/下へボタンがあり、順番を変えると自動で `001.png` からリネームし直します。

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

## タイトル表示

動画プロジェクトの `title.txt` にタイトルが入力されている場合、動画の上部などにタイトルを焼き込んで常時または一定時間表示できます。

タイトル設定:

- タイトルを表示: ON/OFF
- タイトルサイズ: デフォルト72
- タイトル位置: 上 / 中央 / 下
- 半透明背景: ON/OFF (半透明黒色の背景ボックスを表示して視認性を高めます)
- タイトル表示時間: 常に表示 / 3秒 / 5秒 / 10秒

タイトルが14文字を超える場合、自動的に適切な位置で最大2行に改行されて表示されます。タイトル表示が有効で、`title.txt` が存在しないか空の場合は、日本語のエラーメッセージが表示されて動画生成が停止します。

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

- 0.5.2 Phase5.2: 画像一括取り込み、ドラッグ＆ドロップ、Ctrl+V貼り付け、PNG自動変換、001.png形式への自動リネーム、サムネイル一覧と順番変更
- 0.5.1 Phase5.1: 画像生成プロンプト一括コピー、画像枚数自動対応、共通画像条件編集、テンプレート別画像条件対応
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
