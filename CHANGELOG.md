# Changelog

## v0.13.1
- Gemini Story Providerを追加
- `google-genai` SDK + Structured Outputsに対応
- default Story ProviderをGeminiへ変更
- `gemini-3.5-flash-lite` / `gemini-3.5-flash` / `gemini-3.6-flash` のmodel catalogを追加
- Free-tier-only guardを追加し、Project Tier Free / Billing disabled確認を必須化
- API key fingerprintによるGemini確認無効化に対応
- Gemini local usage safety capとusage metricsを追加
- Gemini固有のquota / rate limit / safety / finish reason分類を追加
- Story Composer UIへGemini設定と課金リスク表示を追加

## v0.13.0
- Story AI Provider基盤を追加
- OpenAI Responses API + Structured OutputsによるStory生成に対応
- default modelを`gpt-5.6-luna`に設定し、Terra/Sol/Custom model IDを選択可能に変更
- Mock Story ProviderとProvider Managerを追加
- `story_generation.json`へ生成状態、retry、token metrics、料金推定snapshotを保存
- 生成Storyを候補ファイルへ保存し、`Use Generated Story`で明示採用する流れを追加
- Story ComposerへGenerate/Cancel/Retry/Resume/Preview/Use Generated Story UIを追加
- `logs/story_provider.log`と`OPENAI_API_KEY`設定を追加

## v0.12.0
- Automated Production Orchestratorを追加
- `production_run.json` にProductionRun / Step状態を保存
- Step AdapterでStory Export、画像生成、VOICEVOX、字幕生成、動画render、YouTube/TikTok uploadを順番実行
- Preflight / Dry Run / Resume / Retry / Cancelに対応
- 既存成果物reuseとstale判定を追加
- `.production.lock` による同一project二重Run防止を追加
- Automated Production専用Widgetと `logs/production.log` を追加

## v0.11.0
- Story Composerを追加
- Story / SceneモデルとStory JSON schemaを追加
- ManualPromptProviderによる手動AI用Prompt生成を追加
- story.json / story_manifest.json保存、Resume、Resetに対応
- Story validationとExport Previewを追加
- StoryFactoryAdapterで既存Factoryファイルへの明示Exportに対応
- Export時のバックアップとcontent_source記録に対応
- 既存ChatGPT取込、画像生成、VOICEVOX、render、YouTube/TikTok処理とは独立して動作

## v0.10.2
- Prompt Library + Theme Templatesを追加
- YAMLテンプレートのschema検証、安全読み込み、単一継承mergeに対応
- generic_space / black_hole / star / planet / galaxy / nebula / solar_system の初期templateを追加
- project topic / title / category / genre / series / tags / image promptによるAuto theme判定を追加
- Manual template選択、Resolved Template表示、Reload Templatesに対応
- Prompt Optimizerへtemplate ruleとscene選択を統合
- image_generation_manifest.jsonへtemplate判定・適用/skip情報を保存

## v0.10.1
- Image Prompt Optimizerを追加
- Optimizer ON/OFFとpromptプレビューを追加
- sceneごとの構図差別化と衝突回避に対応
- Cloudflare prompt上限に合わせた段階的圧縮を追加
- optimizer詳細をimage_generation_manifest.jsonへ保存

## v0.10.0
- Cloudflare Workers AIによる画像生成基盤を追加
- `@cf/black-forest-labs/flux-1-schnell` で `image_prompts.txt` から不足画像を生成
- `001.png` 形式でのatomic保存とmanifest保存に対応
- 既存画像skip、retry、cancel、ローカル利用上限を追加
- 素材管理に最小限のAI Image Generation UIを追加
- OpenAI provider / OpenAI SDKは未実装

## v0.9.0
- TikTok OAuth v2 / Desktop Login Kit / PKCEに対応
- TikTok Content Posting APIのUpload Contentに対応
- 完成済み `final.mp4` のTikTok Inboxアップロードを追加
- TikTok Status Fetchと `SEND_TO_USER_INBOX` 表示に対応
- `tiktok_upload` 状態保存、duplicate prevention、retryを追加
- `logs/tiktok.log` の専用ログを追加
- 制作ウィザードに最小限のTikTok Upload UIを追加

## v0.8.0
- Job systemを追加
- project.jsonへ制作状態とYouTube upload状態の永続化を追加
- YouTube Data API v3 / OAuthによるPRIVATEアップロードを追加
- resumable uploadと一時エラーretryに対応
- YouTube video IDによる重複アップロード防止を追加
- Windows Credential Managerを利用したrefresh token保存に対応
- 制作ウィザードに最小限のYouTube Upload UIを追加
- logs/youtube.log の専用ログを追加

## v0.7.4
- ジャンル配下のカテゴリ管理を追加
- プロジェクトへカテゴリ項目を追加
- ジャンル・カテゴリ・シリーズの階層フィルターを追加
- 複合フィルターと絞り込み解除に対応
- 未分類プロジェクトの整理機能を追加
- 複数プロジェクトの一括カテゴリ変更に対応
- カテゴリ別Analyticsを追加
- AIアドバイザーの提案にカテゴリ情報を反映

## v0.7.3
- YouTube Studioの表データ・グラフデータ・合計CSV取込に対応
- CSVと各プロジェクトの自動紐付けを追加
- 未紐付け動画の手動紐付けに対応
- プロジェクトごとのYouTube / TikTok成績表示を追加
- 個別動画グラフ用の推移データ読込を追加
- 5段階評価と伸びた理由分析を追加
- 次回改善案と続編テーマ提案を追加
- YouTube / TikTok横断比較を追加

## v0.6.5.1
- Light Effect有効時のFFmpegフィルターエラーを修正
- イントロ・エンディングの表示時間設定を追加
- イントロ・エンディングのズーム設定を追加
- 素材音声、BGM、素材音声+BGM、無音を個別に選択可能に変更
- イントロ・エンディングのBGM音量設定を追加

## v0.6.5
- Motion Engineを追加
- Ken BurnsとRandom Motionに対応
- 画像ごとの自動Motion割り当てを追加
- トランジションを追加
- `assets/overlay` によるOverlayに対応
- Light Effectを追加

## v0.7.1
- AIアドバイザーを追加
- Rule Engineによるおすすめテーマ提案を追加
- CSVタイトル分析からおすすめタイトルを生成
- 次の企画と改善ポイントを表示
- 制作目標、実績バッジ、ネタ在庫、毎日の一言を追加

## v0.7.0
- Analyticsタブを追加
- YouTube Studio / TikTok Studio CSV分析に対応
- 集計、ランキング、ジャンル分析、タイトル分析を追加
- matplotlibによるグラフ表示を追加
- 動画ごとの5段階評価と分析コメントを追加
- 検索と分析結果CSVエクスポートに対応

## v0.6.0
- オープニング追加機能
- エンディング追加機能
- 総集編動画生成
- 総集編タブをホーム/制作ウィザードと同じ階層へ移動
- ジャンル別の動画一覧と結合順の変更に対応
- chapter.txt生成

## v0.5.3.5
- 左側のプロジェクト一覧と一括ネタ管理の縦幅を調整できるように変更
- 素材管理の取り込み済み画像エリアと素材一覧の縦幅を調整できるように変更
- 取り込み済み画像エリアに高さ入力を追加し、数値で縦幅を変更できるように修正

## v0.5.3.4
- YouTubeタグ保存とTikTokタグ保存を分離
- `hashtags.txt` からYouTube向けタグを `#` なし・カンマ区切りで自動入力
- `hashtags.txt` からTikTok向けタグを `#` 付きで自動入力し、`#VOICEVOX` を自動追加
- 一括ネタ管理の下に10個の制作メモ欄を追加
- メモ、テーマ、YouTubeタグ、TikTokタグのワンクリックコピーに対応
- 左側の操作エリアをスクロール可能に変更

## v0.5.3.3
- 字幕の下位置をTikTok / YouTube Shortsの詳細表示に重なりにくい高さへ調整
- 字幕の下位置を画面中央の少し下に表示される安全位置へ変更

## v0.5.3.2
- 制作ウィザードから不要なSTEP6字幕を削除
- STEP完了後も現在のプロジェクトに滞在するように修正
- 次に押すボタンや入力欄をハイライトするガイドを追加

## v0.5.3.1
- タイトルデザインプリセットを追加
- タイトル背景デザインを改善 (余白、透明度、横幅%などをカスタマイズ可能に)
- 強調キーワード記法 (`【】`) に対応
- タイトル装飾ライン (━) を追加
- タイトル表示設定を拡張 (位置として左寄せなどを追加)

## v0.5.3
- タイトルオーバーレイ機能を追加
- タイトル背景を追加
- タイトル表示時間設定を追加
- タイトル位置設定を追加

## v0.5.2
- 画像一括取り込み機能を追加
- ドラッグ＆ドロップに対応
- Ctrl+V貼り付けに対応
- PNG自動変換に対応
- 001.png形式への自動リネームに対応
- サムネイル一覧と順番変更を追加

## v0.5.1
- 画像生成プロンプト一括コピー機能を追加
- 画像枚数自動対応
- テンプレート別画像条件対応
- 共通画像条件編集機能追加

## v0.5.0
- ASS字幕生成機能を追加
- FFmpeg字幕焼き込みに対応
- 字幕設定を追加
- ChatGPT JSONの subtitles 形式を改善

## v0.4.6
- BGM追加
- BGMフェードアウト
- BGM音量設定

## v0.4.5
- テスト追加
- バグ修正
- ログ追加

## v0.4.0
- VOICEVOX連携
- FFmpeg連携
- JSON対応
