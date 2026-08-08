# AI Video Factory

## Public Website for TikTok Developer Portal

A minimal static public website is available in `website/` for TikTok Developer
Portal Sandbox / Production review fields.

Pages:

- `/` - CosmicVideoFactory overview
- `/terms` - Terms of Service
- `/privacy` - Privacy Policy

The site is bilingual Japanese/English, has no database, no external API, and
no personal information form. It is independent from the desktop application.

Local check:

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory\website
python -m http.server 8080
```

Vercel deployment:

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory\website
vercel
vercel --prod
```

Example TikTok Developer Portal URLs after deployment:

- Web/Desktop URL: `https://your-vercel-domain.vercel.app/`
- Terms of Service URL: `https://your-vercel-domain.vercel.app/terms`
- Privacy Policy URL: `https://your-vercel-domain.vercel.app/privacy`

## Automated Production Orchestrator (Phase 7)

Automated Production is an optional one-click workflow that starts from a valid
`projects/<project>/story.json` and runs the selected production steps in order.

Default flow:

1. Story load
2. Story validation
3. Export to Factory
4. Image generation
5. VOICEVOX audio generation
6. Subtitle generation
7. Video render
8. YouTube PRIVATE upload
9. TikTok Upload Content

Each step can be turned ON/OFF before the run. Upload steps are OFF by default
and must be explicitly enabled. The orchestrator does not generate a new Story,
does not call external LLMs, does not schedule posts, and does not publish
YouTube or TikTok videos publicly.

Safety features:

- `projects/<project>/production_run.json` stores run status, step status,
  outputs, preflight results, and resume data.
- `projects/<project>/.production.lock` prevents two runs for the same project.
- `Dry Run` checks the plan and existing artifacts without calling Cloudflare,
  VOICEVOX, FFmpeg, YouTube, TikTok, or writing Factory outputs.
- Existing valid artifacts can be reused after validation.
- YouTube video IDs and TikTok publish IDs prevent duplicate uploads.
- Stale detection uses SHA-256 for small input files and mtime/size/format
  validation for large artifacts.
- `logs/production.log` records run and step activity without tokens, raw API
  responses, upload URLs, Base64 images, or full prompts.

Artifact freshness states:

- `fresh`: valid and current enough to reuse
- `stale`: valid but older than an input it depends on
- `missing`: required artifact is not present
- `invalid`: artifact exists but failed validation
- `unknown`: not enough information to decide

Use `Run Preflight` before a normal run. Preflight errors block `Start
Production`; warnings can be reviewed before proceeding. `Cancel` stops new
steps and asks cancellable services to stop at their next safe boundary.

## Story Composer (Phase 6)

Story Composer is an optional workflow for designing the story before exporting it into the existing Factory files.

Canonical file when using Story Composer:

```text
projects/<project>/story.json
```

Derived files are written only when you press `Export to Factory`:

```text
title.txt
script.txt
voice.txt
image_prompts.txt
subtitles.txt
hashtags.txt
memo.txt
```

Story Composer does not call OpenAI, Claude, Gemini, Cloudflare LLM, local LLMs, image generation, VOICEVOX, video rendering, or YouTube/TikTok upload. `Generate Prompt` only creates a copy/paste prompt for manual AI use. `Import Story JSON` parses and validates pasted JSON, then saves `story.json` and `story_manifest.json`.

Basic workflow:

1. Open a project and go to `Story Composer`.
2. Set Theme, Scene Count, and Estimated Duration.
3. Press `Generate Prompt` and copy it to your AI tool manually.
4. Paste the returned JSON into `Raw Story JSON`.
5. Press `Import Story JSON`, then `Validate`.
6. Use `Export Preview` to confirm which Factory files will be created or overwritten.
7. Press `Export to Factory` only when ready.

Export safety:

- Validation errors block export.
- Validation warnings can be exported only after confirmation.
- Existing derived files are backed up to `projects/<project>/backups/story_export_<timestamp>/`.
- Reset deletes only `story.json` and `story_manifest.json`.
- Existing images, audio, `video/final.mp4`, YouTube state, and TikTok state are not deleted.

The existing ChatGPT JSON import workflow remains available and unchanged. The app records `content_source: story_composer` and `content_exported_at` in `project.json` only after a successful Story export.

## Prompt Library + Theme Templates（Phase 5.2）

AI Image GenerationのPrompt Optimizerは、`prompt_library/` のYAMLテンプレートを読み込み、画像生成promptへテーマ別の補助ルールを適用できます。外部LLM、新しい画像生成provider、OpenAI API、Claude API、自動翻訳は使いません。

標準ライブラリ:

- `prompt_library/generic_space.yaml`
- `prompt_library/themes/black_hole.yaml`
- `prompt_library/themes/star.yaml`
- `prompt_library/themes/planet.yaml`
- `prompt_library/themes/galaxy.yaml`
- `prompt_library/themes/nebula.yaml`
- `prompt_library/themes/solar_system.yaml`

テンプレートは原文promptを置き換えるものではありません。`image_prompts.txt` を正本として保持し、主役、天体名、数量、色、カメラアングル、画風、図解や文字指定が原文にある場合は原文を優先します。Optimizer OFFの場合はテンプレートルールも適用せず、原文promptをそのままproviderへ渡します。

Auto判定は `project topic`、`title`、`category / genre / series`、`tags`、`image_prompts.txt` の順に重み付けして判定します。判定不能な場合は `generic_space` にフォールバックします。Manualでは画面から `Generic Space / Black Hole / Star / Planet / Galaxy / Nebula / Solar System` を選択できます。

YAML読み込みは `yaml.safe_load` を使い、`.yaml` / `.yml` だけを標準 `prompt_library/` 配下から読み込みます。hidden/temp file、symlink、過大ファイル、未知parent、循環継承、不正schemaは無効化し、アプリ全体は止めず `generic_space` へフォールバックします。

Manifestには各画像ごとに `selected_template`、`template_version`、`template_mode`、`manual_template`、`detected_keywords`、`matched_sources`、`candidate_scores`、`resolution_reason`、`inherited_templates`、`selected_scene`、`scene_rule_applied`、`skipped_scene_reason`、`applied_template_rules`、`skipped_template_rules`、`template_warnings` を保存します。API token、Account ID、Authorization、raw response、Base64画像は保存しません。

﻿# AI Video Factory

## Image Prompt Optimizer（Phase 5.1）

AI Image Generation欄の `Prompt Optimizer ON` を有効にすると、`image_prompts.txt` の原文promptを正本として保持したまま、Cloudflare Workers AI向けにルールベースの補強語句を追加します。外部LLM、OpenAI API、Claude API、自動翻訳、ChatGPT/Codex自動操作は使用しません。

- OFF: `image_prompts.txt` の原文promptをそのままCloudflareへ送信します。既存の自動suffix追加も行いません。
- ON: 原文を先頭に保持し、映画風・ドキュメンタリー風の品質語句、sceneごとの構図差別化、最小限の禁止語句を追加します。
- `Original Prompt` / `Optimized Prompt` / `Applied Rules` / `Skipped Rules` / `Prompt Length` をプレビューできます。
- `Refresh Preview` はAPIを呼びません。画像生成も動画生成も投稿も開始しません。
- `Copy Optimized Prompt` で最適化後promptだけをクリップボードへコピーできます。

Optimizerは原文の主役、天体名、数量、色、カメラアングル、時代、場所、出来事、画風、文字や図解の明示指示を勝手に変更しません。たとえば `anime style` がある場合は写実指定を追加せず、`diagram with labels` がある場合は `no text` を追加しません。`close-up` など構図指定がある場合はscene構図テンプレートを適用せず、manifestの `skipped_rules` に理由を保存します。

Cloudflare公式仕様で `@cf/black-forest-labs/flux-1-schnell` の `prompt` は `maxLength: 2048` です。Optimizerはこの文字数上限を超えないよう、重複語句の削除、低優先度語句の削除、構図テンプレート短縮、禁止語句の最小化、句読点整理の順に圧縮します。元prompt単体が2048文字を超える場合は原文を自動編集せず、APIを呼ばずに停止します。

生成manifestには `original_prompt`、`optimized_prompt`、`optimizer_enabled`、`optimizer_version`、`scene_index`、`scene_composition`、`applied_rules`、`skipped_rules`、`removed_rules`、`original_length`、`optimized_length`、`max_prompt_length`、`was_compacted`、`was_truncated` を保存します。API token、Authorization header、API response全文、Base64画像は保存しません。

AI Video Factory 縺ｯ縲√す繝ｧ繝ｼ繝亥虚逕ｻ蛻ｶ菴懊ｒ繝ｭ繝ｼ繧ｫ繝ｫPC縺ｧ謨ｴ逅・・蜊願・蜍募喧縺吶ｋWindows逕ｨ繝・せ繧ｯ繝医ャ繝励い繝励Μ縺ｧ縺吶・

Version: `0.7.4`
Phase: `Phase7.4`

## Cloudflare Workers AI Image Generation・・hase 5・・
AI Image Generation 縺ｯ縲∽ｿ晏ｭ俶ｸ医∩縺ｮ `image_prompts.txt` 繧呈ｭ｣譛ｬ縺ｨ縺励※ Cloudflare Workers AI 縺ｧ荳崎ｶｳ逕ｻ蜒上□縺代ｒ逕滓・縺励∪縺吶０penAI provider縲＾penAI SDK縲，hatGPT閾ｪ蜍墓桃菴懊，odex縺ｫ繧医ｋ逕ｻ蜒冗函謌舌・莉雁屓譛ｪ螳溯｣・〒縺吶・
莠句燕貅門ｙ:

1. Cloudflare繧｢繧ｫ繧ｦ繝ｳ繝医ｒ菴懈・縺励∪縺吶・2. Cloudflare Dashboard縺ｧ Workers AI 繧呈怏蜉ｹ蛹悶＠縺ｾ縺吶・3. Account ID 繧堤｢ｺ隱阪＠縺ｾ縺吶・4. API Tokens 縺ｧ Workers AI 縺ｮ蠢・ｦ∵怙蟆乗ｨｩ髯舌ｒ謖√▽token繧剃ｽ懈・縺励∪縺吶・5. `.env.example` 繧貞盾閠・↓ `.env` 縺ｸ `CLOUDFLARE_ACCOUNT_ID` 縺ｨ `CLOUDFLARE_API_TOKEN` 繧定ｨｭ螳壹＠縺ｾ縺吶・
菴ｿ縺・婿:

1. ChatGPT JSON雋ｼ繧贋ｻ倥￠縺ｪ縺ｩ縺ｧ `image_prompts.txt` 繧剃ｿ晏ｭ倥＠縺ｾ縺吶・2. 繝励Ο繧ｸ繧ｧ繧ｯ繝医・逕ｻ蜒乗椢謨ｰ・・ / 4 / 5 / 6 / 8・牙・縺ｮ繝励Ο繝ｳ繝励ヨ縺後≠繧九％縺ｨ繧堤｢ｺ隱阪＠縺ｾ縺吶・3. 縲檎ｴ譚千ｮ｡逅・阪ち繝悶・ `AI Image Generation` 繧堤｢ｺ隱阪＠縺ｾ縺吶・4. `Generate Missing Images` 繧呈款縺励｝rovider縲［odel縲《teps縲∫函謌先椢謨ｰ縲∵耳螳壼茜逕ｨ驥上ｒ遒ｺ隱阪＠縺ｾ縺吶・5. 逕滓・逕ｻ蜒上・ `projects/<project>/images/001.png`縲～002.png` 縺ｮ蠖｢蠑上〒菫晏ｭ倥＆繧後∪縺吶・
蛻晄悄繝｢繝・Ν縺ｯ `@cf/black-forest-labs/flux-1-schnell` 縺ｧ縺吶る∽ｿ｡縺吶ｋrequest縺ｯ蜈ｬ蠑上↓遒ｺ隱阪〒縺阪ｋ `prompt` 縺ｨ `steps` 縺ｮ縺ｿ縺ｧ縺吶Ａsteps` 縺ｯ1縲・縺ｧ縺吶ゅΔ繝・Ν縺ｸ譛ｪ遒ｺ隱阪・width/height謖・ｮ壹・騾√ｉ縺壹，loudflare縺瑚ｿ斐＠縺溽判蜒上ｒ蠑輔″莨ｸ縺ｰ縺輔★縺ｫ縲∽ｿ晏ｭ俶凾縺ｫ蜍慕判繧ｵ繧､繧ｺ・磯壼ｸｸ1080x1920・峨∈荳ｭ螟ｮ繧ｯ繝ｭ繝・・縺ｧ豁｣隕丞喧縺励∪縺吶・
Cloudflare Workers AI縺ｮ辟｡譁吝牡蠖薙・迴ｾ蝨ｨ `10,000 Neurons/day`縲√Μ繧ｻ繝・ヨ蝓ｺ貅悶・UTC縺ｧ縺吶ゅい繝励Μ蜀・・蛻ｩ逕ｨ驥剰｡ｨ遉ｺ縺ｯ繝ｭ繝ｼ繧ｫ繝ｫ謗ｨ螳壹〒縲，loudflare Dashboard縺ｮ螳滉ｽｿ逕ｨ驥上→蟾ｮ縺悟・繧句庄閭ｽ諤ｧ縺後≠繧翫∪縺吶ゅ悟ｮ悟・辟｡譁吶阪→縺ｯ髯舌ｉ縺壹￣aid plan縺ｧ縺ｯ辟｡譁呎棧雜・℃蛻・′隱ｲ驥大ｯｾ雎｡縺ｫ縺ｪ繧句庄閭ｽ諤ｧ縺後≠繧翫∪縺吶・
譌｢蟄倥・豁｣蟶ｸ逕ｻ蜒上・荳頑嶌縺阪○縺嘖kip縺励∪縺吶ょ｣翫ｌ縺溽判蜒上・逕滓・蟇ｾ雎｡縺ｨ縺励※謇ｱ縺・∪縺吶′縲∬・蜍募炎髯､縺ｯ縺励∪縺帙ｓ縲ら函謌仙ｾ後↓蜍慕判逕滓・繧ШouTube/TikTok謚慕ｨｿ縺ｯ閾ｪ蜍募ｮ溯｡後＆繧後∪縺帙ｓ縲・
Phase5縺ｧ縺ｯ縲，hatGPT JSON縺ｮ譎る俣莉倥″蟄怜ｹ輔°繧陰SS蟄怜ｹ輔ｒ逕滓・縺励：Fmpeg縺ｧ蜍慕判縺ｸ辟ｼ縺崎ｾｼ繧√ｋ繧医≧縺ｫ縺励∪縺励◆縲・

## 迺ｰ蠅・ｧ狗ｯ・

謗ｨ螂ｨ:

- Windows
- Python 3.10莉･荳・
- VOICEVOX Engine
- FFmpeg

繧ｻ繝・ヨ繧｢繝・・:

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory
python -m pip install -r requirements.txt
```

襍ｷ蜍・

```powershell
python app\main.py
```

縺ｾ縺溘・ `run_app.bat` 繧偵ム繝悶Ν繧ｯ繝ｪ繝・け縺励∪縺吶・

## 蛻晏屓繧ｻ繝・ヨ繧｢繝・・

1. 繧｢繝励Μ繧定ｵｷ蜍輔＠縺ｾ縺吶・
2. 縲瑚ｨｭ螳壹阪ｒ髢九″縺ｾ縺吶・
3. 縲檎腸蠅・メ繧ｧ繝・け縲阪ｒ謚ｼ縺励∪縺吶・
4. Python縲：Fmpeg縲〃OICEVOX縲｝rojects / exports / assets縲∵嶌縺崎ｾｼ縺ｿ讓ｩ髯舌ｒ遒ｺ隱阪＠縺ｾ縺吶・
5. FFmpeg縺係ARNING縺ｮ蝣ｴ蜷医・FFmpeg繧偵う繝ｳ繧ｹ繝医・繝ｫ縺吶ｋ縺九～FFmpeg path` 縺ｫ `ffmpeg.exe` 縺ｮ繝代せ繧貞・繧後∪縺吶・
6. VOICEVOX縺係ARNING縺ｮ蝣ｴ蜷医・VOICEVOX繧定ｵｷ蜍輔＠縺ｦ縺九ｉ蜀咲｢ｺ隱阪＠縺ｾ縺吶・

## 5蛻・〒隧ｦ縺呎婿豕・

1. 譁ｰ隕上・繝ｭ繧ｸ繧ｧ繧ｯ繝医ｒ菴懈・縺励∪縺吶・
2. `samples/space.json` 縺ｮ蜀・ｮｹ繧偵さ繝斐・縺励∪縺吶・
3. 繧｢繝励Μ縺ｮ縲繰SON蝗樒ｭ碑ｲｼ繧贋ｻ倥￠縲阪↓雋ｼ繧贋ｻ倥￠縺ｾ縺吶・
4. `sample_images/001.png`縲～002.png`縲～003.png` 繧偵・繝ｭ繧ｸ繧ｧ繧ｯ繝医・ `images` 繝輔か繝ｫ繝縺ｸ繧ｳ繝斐・縺励∪縺吶・
5. VOICEVOX繧定ｵｷ蜍輔＠縺ｦ縲祁OICEVOX髻ｳ螢ｰ逕滓・縲阪ｒ謚ｼ縺励∪縺吶・
6. FFmpeg繧剃ｽｿ縺医ｋ迥ｶ諷九↓縺励※縲熊Fmpeg蜍慕判逕滓・縲阪ｒ謚ｼ縺励∪縺吶・
7. `video/final.mp4` 繧偵悟ｮ梧・蜍慕判繝励Ξ繝薙Η繝ｼ縲阪∪縺溘・Explorer縺ｧ遒ｺ隱阪＠縺ｾ縺吶・

繧ｵ繝ｳ繝励Ν:

- `samples/space.json`
- `samples/stock.json`
- `samples/history.json`
- `samples/cat.json`
- `samples/ai.json`
- `sample_images/001.png`
- `sample_images/002.png`
- `sample_images/003.png`

## 逕ｻ蜒冗函謌舌・繝ｭ繝ｳ繝励ヨ荳諡ｬ繧ｳ繝斐・

Phase5.1縺ｧ縺ｯ縲～image_prompts.txt` 縺ｾ縺溘・逕ｻ髱｢荳翫・逕ｻ蜒上・繝ｭ繝ｳ繝励ヨ荳隕ｧ縺九ｉ縲，hatGPT縺ｸ1蝗櫁ｲｼ繧九□縺代〒隍・焚逕ｻ蜒上ｒ縺ｾ縺ｨ繧√※逕滓・縺ｧ縺阪ｋ繝励Ο繝ｳ繝励ヨ繧剃ｽ懈・縺ｧ縺阪∪縺吶・

菴ｿ縺・婿:

1. ChatGPT JSON蝗樒ｭ斐ｒ雋ｼ繧贋ｻ倥￠縺ｦ `image_prompts.txt` 繧剃ｿ晏ｭ倥＠縺ｾ縺吶・
2. 縲御ｸ諡ｬ逕ｻ蜒冗函謌舌阪ち繝悶〒逕滓・蜀・ｮｹ繧偵・繝ｬ繝薙Η繝ｼ縺励∪縺吶・
3. 蠢・ｦ√↑繧牙・螳ｹ繧堤ｷｨ髮・＠縺ｾ縺吶・
4. 縲檎判蜒冗函謌舌・繝ｭ繝ｳ繝励ヨ繧偵さ繝斐・縲阪ｒ謚ｼ縺励∪縺吶・
5. ChatGPT縺ｸ雋ｼ繧贋ｻ倥￠縺ｦ縲√∪縺ｨ繧√※逕ｻ蜒冗函謌舌＠縺ｾ縺吶・

蟇ｾ蠢懃判蜒乗椢謨ｰ:

- 3譫・
- 4譫・
- 5譫・
- 6譫・
- 8譫・

險ｭ螳夂判髱｢縺ｮ縲檎判蜒丞・騾壽擅莉ｶ縲阪〒縲∝・逕ｻ蜒上↓蜈ｱ騾壹☆繧区擅莉ｶ繧定・逕ｱ縺ｫ邱ｨ髮・〒縺阪∪縺吶ゅョ繝輔か繝ｫ繝医・ `9:16`縲～4K`縲～譁・ｭ励↑縺輿縲～繝ｪ繧｢繝ｫ`縲～譏逕ｻ鬚ｨ`縲～繝峨く繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ鬚ｨ` 縺ｧ縺吶・

繝・Φ繝励Ξ繝ｼ繝亥挨逕ｻ蜒乗擅莉ｶ:

- 螳・ｮ・ 譏逕ｻ鬚ｨ縲¨ASA鬚ｨ縲√Μ繧｢繝ｫ縺ｪ螳・ｮ吶ラ繧ｭ繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ
- 譬ｪ: 霑第悴譚･縲√ン繧ｸ繝阪せ縲√す繝ｳ繝励Ν
- AI繝九Η繝ｼ繧ｹ: 霑第悴譚･縲√ユ繧ｯ繝弱Ο繧ｸ繝ｼ縲√ラ繧ｭ繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ
- 豁ｴ蜿ｲ: 譏逕ｻ鬚ｨ縲√Μ繧｢繝ｫ縲∵ｭｴ蜿ｲ繝峨く繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ
- 迪ｫ: 證悶°縺・∵沐繧峨°縺・・縲√°繧上＞縺・

逕滓・繝励Ο繝ｳ繝励ヨ縺ｮ譛ｫ蟆ｾ縺ｫ縺ｯ縲∵ｧ句峙繝ｻ霍晞屬繝ｻ繧｢繝ｳ繧ｰ繝ｫ繝ｻ貍泌・繧堤判蜒上＃縺ｨ縺ｫ螟峨∴繧区欠遉ｺ縲∵枚蟄励・繝ｭ繧ｴ繝ｻ繧ｦ繧ｩ繝ｼ繧ｿ繝ｼ繝槭・繧ｯ繧貞・繧後↑縺・欠遉ｺ縲∽ｸ也阜隕ｳ繧堤ｵｱ荳縺吶ｋ謖・､ｺ縺瑚・蜍輔〒霑ｽ蜉縺輔ｌ縺ｾ縺吶・

縺薙・讖溯・縺ｯChatGPT縺ｸ謇句虚縺ｧ雋ｼ繧贋ｻ倥￠繧九◆繧√・繝・く繧ｹ繝医ｒ菴懊ｋ縺縺代〒縺吶ら判蜒冗函謌植PI繧・・蜍慕判蜒冗函謌舌・霑ｽ蜉縺励※縺・∪縺帙ｓ縲・

## 逕ｻ蜒丈ｸ諡ｬ蜿悶ｊ霎ｼ縺ｿ

Phase5.2縺ｧ縺ｯ縲，hatGPT縺ｪ縺ｩ縺ｧ逕滓・縺励◆隍・焚逕ｻ蜒上ｒ縺ｾ縺ｨ繧√※蜿悶ｊ霎ｼ縺ｿ縲√・繝ｭ繧ｸ繧ｧ繧ｯ繝医・ `images` 繝輔か繝ｫ繝縺ｸ `001.png`, `002.png`, `003.png` 縺ｮ蠖｢蠑上〒閾ｪ蜍穂ｿ晏ｭ倥〒縺阪∪縺吶・

蜿悶ｊ霎ｼ縺ｿ譁ｹ豕・

- 邏譚千ｮ｡逅・ち繝悶・繝峨Λ繝・げ・・ラ繝ｭ繝・・鬆伜沺縺ｸ逕ｻ蜒上ｒ繝峨Ο繝・・
- 縲檎判蜒上ヵ繧｡繧､繝ｫ繧帝∈謚槭阪°繧芽､・焚逕ｻ蜒上ｒ驕ｸ謚・
- 繧ｨ繧ｯ繧ｹ繝励Ο繝ｼ繝ｩ繝ｼ縺ｧ逕ｻ蜒上ヵ繧｡繧､繝ｫ繧偵さ繝斐・縺励※縲√い繝励Μ荳翫〒 Ctrl+V
- 繧ｯ繝ｪ繝・・繝懊・繝牙・縺ｮ逕ｻ蜒上ョ繝ｼ繧ｿ繧・Ctrl+V 縺ｧ雋ｼ繧贋ｻ倥￠

蟇ｾ蠢懷ｽ｢蠑・

- `png`
- `jpg`
- `jpeg`
- `webp`

菫晏ｭ俶凾縺ｯ蠢・★PNG縺ｸ螟画鋤縺輔ｌ縲～projects/<project>/images/001.png` 縺九ｉ騾｣逡ｪ縺ｧ菫晏ｭ倥＆繧後∪縺吶よ里蟄倡判蜒上′縺ゅｋ蝣ｴ蜷医・縲√御ｸ頑嶌縺阪☆繧九阪瑚ｿｽ蜉縺吶ｋ縲阪後く繝｣繝ｳ繧ｻ繝ｫ縲阪ｒ驕ｸ縺ｹ縺ｾ縺吶・

蜿悶ｊ霎ｼ縺ｿ貂医∩逕ｻ蜒上・繧ｵ繝繝阪う繝ｫ荳隕ｧ縺ｧ遒ｺ隱阪〒縺阪∪縺吶ょ推逕ｻ蜒上↓縺ｯ繝輔ぃ繧､繝ｫ蜷阪∝炎髯､繝懊ち繝ｳ縲∽ｸ翫∈/荳九∈繝懊ち繝ｳ縺後≠繧翫・・分繧貞､峨∴繧九→閾ｪ蜍輔〒 `001.png` 縺九ｉ繝ｪ繝阪・繝縺礼峩縺励∪縺吶・

## ChatGPT JSON蜃ｺ蜉帛ｽ｢蠑・

ChatGPT縺ｫ縺ｯJSON縺縺代ｒ霑斐☆繧医≧謖・､ｺ縺励∪縺吶・

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

JSON莉･螟悶・隱ｬ譏取枚繧Мarkdown繧ｳ繝ｼ繝峨ヶ繝ｭ繝・け縺ｯ荳崎ｦ√〒縺吶・

## 謚慕ｨｿ繧ｿ繧ｰ

蛻ｶ菴懆ｨｭ螳壹・繧ｿ繧ｰ谺・・縲軽outube繧ｿ繧ｰ菫晏ｭ倥阪→縲荊iktok繧ｿ繧ｰ菫晏ｭ倥阪↓蛻・°繧後※縺・∪縺吶・

- youtube繧ｿ繧ｰ菫晏ｭ・ `hashtags.txt` 縺ｮ繧ｿ繧ｰ縺九ｉ `#` 繧貞炎髯､縺励√き繝ｳ繝槫玄蛻・ｊ縺ｧ閾ｪ蜍募・蜉帙＠縺ｾ縺吶・
- tiktok繧ｿ繧ｰ菫晏ｭ・ `hashtags.txt` 縺ｮ繧ｿ繧ｰ繧・`#` 莉倥″縺ｧ繧ｳ繝斐・縺励∵怙蠕後↓ `#VOICEVOX` 繧定ｿｽ蜉縺励※閾ｪ蜍募・蜉帙＠縺ｾ縺吶・
- 繝・・繝槭〆ouTube繧ｿ繧ｰ縲ゝikTok繧ｿ繧ｰ縺ｯ蜷・さ繝斐・繝懊ち繝ｳ縺九ｉ繝ｯ繝ｳ繧ｯ繝ｪ繝・け縺ｧ繧ｯ繝ｪ繝・・繝懊・繝峨∈繧ｳ繝斐・縺ｧ縺阪∪縺吶・

## 蛻ｶ菴懊Γ繝｢

荳諡ｬ繝阪ち邂｡逅・・荳九↓10蛟九・繝｡繝｢谺・′縺ゅｊ縺ｾ縺吶ゅｈ縺丈ｽｿ縺・兜遞ｿ譁・∵ｳｨ諢冗せ縲∝ｮ壼梛譁・↑縺ｩ繧剃ｿ晏ｭ倥＠縲∝推繝｡繝｢縺ｮ縲後さ繝斐・縲阪・繧ｿ繝ｳ縺ｧ繝ｯ繝ｳ繧ｯ繝ｪ繝・け繧ｳ繝斐・縺ｧ縺阪∪縺吶・

蟾ｦ蛛ｴ縺ｮ謫堺ｽ懊お繝ｪ繧｢縺ｯ繧ｹ繧ｯ繝ｭ繝ｼ繝ｫ縺ｧ縺阪ｋ縺溘ａ縲√Γ繝｢谺・′蠅励∴縺ｦ繧ら判髱｢縺九ｉ隕句・繧後↓縺上￥縺ｪ縺｣縺ｦ縺・∪縺吶・

## 陦ｨ遉ｺ繧ｨ繝ｪ繧｢縺ｮ鬮倥＆隱ｿ謨ｴ

蟾ｦ蛛ｴ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｨ荳諡ｬ繝阪ち邂｡逅・・髢薙・縲∝｢・岼繧偵ラ繝ｩ繝・げ縺励※邵ｦ蟷・ｒ隱ｿ謨ｴ縺ｧ縺阪∪縺吶らｴ譚千ｮ｡逅・・蜿悶ｊ霎ｼ縺ｿ貂医∩逕ｻ蜒上お繝ｪ繧｢縺ｯ縲√碁ｫ倥＆縲阪・謨ｰ蛟､繧貞､画峩縺励※邵ｦ蟷・ｒ隱ｿ謨ｴ縺ｧ縺阪∪縺吶・

## 繝ｭ繧ｰ

繝ｭ繧ｰ縺ｯ `logs/YYYY-MM-DD.log` 縺ｫ菫晏ｭ倥＆繧後∪縺吶・

險倬鹸蟇ｾ雎｡:

- 襍ｷ蜍・
- 邨ゆｺ・
- JSON隗｣譫・
- VOICEVOX
- FFmpeg
- 繧ｨ繝ｩ繝ｼ

繝ｭ繧ｰ繝ｬ繝吶Ν:

- INFO
- WARNING
- ERROR

## VOICEVOX

繝・ヵ繧ｩ繝ｫ繝・

- URL: `http://127.0.0.1:50021`
- speaker id: `3`

VOICEVOX繧定ｵｷ蜍輔＠縺ｦ縺九ｉ縲祁OICEVOX髻ｳ螢ｰ逕滓・縲阪ｒ謚ｼ縺吶→縲～audio/voice.wav` 繧剃ｽ懈・縺励∪縺吶・
`subtitles.txt` 縺悟ｭ伜惠縺吶ｋ蝣ｴ蜷医∝ｭ怜ｹ輔く繝･繝ｼ縺斐→縺ｫ髻ｳ螢ｰ繧貞句挨縺ｫ逕滓・繝ｻ邨仙粋縺励∝ｮ滄圀縺ｮ髻ｳ螢ｰ縺ｮ髟ｷ縺輔↓蜷医ｏ縺帙※蟄怜ｹ輔・繧ｿ繧､繝溘Φ繧ｰ・育ｧ呈焚・峨ｒ閾ｪ蜍慕噪縺ｫ陬懈ｭ｣繝ｻ蜷梧悄縺励∪縺吶ゅ％繧後↓繧医ｊ縲・浹螢ｰ縺ｨ蟄怜ｹ輔・繧ｺ繝ｬ縺檎匱逕溘＠縺ｾ縺帙ｓ縲・

## FFmpeg

遒ｺ隱・

```powershell
ffmpeg -version
```

蜍慕判逕滓・縺ｮ蜈･蜉・

- `images/001.png` 縺ｪ縺ｩ縺ｮ逕ｻ蜒・
- `audio/voice.wav`
- `assets/bgm` 蜀・・BGM・井ｻｻ諢擾ｼ・
- `subtitles.txt` 縺ｮ譎る俣莉倥″蟄怜ｹ包ｼ井ｻｻ諢擾ｼ・

蜃ｺ蜉・

- `video/final.mp4`

## BGM

`assets/bgm` 縺ｫ `mp3` 縺ｾ縺溘・ `wav` 繧貞・繧後ｋ縺縺代〒縲∝虚逕ｻ逕滓・譎ゅ↓閾ｪ蜍輔〒菴ｿ逕ｨ縺輔ｌ縺ｾ縺吶・

繝・ヵ繧ｩ繝ｫ繝・

- BGM繧剃ｽｿ逕ｨ縺吶ｋ: ON
- 繝翫Ξ繝ｼ繧ｷ繝ｧ繝ｳ髻ｳ驥・ 100%
- BGM髻ｳ驥・ 20%
- BGM縺ｮ髢句ｧ・ 邏・.5遘偵ヵ繧ｧ繝ｼ繝峨う繝ｳ
- BGM縺ｮ邨ゆｺ・ 蜍慕判邨ゆｺ・凾縺ｫBGM縺縺・遘偵ヵ繧ｧ繝ｼ繝峨い繧ｦ繝・

`assets/bgm` 縺ｫ隍・焚繝輔ぃ繧､繝ｫ縺後≠繧句ｴ蜷医・縲√ヵ繧｡繧､繝ｫ蜷埼・〒譛蛻昴・1譖ｲ繧剃ｽｿ逕ｨ縺励∪縺吶・GM縺悟虚逕ｻ繧医ｊ遏ｭ縺・ｴ蜷医・閾ｪ蜍輔〒繝ｫ繝ｼ繝励＠縲∝虚逕ｻ繧医ｊ髟ｷ縺・ｴ蜷医・蜍慕判縺ｮ邨ゆｺ・ｽ咲ｽｮ縺ｧ蛻・ｊ縺ｾ縺吶・

BGM縺檎┌縺・ｴ蜷医・縲∝ｾ捺擂騾壹ｊ繝翫Ξ繝ｼ繧ｷ繝ｧ繝ｳ縺ｮ縺ｿ縺ｧ蜍慕判繧堤函謌舌＠縺ｾ縺吶ゅお繝ｩ繝ｼ縺ｫ縺ｯ縺ｪ繧翫∪縺帙ｓ縲・

險ｭ螳夂判髱｢縺ｧ縺ｯ縲沓GM繧剃ｽｿ逕ｨ縺吶ｋ縲阪→縲沓GM髻ｳ驥上阪ｒ螟画峩縺ｧ縺阪∪縺吶ゅ沓GM繝輔か繝ｫ繝繧帝幕縺上阪°繧・`assets/bgm` 繧堤峩謗･髢九￠縺ｾ縺吶・

## 繧ｪ繝ｼ繝励ル繝ｳ繧ｰ繝ｻ繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ

`assets/intro` 縺ｫ `mp4` / `png` / `jpg` 繧貞・繧後ｋ縺ｨ縲∬ｨｭ螳夂判髱｢縺ｮ縲後が繝ｼ繝励ル繝ｳ繧ｰ繧剃ｽｿ逕ｨ縺吶ｋ縲阪′ON縺ｮ蝣ｴ蜷医↓蜍慕判縺ｮ蜈磯ｭ縺ｸ閾ｪ蜍戊ｿｽ蜉縺ｧ縺阪∪縺吶・

`assets/ending` 縺ｫ `mp4` / `png` / `jpg` 繧貞・繧後ｋ縺ｨ縲∬ｨｭ螳夂判髱｢縺ｮ縲後お繝ｳ繝・ぅ繝ｳ繧ｰ繧剃ｽｿ逕ｨ縺吶ｋ縲阪′ON縺ｮ蝣ｴ蜷医↓蜍慕判縺ｮ譛ｫ蟆ｾ縺ｸ閾ｪ蜍戊ｿｽ蜉縺ｧ縺阪∪縺吶・

繧､繝ｳ繝医Ο縺ｨ繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ縺ｯ縲√◎繧後◇繧瑚ｨｭ螳夂判髱｢縺ｧ谺｡縺ｮ鬆・岼繧定ｪｿ謨ｴ縺ｧ縺阪∪縺吶・

- 陦ｨ遉ｺ譎る俣: 1・・0遘抵ｼ育判蜒上・蜍慕判蜈ｱ騾壹ら洒縺・虚逕ｻ縺ｯ閾ｪ蜍輔Ν繝ｼ繝暦ｼ・
- 繧ｺ繝ｼ繝: `Static` / `Slow Zoom In` / `Slow Zoom Out`
- 髻ｳ螢ｰ: `Original` / `BGM` / `Original + BGM` / `Mute`
- BGM髻ｳ驥・ 0・・00%

`BGM` 繧帝∈縺ｶ蝣ｴ蜷医・縲・壼ｸｸ縺ｮBGM縺ｨ蜷後§縺・`assets/bgm` 縺ｮ蜈磯ｭ縺ｮ `mp3` 縺ｾ縺溘・ `wav` 縺御ｽｿ繧上ｌ縺ｾ縺吶らｴ譚宣浹螢ｰ縺後↑縺・判蜒上〒繧・GM繧剃ｻ倥￠繧峨ｌ縺ｾ縺吶・

隍・焚繝輔ぃ繧､繝ｫ縺後≠繧句ｴ蜷医・縲√ヵ繧｡繧､繝ｫ蜷埼・〒譛蛻昴・繝輔ぃ繧､繝ｫ繧剃ｽｿ逕ｨ縺励∪縺吶らｴ譚舌′辟｡縺・ｴ蜷医・縲∝ｾ捺擂騾壹ｊ譛ｬ邱ｨ縺ｮ縺ｿ縺ｧ蜍慕判繧堤函謌舌＠縺ｾ縺吶・

## 邱城寔邱ｨ菴懈・

荳企Κ縺ｮ縲檎ｷ城寔邱ｨ縲阪ち繝悶〒縺ｯ縲√ず繝｣繝ｳ繝ｫ縺斐→縺ｫ螳梧・貂医∩蜍慕判繧剃ｸ隕ｧ陦ｨ遉ｺ縺励∪縺吶ゆｽｿ縺・◆縺・虚逕ｻ縺ｫ繝√ぉ繝・け繧貞・繧後√御ｸ翫∈縲阪御ｸ九∈縲阪〒縺､縺ｪ縺宣・分繧呈ｱｺ繧√※縺九ｉ縲檎ｷ城寔邱ｨ繧剃ｽ懈・縲阪ｒ謚ｼ縺吶→縲：Fmpeg縺ｧ荳隕ｧ縺ｮ鬆・分騾壹ｊ縺ｫ邨仙粋縺励∪縺吶・

險ｭ螳壹〒繧ｪ繝ｼ繝励ル繝ｳ繧ｰ繝ｻ繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ縺薫N縺ｧ縲～assets/intro` / `assets/ending` 縺ｫ邏譚舌′縺ゅｋ蝣ｴ蜷医∫ｷ城寔邱ｨ縺ｫ繧り・蜍輔〒霑ｽ蜉縺輔ｌ縺ｾ縺吶・

蜃ｺ蜉帛・:

```text
exports/series/<series>_complete.mp4
exports/series/chapter.txt
```

`chapter.txt` 縺ｫ縺ｯ縲∝推蜍慕判縺ｮ髢句ｧ区凾蛻ｻ縺ｨ繧ｿ繧､繝医Ν繧剃ｿ晏ｭ倥＠縺ｾ縺吶ら樟譎らせ縺ｧ縺ｯ蜍慕判縺ｸ縺ｮ繝√Ε繝励ち繝ｼ蝓九ａ霎ｼ縺ｿ縺ｯ陦後＞縺ｾ縺帙ｓ縲・

## Cinematic Motion Engine

Phase6.5縺ｧ縺ｯ縲・撕豁｢逕ｻ縺九ｉ菴懊ｋ蜍慕判縺ｫFFmpeg縺縺代〒譏逕ｻ鬚ｨ繝ｻ繝峨く繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ鬚ｨ縺ｮ蜍輔″繧剃ｻ倥￠繧峨ｌ繧九ｈ縺・↓縺励∪縺励◆縲０penAI API縲∫判蜒冗函謌植PI縲∝虚逕ｻ逕滓・AI縺ｯ菴ｿ逕ｨ縺励∪縺帙ｓ縲・

險ｭ螳夂判髱｢縺ｧ螟画峩縺ｧ縺阪ｋ鬆・岼:

- Motion Style: `Static`, `Slow Zoom In`, `Slow Zoom Out`, `Pan Left`, `Pan Right`, `Pan Up`, `Pan Down`, `Ken Burns`, `Random Motion`
- 繧ｺ繝ｼ繝騾溷ｺｦ: `Slow`, `Normal`, `Fast`
- 繝医Λ繝ｳ繧ｸ繧ｷ繝ｧ繝ｳ: `Fade`, `Cross Fade`, `Zoom Fade`, `Slide`, `None`
- 螳・ｮ吶が繝ｼ繝舌・繝ｬ繧､騾乗・蠎ｦ: 10縲・0%
- Light Effect: `OFF`, `Lens Flare`, `Glow`, `Soft Light`

Light Effect縺ｯMotion繝ｻOverlay縺ｮ蠕後∝ｭ怜ｹ輔・繧ｿ繧､繝医Ν縺ｮ蜑阪↓驕ｩ逕ｨ縺輔ｌ縺ｾ縺吶・ight Effect縺ｧFFmpeg繧ｨ繝ｩ繝ｼ縺ｫ縺ｪ繧句ｴ蜷医・縲∵怙譁ｰ迚医〒縺ゅｋ縺薙→繧堤｢ｺ隱阪＠縺ｦ縺九ｉ蜀咲函謌舌＠縺ｦ縺上□縺輔＞縲・

`Random Motion` 縺ｧ縺ｯ縲∫判蜒上＃縺ｨ縺ｫ逡ｰ縺ｪ繧区ｼ泌・繧定・蜍輔〒蜑ｲ繧雁ｽ薙※縺ｾ縺吶ょ酔縺俶ｼ泌・縺碁｣邯壹＠縺ｪ縺・ｈ縺・↓縺励～image_prompts.txt` 縺ｫ繝悶Λ繝・け繝帙・繝ｫ縲・橿豐ｳ縲∝ｮ・ｮ呵飴縺ｪ縺ｩ縺ｮ隱槭′縺ゅｋ蝣ｴ蜷医・繧ｷ繝ｼ繝ｳ蜀・ｮｹ縺ｫ蜷医≧蜍輔″繧貞━蜈医＠縺ｾ縺吶・

Overlay縺ｮ菴ｿ縺・婿:

1. `assets/overlay` 縺ｫ `mp4`, `png`, `jpg`, `jpeg`, `webp` 繧貞・繧後∪縺吶・
2. 險ｭ螳夂判髱｢縺ｧ騾乗・蠎ｦ繧定ｪｿ謨ｴ縺励∪縺吶・
3. 蜍慕判逕滓・譎ゅ↓譛ｬ邱ｨ縺ｸ閾ｪ蜍輔〒驥阪・縺ｾ縺吶・

邏譚千ｮ｡逅・・蜿悶ｊ霎ｼ縺ｿ貂医∩逕ｻ蜒丈ｸ隕ｧ縺ｫ縺ｯ縲～001.png / Zoom In` 縺ｮ繧医≧縺ｫ逕ｻ蜒上＃縺ｨ縺ｮMotion蜷阪′陦ｨ遉ｺ縺輔ｌ縺ｾ縺吶・

蜍慕判逕滓・縺ｮ蜃ｦ逅・・・縲｀otion縲∝ｭ怜ｹ・繧ｿ繧､繝医Ν縲。GM縲∝ｮ梧・蜍慕判縺ｧ縺吶・

## Analytics

Phase7縺ｧ縺ｯ縲∽ｸ企Κ縺ｫ縲窟nalytics縲阪ち繝悶ｒ霑ｽ蜉縺励∪縺励◆縲・ouTube Studio / TikTok Studio 縺九ｉ繧ｨ繧ｯ繧ｹ繝昴・繝医＠縺櫃SV繧定ｪｭ縺ｿ霎ｼ繧縺縺代〒縲√メ繝｣繝ｳ繝阪Ν驕句霧逕ｨ縺ｮ蛻・梵繧堤｢ｺ隱阪〒縺阪∪縺吶・ouTube API繧УikTok API縺ｯ菴ｿ逕ｨ縺励∪縺帙ｓ縲・

菴ｿ縺・婿:

1. 縲窟nalytics縲阪ち繝悶ｒ髢九″縺ｾ縺吶・
2. 縲靴SV繧定ｪｭ縺ｿ霎ｼ繧縲阪ｒ謚ｼ縺励〆ouTube Studio 縺ｾ縺溘・ TikTok Studio 縺ｮCSV繧帝∈謚槭＠縺ｾ縺吶り､・焚CSV繧偵∪縺ｨ繧√※驕ｸ謚槭〒縺阪∪縺吶・3. 繝輔か繝ｫ繝蜀・・CSV繧偵∪縺ｨ繧√※蜿悶ｊ霎ｼ繧蝣ｴ蜷医・縲靴SV繝輔か繝ｫ繝繧定ｪｭ縺ｿ霎ｼ繧縲阪ｒ謚ｼ縺励∪縺吶・4. 髮・ｨ医√Λ繝ｳ繧ｭ繝ｳ繧ｰ縲√ず繝｣繝ｳ繝ｫ蛻・梵縲√ち繧､繝医Ν蛻・梵縲∝虚逕ｻ荳隕ｧ縲￣roject Analytics縲∝・譫舌さ繝｡繝ｳ繝医ｒ遒ｺ隱阪＠縺ｾ縺吶・5. 蠢・ｦ√↓蠢懊§縺ｦ繧ｿ繧､繝医Ν縲√ず繝｣繝ｳ繝ｫ縲∝・逕滓焚莉･荳翫∵兜遞ｿ譌･縲∬ｩ穂ｾ｡縺ｧ讀懃ｴ｢縺励∪縺吶・6. 縲悟・譫千ｵ先棡CSV菫晏ｭ倥阪〒謨ｴ蠖｢貂医∩縺ｮ蛻・梵邨先棡繧辰SV縺ｨ縺励※菫晏ｭ倥〒縺阪∪縺吶・
陦ｨ遉ｺ縺ｧ縺阪ｋ髮・ｨ・

- 邱丞虚逕ｻ謨ｰ
- 邱丞・逕滓焚
- 蟷ｳ蝮・・逕滓焚
- 譛鬮伜・逕滓焚 / 譛菴主・逕滓焚
- 邱上＞縺・・
- 邱上さ繝｡繝ｳ繝・
- 蟷ｳ蝮・＞縺・・邇・
- 蟷ｳ蝮・さ繝｡繝ｳ繝育紫

繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ:

- 蜀咲函謨ｰ TOP10
- 縺・＞縺ｭ TOP10
- 繧ｳ繝｡繝ｳ繝・TOP10
- 縺・＞縺ｭ邇・TOP10
- 繧ｳ繝｡繝ｳ繝育紫 TOP10

蛻・梵逕ｻ髱｢:

- 繧ｸ繝｣繝ｳ繝ｫ蛻･縺ｮ蜍慕判謨ｰ縲∝ｹｳ蝮・・逕滓焚縲∝ｹｳ蝮・＞縺・・
- 繧ｿ繧､繝医Ν鬆ｻ蜃ｺ繝ｯ繝ｼ繝・
- 縲後懊→縺ｯ・溘阪後懊〒縺阪ｋ・溘阪後懊↑縺懶ｼ溘阪卦OP蠖｢蠑上阪後Λ繝ｳ繧ｭ繝ｳ繧ｰ縲阪娯雷笳九☆繧九→・溘阪↑縺ｩ縺ｮ繧ｿ繧､繝医Ν繝代ち繝ｼ繝ｳ蛻・梵
- 蟷ｳ蝮・・逕滓焚縺ｨ蟷ｳ蝮・＞縺・・邇・ｒ蜈・↓縺励◆5谿ｵ髫手ｩ穂ｾ｡
- AI Video Factory繧ｳ繝｡繝ｳ繝・

繧ｰ繝ｩ繝・

- 蜀咲函謨ｰ謗ｨ遘ｻ
- 謚慕ｨｿ譛ｬ謨ｰ謗ｨ遘ｻ
- 繧ｸ繝｣繝ｳ繝ｫ蜑ｲ蜷・
- 蜀咲函謨ｰTOP10

繧ｰ繝ｩ繝慕函謌舌↓縺ｯ `matplotlib` 繧剃ｽｿ逕ｨ縺励∪縺吶ゆｾ晏ｭ倬未菫ゅ・ `requirements.txt` 縺ｫ霑ｽ蜉貂医∩縺ｧ縺吶・
## 繧ｫ繝・ざ繝ｪ繝ｻ髫主ｱ､繝輔ぅ繝ｫ繧ｿ繝ｼ

Phase7.4縺ｧ縺ｯ縲√・繝ｭ繧ｸ繧ｧ繧ｯ繝域焚縺悟｢励∴縺ｦ繧よ紛逅・＠繧・☆縺・ｈ縺・↓縲～繧ｸ繝｣繝ｳ繝ｫ > 繧ｫ繝・ざ繝ｪ > 繧ｷ繝ｪ繝ｼ繧ｺ` 縺ｮ髫主ｱ､繧定ｿｽ蜉縺励∪縺励◆縲・
菴ｿ縺・・縺・

- 繧ｸ繝｣繝ｳ繝ｫ: 螟ｧ蛻・｡槭〒縺吶ゆｾ・ 螳・ｮ吶∵ｪ縲、I繝九Η繝ｼ繧ｹ
- 繧ｫ繝・ざ繝ｪ: 繧ｸ繝｣繝ｳ繝ｫ蜀・・蟆丞・鬘槭〒縺吶ゆｾ・ 螳・ｮ・> 繝悶Λ繝・け繝帙・繝ｫ縲∝ｮ・ｮ・> 諱呈弌
- 繧ｷ繝ｪ繝ｼ繧ｺ: 騾｣邯壽兜遞ｿ縺ｮ縺ｾ縺ｨ縺ｾ繧翫〒縺吶ゆｾ・ 繝悶Λ繝・け繝帙・繝ｫ蝓ｺ遉・#003

繧ｫ繝・ざ繝ｪ邂｡逅・

1. 蟾ｦ蛛ｴ縺ｮ縲御ｸ諡ｬ繝阪ち邂｡逅・榊・縺ｫ縺ゅｋ縲後き繝・ざ繝ｪ邂｡逅・阪ｒ髢九″縺ｾ縺吶・2. 邂｡逅・☆繧九ず繝｣繝ｳ繝ｫ繧帝∈縺ｳ縺ｾ縺吶・3. 縲瑚ｿｽ蜉縲阪檎ｷｨ髮・阪悟炎髯､縲阪〒繧ｫ繝・ざ繝ｪ繧堤ｮ｡逅・＠縺ｾ縺吶・4. 縲御ｸ翫∈縲阪御ｸ九∈縲阪〒荳ｦ縺ｳ譖ｿ縺医〒縺阪∪縺吶・
繧ｫ繝・ざ繝ｪ蜑企勁譎ゅ√◎縺ｮ繧ｫ繝・ざ繝ｪ繧剃ｽｿ逕ｨ荳ｭ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝医′縺ゅｋ蝣ｴ蜷医・隴ｦ蜻翫＠縺ｾ縺吶よ里蟄倥・繝ｭ繧ｸ繧ｧ繧ｯ繝医・繧ｫ繝・ざ繝ｪ縺ｯ蜍晄焔縺ｫ蜑企勁繝ｻ螟画峩縺励∪縺帙ｓ縲・
繝励Ο繧ｸ繧ｧ繧ｯ繝医∈縺ｮ繧ｫ繝・ざ繝ｪ險ｭ螳・

- 蛻ｶ菴懆ｨｭ螳壹〒繧ｸ繝｣繝ｳ繝ｫ繧帝∈縺ｶ縺ｨ縲√◎縺ｮ繧ｸ繝｣繝ｳ繝ｫ縺ｮ繧ｫ繝・ざ繝ｪ蛟呵｣懊□縺代′陦ｨ遉ｺ縺輔ｌ縺ｾ縺吶・- 繧ｫ繝・ざ繝ｪ谺・・閾ｪ逕ｱ蜈･蜉帙〒縺阪∪縺吶・- 閾ｪ逕ｱ蜈･蜉帙＠縺溘き繝・ざ繝ｪ縺ｯ遒ｺ隱榊ｾ後↓繧ｫ繝・ざ繝ｪ荳隕ｧ縺ｸ霑ｽ蜉縺ｧ縺阪∪縺吶・- 荳諡ｬ繝阪ち邂｡逅・・縲御ｸ諡ｬ菴懈・繧ｫ繝・ざ繝ｪ縲阪御ｸ諡ｬ菴懈・繧ｷ繝ｪ繝ｼ繧ｺ縲阪°繧峨∬､・焚繝励Ο繧ｸ繧ｧ繧ｯ繝医∈蜷後§繧ｫ繝・ざ繝ｪ繧貞渚譏縺ｧ縺阪∪縺吶・
邨槭ｊ霎ｼ縺ｿ:

- 蟾ｦ蛛ｴ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｧ縲√ず繝｣繝ｳ繝ｫ縲√き繝・ざ繝ｪ縲√す繝ｪ繝ｼ繧ｺ縲√ち繧ｰ縲∵兜遞ｿ迥ｶ諷九∝宛菴懃憾諷九∬ｩ穂ｾ｡縲∝・逕滓焚繧堤ｵ・∩蜷医ｏ縺帙※讀懃ｴ｢縺ｧ縺阪∪縺吶・- 縲梧悴蛻・｡槭阪ｒ驕ｸ縺ｶ縺ｨ縲√き繝・ざ繝ｪ譛ｪ險ｭ螳壹・譌｢蟄倥・繝ｭ繧ｸ繧ｧ繧ｯ繝医□縺代ｒ陦ｨ遉ｺ縺ｧ縺阪∪縺吶・- 縲檎ｵ槭ｊ霎ｼ縺ｿ隗｣髯､縲阪〒譚｡莉ｶ繧・繧ｯ繝ｪ繝・け縺ｧ蛻晄悄蛹悶〒縺阪∪縺吶・- 陦ｨ遉ｺ莉ｶ謨ｰ縺ｯ `陦ｨ遉ｺ荳ｭ: 24莉ｶ / 蜈ｨ186莉ｶ` 縺ｮ蠖｢蠑上〒遒ｺ隱阪〒縺阪∪縺吶・
荳諡ｬ繧ｫ繝・ざ繝ｪ螟画峩:

1. 繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｧ隍・焚繝励Ο繧ｸ繧ｧ繧ｯ繝医ｒ驕ｸ謚槭＠縺ｾ縺吶・2. 繧ｫ繝・ざ繝ｪ邂｡逅・〒蜿肴丐縺励◆縺・ず繝｣繝ｳ繝ｫ繝ｻ繧ｫ繝・ざ繝ｪ繧帝∈縺ｳ縺ｾ縺吶・3. 縲碁∈謚槭・繝ｭ繧ｸ繧ｧ繧ｯ繝医∈荳諡ｬ蜿肴丐縲阪ｒ謚ｼ縺励∪縺吶・4. 蠢・ｦ√↓蠢懊§縺ｦ繧ｷ繝ｪ繝ｼ繧ｺ蜷阪∬ｿｽ蜉繧ｿ繧ｰ縲∝炎髯､繧ｿ繧ｰ繧貞・蜉帙＠縺ｾ縺吶・
繧ｫ繝・ざ繝ｪ蛻･Analytics:

- Analytics縺ｮ縲後ず繝｣繝ｳ繝ｫ蛻・梵縲阪↓繧ｫ繝・ざ繝ｪ蛻･髮・ｨ医′陦ｨ遉ｺ縺輔ｌ縺ｾ縺吶・- 繧ｫ繝・ざ繝ｪ蛻･縺ｮ蜍慕判譛ｬ謨ｰ縲∫ｷ丞・逕滓焚縲∝ｹｳ蝮・・逕滓焚縲∝ｹｳ蝮・＞縺・・邇・∝ｹｳ蝮・ｦ冶・邇・・谿ｵ髫手ｩ穂ｾ｡繧堤｢ｺ隱阪〒縺阪∪縺吶・- AI繧｢繝峨ヰ繧､繧ｶ繝ｼ縺ｮ縺翫☆縺吶ａ繝・・繝槭↓繧ゅ∝･ｽ隱ｿ繧ｫ繝・ざ繝ｪ縺悟渚譏縺輔ｌ縺ｾ縺吶・
## Project Analytics / 蛟句挨蜍慕判蛻・梵

Phase7.2縲弃hase7.3縺ｧ縺ｯ縲、nalytics縺ｧ隱ｭ縺ｿ霎ｼ繧薙□CSV繝・・繧ｿ繧・`projects` 蜀・・蜷・虚逕ｻ繝励Ο繧ｸ繧ｧ繧ｯ繝医∈閾ｪ蜍輔〒邏蝉ｻ倥￠縲∝句挨謌千ｸｾ縺ｨ謾ｹ蝟・｡医ｒ遒ｺ隱阪〒縺阪∪縺吶・
YouTube Studio CSV:

- `陦ｨ繝・・繧ｿ.csv`: 蜍慕判縺斐→縺ｮ謌千ｸｾ縺ｨ縺励※蛻ｩ逕ｨ縺励∪縺吶・- `繧ｰ繝ｩ繝輔ョ繝ｼ繧ｿ.csv`: 譌･蛻･謗ｨ遘ｻ繧ｰ繝ｩ繝輔→縺励※蛻ｩ逕ｨ縺励∪縺吶・- `蜷郁ｨ・csv`: 繝√Ε繝ｳ繝阪Ν蜈ｨ菴薙・蜷郁ｨ亥､縺ｨ縺励※蛻ｩ逕ｨ縺励∪縺吶・
繝輔ぃ繧､繝ｫ蜷阪□縺代〒縺ｯ縺ｪ縺丞・蜷阪°繧臥ｨｮ鬘槭ｒ蛻､螳壹☆繧九◆繧√∬恭隱槫錐繧・Μ繝阪・繝貂医∩CSV縺ｧ繧ょ茜逕ｨ縺ｧ縺阪ｋ遽・峇縺ｧ隱ｭ縺ｿ霎ｼ縺ｿ縺ｾ縺吶ゆｸ驛ｨ繝輔ぃ繧､繝ｫ縺励°縺ｪ縺・ｴ蜷医ｂ繧ｨ繝ｩ繝ｼ縺ｫ縺ｯ縺帙★縲∝叙蠕励〒縺阪◆蛻励□縺代ｒ菴ｿ縺・∪縺吶・
TikTok Studio CSV:

- 繧ｿ繧､繝医Ν縲∬ｦ冶・蝗樊焚縲√＞縺・・縲√さ繝｡繝ｳ繝医√す繧ｧ繧｢縲∽ｿ晏ｭ倥∝ｹｳ蝮・ｦ冶・譎る俣縲∝ｮ瑚ｦ冶・邇・√ヵ繧ｩ繝ｭ繝ｯ繝ｼ蠅玲ｸ帙↑縺ｩ縲，SV縺ｫ蟄伜惠縺吶ｋ蛻励□縺代ｒ蛻ｩ逕ｨ縺励∪縺吶・
繝励Ο繧ｸ繧ｧ繧ｯ繝郁・蜍慕ｴ蝉ｻ倥￠:

- `title.txt`
- `topic.txt`
- `project.json` 縺ｮ繧ｿ繧､繝医Ν / 繝・・繝・- 蜍慕判繝輔ぃ繧､繝ｫ蜷・- 繝励Ο繧ｸ繧ｧ繧ｯ繝医ヵ繧ｩ繝ｫ繝蜷・
荳願ｨ倥→CSV繧ｿ繧､繝医Ν繧呈ｯ碑ｼ・＠縲∝ｮ悟・荳閾ｴ縲∵ｭ｣隕丞喧荳閾ｴ縲・Κ蛻・ｸ閾ｴ縲・｡樔ｼｼ蠎ｦ荳閾ｴ縺ｮ鬆・↓邏蝉ｻ倥￠縺ｾ縺吶よｭ｣隕丞喧縺ｧ縺ｯ縲∫ｩｺ逋ｽ縲∝・隗貞濠隗偵∝､ｧ蟆乗枚蟄励∬ｨ伜捷縲√ワ繝・す繝･繧ｿ繧ｰ縲∫ｵｵ譁・ｭ励～#Shorts`縲∵忰蟆ｾ逡ｪ蜿ｷ縺ｪ縺ｩ繧定・・縺励∪縺吶・
謇句虚邏蝉ｻ倥￠:

1. Analytics繧ｿ繝悶〒CSV繧定ｪｭ縺ｿ霎ｼ縺ｿ縺ｾ縺吶・2. 縲梧悴邏蝉ｻ倥￠邂｡逅・阪ち繝悶ｒ髢九″縺ｾ縺吶・3. 譛ｪ邏蝉ｻ倥￠蜍慕判繧帝∈縺ｳ縲∫ｴ蝉ｻ倥￠蜈医・繝ｭ繧ｸ繧ｧ繧ｯ繝医ｒ驕ｸ謚槭＠縺ｾ縺吶・4. 縲檎ｴ蝉ｻ倥￠菫晏ｭ倥阪ｒ謚ｼ縺励∪縺吶・
謇句虚邏蝉ｻ倥￠縺ｯ `analytics_links.json` 縺ｫ菫晏ｭ倥＆繧後∵ｬ｡蝗曚SV隱ｭ縺ｿ霎ｼ縺ｿ蠕後ｂ邯ｭ謖√＆繧後∪縺吶・SV縺ｨ邏蝉ｻ倥＞縺溘・繝ｭ繧ｸ繧ｧ繧ｯ繝医↓縺ｯ `project.json` 縺ｮ `analytics` 縺ｨ `posting_status` 縺御ｿ晏ｭ倥＆繧後∪縺吶よ里蟄倥・ `posted.txt` 縺ｯ蜑企勁繝ｻ荳頑嶌縺阪＠縺ｾ縺帙ｓ縲・
蛟句挨蜍慕判蛻・梵:

- 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨・縲悟句挨蛻・梵縲阪ち繝悶〒縲∫樟蝨ｨ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝医・YouTube / TikTok謌千ｸｾ繧堤｢ｺ隱阪〒縺阪∪縺吶・- URL縺靴SV縺ｫ蜷ｫ縺ｾ繧後ｋ蝣ｴ蜷医√刑ouTube URL繧帝幕縺上阪卦ikTok URL繧帝幕縺上阪・繧ｿ繝ｳ縺九ｉ繝悶Λ繧ｦ繧ｶ縺ｧ髢九￠縺ｾ縺吶・- 繝・・繧ｿ縺後↑縺・・岼縺ｯ縲梧悴蜿門ｾ励阪→陦ｨ遉ｺ縺輔ｌ縺ｾ縺吶・- 5谿ｵ髫手ｩ穂ｾ｡縲∽ｼｸ縺ｳ縺溽炊逕ｱ縲∵ｬ｡蝗樊隼蝟・｡医∫ｶ夂ｷｨ蛟呵｣懊〆ouTube / TikTok讓ｪ譁ｭ豈碑ｼ・ｒ繝ｫ繝ｼ繝ｫ繝吶・繧ｹ縺ｧ陦ｨ遉ｺ縺励∪縺吶・
隧穂ｾ｡縺ｮ隕区婿:

- 笘・・笘・・笘・ 髱槫ｸｸ縺ｫ螂ｽ隱ｿ
- 笘・・笘・・笘・ 螂ｽ隱ｿ
- 笘・・笘・・笘・ 蟷ｳ蝮・噪
- 笘・・笘・・笘・ 謾ｹ蝟・ｽ吝慍縺ゅｊ
- 笘・・笘・・笘・ 隕∵隼蝟・
謾ｹ蝟・署譯医・縲∝・逕滓焚縲√＞縺・・邇・√さ繝｡繝ｳ繝育紫縲，TR縲∝ｹｳ蝮・ｦ冶・邇・∝ｮ瑚ｦ冶・邇・∫匳骭ｲ閠・繝輔か繝ｭ繝ｯ繝ｼ蠅玲ｸ帙↑縺ｩ縲∝叙蠕励〒縺阪ｋ謖・ｨ吶□縺代ｒ菴ｿ縺・∪縺吶よ欠讓吶′荳崎ｶｳ縺励※縺・ｋ蝣ｴ蜷医・縲悟・譫舌ョ繝ｼ繧ｿ荳崎ｶｳ縲阪→陦ｨ遉ｺ縺励∪縺吶・
CSV譁・ｭ励さ繝ｼ繝峨→蠖｢蠑・

- UTF-8 / UTF-8 BOM / CP932 / Shift-JIS 縺ｫ蟇ｾ蠢懊＠縺ｾ縺吶・- 繧ｫ繝ｳ繝槫玄蛻・ｊ縲∵焚蛟､蜀・・繧ｫ繝ｳ繝槭√ヱ繝ｼ繧ｻ繝ｳ繝郁｡ｨ險倥∫ｩｺ谺・∵律譛ｬ隱・闍ｱ隱槫・蜷阪↓蟇ｾ蠢懊＠縺ｾ縺吶・
繧医￥縺ゅｋ繧ｨ繝ｩ繝ｼ:

- `CSV縺ｫ繧ｿ繧､繝医Ν縺ｾ縺溘・蜀咲函謨ｰ縺ｮ蛻励′縺ゅｊ縺ｾ縺帙ｓ縲Ａ: 陦ｨ繝・・繧ｿ縺ｧ縺ｯ縺ｪ縺ГSV縲√∪縺溘・蛻怜錐縺梧悴蟇ｾ蠢懊〒縺吶り｡ｨ繝・・繧ｿCSV繧ゆｸ邱偵↓驕ｸ謚槭＠縺ｦ縺上□縺輔＞縲・- `CSV縺ｮ譁・ｭ励さ繝ｼ繝峨ｒ蛻､螳壹〒縺阪∪縺帙ｓ縺ｧ縺励◆縲Ａ: CSV繧脱xcel縺ｧ髢九″縲ゞTF-8 CSV縺ｨ縺励※菫晏ｭ倥＠逶ｴ縺励※縺上□縺輔＞縲・- 蛟句挨蛻・梵縺後梧悴蜿門ｾ励阪・縺ｾ縺ｾ: 繧ｿ繧､繝医Ν縺後・繝ｭ繧ｸ繧ｧ繧ｯ繝医→荳閾ｴ縺励※縺・∪縺帙ｓ縲ゅ梧悴邏蝉ｻ倥￠邂｡逅・阪°繧画焔蜍輔〒邏蝉ｻ倥￠縺ｦ縺上□縺輔＞縲・
## AI繧｢繝峨ヰ繧､繧ｶ繝ｼ

Phase7.1縺ｧ縺ｯ縲、nalytics縺ｮ讓ｪ縺ｫ縲窟I繧｢繝峨ヰ繧､繧ｶ繝ｼ縲阪ち繝悶ｒ霑ｽ蜉縺励∪縺励◆縲・nalytics縺ｧ隱ｭ縺ｿ霎ｼ繧薙□CSV謌千ｸｾ縲√・繝ｭ繧ｸ繧ｧ繧ｯ繝域ュ蝣ｱ縲～topics.json` 縺ｮ繝阪ち蝨ｨ蠎ｫ繧貞・縺ｫ縲∵ｬ｡縺ｫ菴懊ｋ縺ｹ縺榊虚逕ｻ繧偵Ν繝ｼ繝ｫ繝吶・繧ｹ縺ｧ謠先｡医＠縺ｾ縺吶０penAI API縲；emini API縲，laude API縺ｪ縺ｩ縺ｮ螟夜ΚAI API縺ｯ菴ｿ逕ｨ縺励∪縺帙ｓ縲・

陦ｨ遉ｺ蜀・ｮｹ:

- 莉頑律縺ｮ蛻・梵
- 閾ｪ蜍輔さ繝｡繝ｳ繝・
- 縺翫☆縺吶ａ繝・・繝・
- 縺翫☆縺吶ａ繧ｿ繧､繝医Ν
- 谺｡縺ｮ莨∫判
- 謾ｹ蝟・・繧､繝ｳ繝・
- 蛻ｶ菴懃岼讓・
- 螳溽ｸｾ繝舌ャ繧ｸ
- 繝阪ち蝨ｨ蠎ｫ
- 豈取律縺ｮ荳險

菴ｿ縺・婿:

1. 縲窟nalytics縲阪ち繝悶〒CSV繧定ｪｭ縺ｿ霎ｼ縺ｿ縺ｾ縺吶・
2. 縲窟I繧｢繝峨ヰ繧､繧ｶ繝ｼ縲阪ち繝悶ｒ髢九″縺ｾ縺吶・
3. 蟷ｳ蝮・・逕滓焚縲∵怙鬮伜・逕溘∝ｹｳ蝮・＞縺・・邇・∵兜遞ｿ譛ｬ謨ｰ繧堤｢ｺ隱阪＠縺ｾ縺吶・
4. 縺翫☆縺吶ａ繝・・繝槭→縺翫☆縺吶ａ繧ｿ繧､繝医Ν繧貞盾閠・↓縲∵ｬ｡縺ｮ蛻ｶ菴懊ユ繝ｼ繝槭ｒ豎ｺ繧√∪縺吶・
5. 縲梧署譯医ｒ譖ｴ譁ｰ縲阪ｒ謚ｼ縺吶→縲∫樟蝨ｨ縺ｮAnalytics邨先棡縲√・繝ｭ繧ｸ繧ｧ繧ｯ繝医√ロ繧ｿ蝨ｨ蠎ｫ縺九ｉ蜀崎ｨ育ｮ励＠縺ｾ縺吶・

CSV譛ｪ隱ｭ縺ｮ蝣ｴ蜷医〒繧ゅ√・繝ｭ繧ｸ繧ｧ繧ｯ繝医→ `topics.json` 縺九ｉ繝阪ち蝨ｨ蠎ｫ縲∝宛菴懃岼讓吶∵ｯ取律縺ｮ荳險縺ｯ陦ｨ遉ｺ縺輔ｌ縺ｾ縺吶・SV繧定ｪｭ縺ｿ霎ｼ繧縺ｨ縲√ユ繝ｼ繝樊署譯医√ち繧､繝医Ν謠先｡医∵隼蝟・・繧､繝ｳ繝医√ヰ繝・ず縺ｮ邊ｾ蠎ｦ縺御ｸ翫′繧翫∪縺吶・

## 蟄怜ｹ慕┥縺崎ｾｼ縺ｿ

ChatGPT JSON縺ｮ `subtitles` 縺ｫ譎る俣莉倥″蟄怜ｹ輔′蜷ｫ縺ｾ繧後※縺・ｋ蝣ｴ蜷医∝虚逕ｻ逕滓・譎ゅ↓ `video/subtitles.ass` 繧剃ｽ懈・縺励：Fmpeg縺ｧ `video/final.mp4` 縺ｫ辟ｼ縺崎ｾｼ縺ｿ縺ｾ縺吶・

蟄怜ｹ募ｽ｢蠑・

```json
"subtitles": [
  {
    "start": 0.0,
    "end": 2.8,
    "text": "繝悶Λ繝・け繝帙・繝ｫ縺ｯ螳・ｮ吶〒譛繧りｬ弱・螟ｩ菴薙〒縺・
  }
]
```

繝ｫ繝ｼ繝ｫ:

- `start` 縺ｨ `end` 縺ｯ遘呈焚縺ｮ謨ｰ蛟､
- 1蟄怜ｹ輔・1縲・陦檎ｨ句ｺｦ
- 1蟄怜ｹ輔・陦ｨ遉ｺ譎る俣縺ｯ邏・縲・遘・
- 繧ｹ繝槭・邵ｦ蜍慕判縺ｧ隱ｭ縺ｿ繧・☆縺・洒縺・枚遶
- JSON莉･螟悶・隱ｬ譏取枚繧Мarkdown繧ｳ繝ｼ繝峨ヶ繝ｭ繝・け縺ｯ荳崎ｦ・

蟄怜ｹ戊ｨｭ螳・

- 蟄怜ｹ輔ｒ菴ｿ逕ｨ縺吶ｋ: ON/OFF
- 蟄怜ｹ輔ヵ繧ｩ繝ｳ繝医し繧､繧ｺ: 繝・ヵ繧ｩ繝ｫ繝・4
- 蟄怜ｹ穂ｽ咲ｽｮ: 荳・/ 荳ｭ螟ｮ / 荳・
- `荳義 縺ｯTikTok / YouTube Shorts縺ｮ隧ｳ邏ｰ陦ｨ遉ｺ縺ｫ驥阪↑繧翫↓縺上＞繧医≧縲∫判髱｢荳ｭ螟ｮ縺ｮ蟆代＠荳九↓陦ｨ遉ｺ縺輔ｌ縺ｾ縺吶・
- 蟄怜ｹ輔い繧ｦ繝医Λ繧､繝ｳ螟ｪ縺・ 繝・ヵ繧ｩ繝ｫ繝・
- 蟄怜ｹ募ｽｱ: ON/OFF

蟄怜ｹ輔′辟｡縺・ｴ蜷医・縲∝ｾ捺擂騾壹ｊ蟄怜ｹ輔↑縺励〒蜍慕判繧堤函謌舌＠縺ｾ縺吶ょ｣翫ｌ縺溷ｭ怜ｹ輔ョ繝ｼ繧ｿ縺後≠繧句ｴ蜷医・縲∵律譛ｬ隱槭・繧ｨ繝ｩ繝ｼ繝｡繝・そ繝ｼ繧ｸ繧定｡ｨ遉ｺ縺励※蜍慕判逕滓・繧呈ｭ｢繧√∪縺吶・

## 繧ｿ繧､繝医Ν陦ｨ遉ｺ

蜍慕判繝励Ο繧ｸ繧ｧ繧ｯ繝医・ `title.txt` 縺ｫ繧ｿ繧､繝医Ν縺悟・蜉帙＆繧後※縺・ｋ蝣ｴ蜷医∝虚逕ｻ縺ｮ荳企Κ縺ｪ縺ｩ縺ｫ繧ｿ繧､繝医Ν繧堤┥縺崎ｾｼ繧薙〒蟶ｸ譎ゅ∪縺溘・荳螳壽凾髢楢｡ｨ遉ｺ縺ｧ縺阪∪縺吶・

繧ｿ繧､繝医Ν險ｭ螳・

- 繧ｿ繧､繝医Ν繧定｡ｨ遉ｺ: ON/OFF
- 繧ｿ繧､繝医Ν繧ｵ繧､繧ｺ: 繝・ヵ繧ｩ繝ｫ繝・2
- 繧ｿ繧､繝医Ν菴咲ｽｮ: 荳・/ 荳奇ｼ亥ｷｦ蟇・○・・ 荳ｭ螟ｮ / 荳・
- 蜊企乗・閭梧勹: ON/OFF (蜊企乗・濶ｲ縺ｮ閭梧勹繝懊ャ繧ｯ繧ｹ繧定｡ｨ遉ｺ縺励※隕冶ｪ肴ｧ繧帝ｫ倥ａ縺ｾ縺・
- 繧ｿ繧､繝医Ν陦ｨ遉ｺ譎る俣: 蟶ｸ縺ｫ陦ｨ遉ｺ / 3遘・/ 5遘・/ 10遘・
- 繧ｿ繧､繝医Ν繝・じ繧､繝ｳ繝励Μ繧ｻ繝・ヨ:
  - **螳・ｮ吶ラ繧ｭ繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ鬚ｨ** (繝・ヵ繧ｩ繝ｫ繝・: 豺｡縺・搨繝ｻ豌ｴ濶ｲ邉ｻ譁・ｭ励∝濠騾乗・邏ｺ繝ｻ鮟定レ譎ｯ縺ｮ關ｽ縺｡逹縺・◆繝・じ繧､繝ｳ縲・
  - **繧ｷ繝ｳ繝励Ν**: 逋ｽ譁・ｭ励・ｻ堤ｸ√∬レ譎ｯ縺ｪ縺暦ｼ郁レ譎ｯ譛牙柑譎ゅ・蜊企乗・閭梧勹・峨・
  - **諠・ｱ逡ｪ邨・｢ｨ**: 逋ｽ譁・ｭ励・ｻ堤ｸ√∝濠騾乗・鮟定レ譎ｯ縲∽ｸ贋ｸ九↓陬・｣ｾ繝ｩ繧､繝ｳ・遺煤・峨ｒ霑ｽ蜉縲・
  - **繝九Η繝ｼ繧ｹ鬚ｨ**: Meiryo螟ｪ蟄励・ｫ倥さ繝ｳ繝医Λ繧ｹ繝医∝ｷｦ蟇・○繧る∈謚槫庄閭ｽ縲・
  - **繧､繝ｳ繝代け繝亥ｼｷ繧・*: 鮟・牡譁・ｭ励∝､ｧ縺阪ａ譁・ｭ励∝ｼｷ繧√・邵∝叙繧翫∝濠騾乗・鮟定レ譎ｯ縲∽ｸ贋ｸ九↓陬・｣ｾ繝ｩ繧､繝ｳ縲・
- 繧ｿ繧､繝医Ν蠑ｷ隱ｿ: ON/OFF
- 繧ｿ繧､繝医Ν閭梧勹騾乗・蠎ｦ: 0縲・00%
- 繧ｿ繧､繝医Ν菴咏區: 閭梧勹繝懊ャ繧ｯ繧ｹ縺ｮ菴咏區繧ｵ繧､繧ｺ・医ヴ繧ｯ繧ｻ繝ｫ・・
- 繧ｿ繧､繝医Ν讓ｪ蟷・: 逕ｻ髱｢蟷・↓蟇ｾ縺吶ｋ繧ｿ繧､繝医Ν繝懊ャ繧ｯ繧ｹ縺ｮ譛螟ｧ讓ｪ蟷・・・5縲・0%謗ｨ螂ｨ・・
- 繧ｿ繧､繝医Ν陦碁俣: 陦後＃縺ｨ縺ｮ髢馴囈

### 蠑ｷ隱ｿ繧ｭ繝ｼ繝ｯ繝ｼ繝峨・譖ｸ縺肴婿

繧ｿ繧､繝医Ν繝・く繧ｹ繝医・荳ｭ縺ｧ驥崎ｦ∬ｪ槭ｒ `縲舌疏・磯嚆莉倥″諡ｬ蠑ｧ・峨〒蝗ｲ繧縺ｨ縲√◎縺ｮ驛ｨ蛻・′閾ｪ蜍慕噪縺ｫ蠑ｷ隱ｿ・郁牡螟画峩縲√ヵ繧ｩ繝ｳ繝医し繧､繧ｺ諡｡螟ｧ縲∝､ｪ蟄怜喧・峨＆繧後∪縺吶・
萓具ｼ・
```text
縲舌ヶ繝ｩ繝・け繝帙・繝ｫ縲代↓關ｽ縺｡繧九→莠ｺ髢薙・縺ｩ縺・↑繧具ｼ・
```

### 邨ｵ譁・ｭ励・險伜捷縺ｮ蟇ｾ蠢・

繧ｿ繧､繝医Ν縺ｫ縺ｯ 閥, 笞・・ 血, 笨・ 笶・縺ｪ縺ｩ縺ｮ邨ｵ譁・ｭ励ｄ險伜捷繧剃ｽｿ逕ｨ縺ｧ縺阪∪縺吶ゅ◆縺縺励∵欠螳壹＠縺溘ヵ繧ｩ繝ｳ繝茨ｼ・u Gothic UI繧Мeiryo遲会ｼ峨′縺昴・邨ｵ譁・ｭ励・繧ｰ繝ｪ繝輔ｒ繧ｵ繝昴・繝医＠縺ｦ縺・↑縺・ｴ蜷医∝屁隗貞ｽ｢・郁ｱ・・・峨ｄ遨ｺ逋ｽ縺ｨ縺励※陦ｨ遉ｺ縺輔ｌ繧句ｴ蜷医′縺ゅｊ縺ｾ縺吶ゅす繧ｹ繝・Β縺ｮ陦ｨ遉ｺ蛻ｶ髯舌↓繧医ｋ繧ゅ・縺ｧ縺ゅｊ縲∝虚逕ｻ逕滓・閾ｪ菴薙・關ｽ縺｡縺壹↓騾ｲ陦後＠縺ｾ縺吶・

### 繧医￥縺ゅｋ陦ｨ遉ｺ蟠ｩ繧・

- **謾ｹ陦御ｽ咲ｽｮ縺ｮ蟠ｩ繧・*: 繧ｿ繧､繝医Ν縺・4譁・ｭ励ｒ雜・∴繧句ｴ蜷医∝渕譛ｬ逧・↓縺ｯ譁・ц荳翫・蛻・ｌ逶ｮ・医せ繝壹・繧ｹ繧・ｪｭ轤ｹ遲会ｼ峨∪縺溘・荳ｭ螟ｮ莉倩ｿ代〒2陦後↓閾ｪ蜍墓隼陦後＆繧後∪縺吶′縲∵э蝗ｳ縺励↑縺・ｽ咲ｽｮ縺ｧ謾ｹ陦後＆繧後ｋ縺薙→縺後≠繧翫∪縺吶ゅ◎縺ｮ蝣ｴ蜷医・縲∽ｺ句燕縺ｫ繧ｿ繧､繝医Ν繝・く繧ｹ繝医ｒ遏ｭ縺剰ｪｿ遽縺励※縺上□縺輔＞縲・
- **縺ｯ縺ｿ蜃ｺ縺・*: 繧ｿ繧､繝医Ν繧ｵ繧､繧ｺ繧呈･ｵ遶ｯ縺ｫ螟ｧ縺阪￥縺励∵ｨｪ蟷・繧貞ｰ上＆縺上☆繧九→縲∵枚蟄励′閭梧勹繝懊ャ繧ｯ繧ｹ縺九ｉ縺ｯ縺ｿ蜃ｺ縺励◆繧頑釜繧願ｿ斐＠縺悟ｴｩ繧後◆繧翫☆繧九％縺ｨ縺後≠繧翫∪縺吶ゅし繧､繧ｺ縺ｨ讓ｪ蟷・縺ｮ繝舌Λ繝ｳ繧ｹ繧定ｪｿ謨ｴ縺励※縺上□縺輔＞縲・

## 騾ｲ謐怜愛螳・

- 蜿ｰ譛ｬ: `script.txt` 縺ｫ蜀・ｮｹ縺後≠繧・
- 逕ｻ蜒・ 逕ｻ蜒乗椢謨ｰ蛻・・ `001.png` / `001.jpg` / `001.webp` 縺後≠繧・
- 髻ｳ螢ｰ: `audio/voice.wav` 縺後≠繧・
- 蟄怜ｹ・ `video/subtitles.ass` 縺後≠繧・
- 蜍慕判: `video/final.mp4` 縺後≠繧・
- 謚慕ｨｿ: `posted.txt` 縺後≠繧・

## 繝・せ繝・

pytest縺ｧ螳溯｡後〒縺阪∪縺吶・

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory
python -m pytest tests -q --basetemp .pytest_tmp -o cache_dir=.pytest_cache
```

蟇ｾ雎｡:

- parser
- project
- voicevox
- ffmpeg
- settings

## 繝医Λ繝悶Ν繧ｷ繝･繝ｼ繝・ぅ繝ｳ繧ｰ

### ChatGPT縺ｮJSON蠖｢蠑上′豁｣縺励￥縺ゅｊ縺ｾ縺帙ｓ

JSON莉･螟悶・隱ｬ譏取枚縲｀arkdown繧ｳ繝ｼ繝峨ヶ繝ｭ繝・け縲∽ｽ吝・縺ｪ繧ｫ繝ｳ繝槭・哩縺伜ｿ倥ｌ縺後↑縺・°遒ｺ隱阪＠縺ｦ縺上□縺輔＞縲・

### VOICEVOX縺瑚ｵｷ蜍輔＠縺ｦ縺・∪縺帙ｓ

VOICEVOX繧定ｵｷ蜍輔＠縺ｦ縺九ｉ蜀榊ｮ溯｡後＠縺ｦ縺上□縺輔＞縲６RL繧гpeaker id繧りｨｭ螳夂判髱｢縺ｧ遒ｺ隱阪〒縺阪∪縺吶・

### FFmpeg縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ

FFmpeg繧偵う繝ｳ繧ｹ繝医・繝ｫ縺励￣ATH繧帝壹＠縺ｦ縺上□縺輔＞縲１ATH繧帝壹＆縺ｪ縺・ｴ蜷医・險ｭ螳夂判髱｢縺ｧ `FFmpeg path` 繧呈欠螳壹＠縺ｦ縺上□縺輔＞縲・

### BGM縺悟・繧翫∪縺帙ｓ

`assets/bgm` 縺ｫ `mp3` 縺ｾ縺溘・ `wav` 縺悟・縺｣縺ｦ縺・ｋ縺狗｢ｺ隱阪＠縺ｦ縺上□縺輔＞縲りｨｭ螳夂判髱｢縺ｧ縲沓GM繧剃ｽｿ逕ｨ縺吶ｋ縲阪′ON縺ｫ縺ｪ縺｣縺ｦ縺・ｋ縺九ｂ遒ｺ隱阪＠縺ｦ縺上□縺輔＞縲・

### 蟄怜ｹ輔′陦ｨ遉ｺ縺輔ｌ縺ｾ縺帙ｓ

`subtitles.txt` 縺ｫ `start` / `end` / `text` 繧呈戟縺､JSON驟榊・縺御ｿ晏ｭ倥＆繧後※縺・ｋ縺狗｢ｺ隱阪＠縺ｦ縺上□縺輔＞縲ょ虚逕ｻ逕滓・蠕後↓ `video/subtitles.ass` 縺御ｽ懈・縺輔ｌ縺ｦ縺・ｋ縺九∬ｨｭ螳夂判髱｢縺ｧ縲悟ｭ怜ｹ輔ｒ菴ｿ逕ｨ縺吶ｋ縲阪′ON縺ｫ縺ｪ縺｣縺ｦ縺・ｋ縺九ｂ遒ｺ隱阪＠縺ｦ縺上□縺輔＞縲・

### 蟄怜ｹ慕┥縺崎ｾｼ縺ｿ縺ｫ螟ｱ謨励＠縺ｾ縺・

FFmpeg縺ｮ蟄怜ｹ輔ヵ繧｣繝ｫ繧ｿ繝ｼ縺ｧ螟ｱ謨励＠縺ｦ縺・ｋ蜿ｯ閭ｽ諤ｧ縺後≠繧翫∪縺吶Ａsubtitles.ass` 縺ｮ蠖｢蠑上：Fmpeg縺ｮ蟆主・迥ｶ豕√√ヵ繧ｩ繝ｳ繝医′隕九▽縺九ｉ縺ｪ縺・庄閭ｽ諤ｧ繧堤｢ｺ隱阪＠縺ｦ縺上□縺輔＞縲８indows讓呎ｺ悶・ `Yu Gothic` 繧貞━蜈医＠縺ｦ菴ｿ逕ｨ縺励∪縺吶・

### 逕ｻ蜒上′1譫壹ｂ縺ゅｊ縺ｾ縺帙ｓ

繝励Ο繧ｸ繧ｧ繧ｯ繝医・ `images` 繝輔か繝ｫ繝縺ｫ `001.png` 縺ｪ縺ｩ縺ｮ逕ｻ蜒上ｒ蜈･繧後※縺上□縺輔＞縲・

### 蜍慕判繝励Ξ繝薙Η繝ｼ縺ｧ縺阪∪縺帙ｓ

迺ｰ蠅・↓繧医▲縺ｦQt Multimedia縺ｧ蜀咲函縺ｧ縺阪↑縺・ｴ蜷医′縺ゅｊ縺ｾ縺吶ゅ悟虚逕ｻ繝輔か繝ｫ繝繧帝幕縺上阪°繧・`final.mp4` 繧堤峩謗･遒ｺ隱阪＠縺ｦ縺上□縺輔＞縲・

## YouTube PRIVATE繧｢繝・・繝ｭ繝ｼ繝・
莉雁屓縺ｮ繧｢繝・・繝ｭ繝ｼ繝画ｩ溯・縺ｯ縲∵里縺ｫ逕滓・貂医∩縺ｮ `projects/<project>/video/final.mp4` 縺縺代ｒYouTube縺ｸPRIVATE縺ｧ騾∽ｿ｡縺励∪縺吶ょ虚逕ｻ縺ｮ蜀咲函謌舌∬・蜍募・髢九∝・髢倶ｺ育ｴ・ゝikTok騾｣謳ｺ縲〆ouTube Analytics蜿門ｾ励・陦後＞縺ｾ縺帙ｓ縲・
迥ｶ諷狗ｮ｡逅・

- `project.json` 縺ｮ `job` 縺ｫ蜍慕判蛻ｶ菴懊・迥ｶ諷九ｒ菫晏ｭ倥＠縺ｾ縺吶・- `project.json` 縺ｮ `youtube_upload` 縺ｫYouTube繧｢繝・・繝ｭ繝ｼ繝臥憾諷九ｒ菫晏ｭ倥＠縺ｾ縺吶・- 蜍慕判蛻ｶ菴懃憾諷九→繧｢繝・・繝ｭ繝ｼ繝臥憾諷九・迢ｬ遶九＠縺ｦ縺・∪縺吶ゅい繝・・繝ｭ繝ｼ繝牙､ｱ謨玲凾繧・`job.status = video_ready` 縺ｮ繧医≧縺ｫ蜍慕判螳梧・迥ｶ諷九・邯ｭ謖√＆繧後∪縺吶・
Job status:

- `draft`
- `script_ready`
- `images_ready`
- `audio_ready`
- `video_ready`
- `quality_checked`
- `youtube_uploaded`
- `failed`

YouTube upload status:

- `pending`
- `uploading`
- `uploaded`
- `failed`

隱崎ｨｼ諠・ｱ:

1. Google Cloud Console縺ｧYouTube Data API v3繧呈怏蜉ｹ蛹悶＠縺ｾ縺吶・2. OAuth蜷梧э逕ｻ髱｢繧定ｨｭ螳壹＠縺ｾ縺吶・3. 繝・せ繧ｯ繝医ャ繝励い繝励Μ逕ｨOAuth client繧剃ｽ懈・縺励∪縺吶・4. client secret JSON繧偵ム繧ｦ繝ｳ繝ｭ繝ｼ繝峨＠縺ｾ縺吶・5. `.env.example` 繧・`.env` 縺ｫ繧ｳ繝斐・縺励～YOUTUBE_CLIENT_SECRETS_FILE` 縺ｫclient secret JSON縺ｮ繝代せ繧定ｨｭ螳壹＠縺ｾ縺吶・
`.env`縲…lient secret縲∥ccess token縲〉efresh token縺ｯGit縺ｸ霑ｽ蜉縺励↑縺・〒縺上□縺輔＞縲Ｓefresh token縺ｯWindows Credential Manager繧貞茜逕ｨ縺ｧ縺阪ｋ蝣ｴ蜷医・縺ｿ `keyring` 縺ｧ菫晏ｭ倥＠縺ｾ縺吶ょｮ牙・縺ｫ菫晏ｭ倥〒縺阪↑縺・腸蠅・〒縺ｯ縲∝ｹｳ譁・ヵ繧｡繧､繝ｫ縺ｸ菫晏ｭ倥○縺壹お繝ｩ繝ｼ縺ｧ蛛懈ｭ｢縺励∪縺吶・
繧｢繝・・繝ｭ繝ｼ繝・

1. 繝励Ο繧ｸ繧ｧ繧ｯ繝医〒 `video/final.mp4` 縺檎函謌先ｸ医∩縺ｧ縺ゅｋ縺薙→繧堤｢ｺ隱阪＠縺ｾ縺吶・2. 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨・縲刑ouTube Upload縲肴ｬ・〒迥ｶ諷九ｒ遒ｺ隱阪＠縺ｾ縺吶・3. `Upload to YouTube` 繧呈款縺励∪縺吶・4. 蛻晏屓縺ｮ縺ｿ繝悶Λ繧ｦ繧ｶ縺ｧGoogle OAuth隱崎ｨｼ繧定｡後＞縺ｾ縺吶・5. 謌仙粥縺吶ｋ縺ｨ `video_id`縲〆ouTube URL縲「pload timestamp 縺・`project.json` 縺ｫ菫晏ｭ倥＆繧後∪縺吶・
驥崎､・亟豁｢:

- `youtube_upload.video_id` 縺御ｿ晏ｭ俶ｸ医∩縺ｮ蝣ｴ蜷医・壼ｸｸ繧｢繝・・繝ｭ繝ｼ繝峨・螳溯｡後＠縺ｾ縺帙ｓ縲・- 謌仙粥貂医∩繝励Ο繧ｸ繧ｧ繧ｯ繝医〒縺ｯ `Retry Upload` 縺ｯ辟｡蜉ｹ縺ｧ縺吶・- Retry縺ｯ荳譎ら噪縺ｪ騾壻ｿ｡螟ｱ謨励°縺､video ID譛ｪ遒ｺ螳壹・蝣ｴ蜷医□縺台ｽｿ縺・∪縺吶・
retry:

- 500 / 502 / 503 / 504 縺ｪ縺ｩ縺ｮ荳譎ら噪HTTP繧ｨ繝ｩ繝ｼ縺ｨ騾壻ｿ｡譁ｭ縺ｮ縺ｿ蜀崎ｩｦ陦後＠縺ｾ縺吶・- 隱崎ｨｼ繧ｨ繝ｩ繝ｼ縲∵ｨｩ髯蝉ｸ崎ｶｳ縲∽ｸ肴ｭ｣縺ｪ蜍慕判縲〈uota雜・℃縺ｪ縺ｩ縺ｯ辟｡髯甚etry縺励∪縺帙ｓ縲・- retry縺ｯexponential backoff縺ｧ譛螟ｧ蝗樊焚縺ｾ縺ｧ陦後＞縲～logs/youtube.log` 縺ｫ險倬鹸縺励∪縺吶・
繝ｭ繧ｰ:

- YouTube蟆ら畑繝ｭ繧ｰ縺ｯ `logs/youtube.log` 縺ｫ菫晏ｭ倥＆繧後∪縺吶・- 險倬鹸縺吶ｋ蜀・ｮｹ: project ID縲「pload start/progress/success/failure縲＾Auth髢句ｧ・謌仙粥/螟ｱ謨励》oken refresh縲〉etry縲・- token縲…lient secret縲∬ｪ崎ｨｼ繧ｳ繝ｼ繝峨・繝ｭ繧ｰ繧ФI縺ｸ蜃ｺ蜉帙＠縺ｾ縺帙ｓ縲・
## TikTok Upload

TikTok Upload縺ｯ縲ゝikTok Content Posting API縺ｮUpload Content繧剃ｽｿ縺｣縺ｦ縲∝ｮ梧・貂医∩縺ｮ `projects/<project>/video/final.mp4` 縺縺代ｒTikTok Inbox縺ｸ騾√ｊ縺ｾ縺吶・
縺薙・讖溯・縺ｯDirect Post縺ｧ縺ｯ縺ゅｊ縺ｾ縺帙ｓ縲ゅい繝・・繝ｭ繝ｼ繝牙ｾ後↓TikTok繧｢繝励Μ繧帝幕縺阪！nbox騾夂衍縺九ｉ謚慕ｨｿ繧貞ｮ御ｺ・＠縺ｦ縺上□縺輔＞縲６I縺ｧ縺ｯ `SEND_TO_USER_INBOX` 繧偵卦ikTok繧｢繝励Μ縺ｧ謚慕ｨｿ螳御ｺ・′蠢・ｦ√阪→陦ｨ遉ｺ縺励∪縺吶・
### 莠句燕險ｭ螳・
1. TikTok Developer Portal縺ｧ繧｢繝励Μ繧剃ｽ懈・縺励∪縺吶・2. Desktop Login Kit繧定ｨｭ螳壹＠縺ｾ縺吶・3. Content Posting API繧定ｿｽ蜉縺励∪縺吶・4. `video.upload` scope繧堤筏隲九・謇ｿ隱阪＠縺ｾ縺吶・5. Redirect URI縺ｫ `http://127.0.0.1:*/callback/` 縺ｾ縺溘・螳滄圀縺ｫ菴ｿ縺・oopback URI繧堤匳骭ｲ縺励∪縺吶・6. `.env.example` 繧・`.env` 縺ｫ繧ｳ繝斐・縺励～TIKTOK_CLIENT_KEY` 縺ｨ `TIKTOK_REDIRECT_URI` 繧定ｨｭ螳壹＠縺ｾ縺吶・7. client secret縺ｯ `.env`縲～project.json`縲～settings.json` 縺ｫ菫晏ｭ倥＠縺ｾ縺帙ｓ縲ゅい繝励Μ縺ｮ `Connect TikTok` 縺ｧ蜈･蜉帙＠縲仝indows Credential Manager縺ｸ菫晏ｭ倥＠縺ｾ縺吶・
### 菴ｿ縺・婿

1. 蟇ｾ雎｡繝励Ο繧ｸ繧ｧ繧ｯ繝医〒 `video/final.mp4` 繧堤函謌舌＠縺ｾ縺吶・2. `Connect TikTok` 繧呈款縺励※OAuth隱崎ｨｼ縺励∪縺吶・3. `Upload to TikTok` 繧呈款縺励∪縺吶・4. 霆｢騾∝ｮ御ｺ・ｾ後～Check Status` 縺ｧ迥ｶ諷九ｒ遒ｺ隱阪＠縺ｾ縺吶・5. `TikTok繧｢繝励Μ縺ｧ謚慕ｨｿ螳御ｺ・′蠢・ｦ～ 縺ｨ陦ｨ遉ｺ縺輔ｌ縺溘ｉ縲ゝikTok繧｢繝励Μ蛛ｴ縺ｧ謚慕ｨｿ繧貞ｮ御ｺ・＠縺ｾ縺吶・
### 菫晏ｭ倥＆繧後ｋ迥ｶ諷・
`project.json` 縺ｫ縺ｯ `tiktok_upload` 縺ｨ縺励※莉･荳九ｒ菫晏ｭ倥＠縺ｾ縺吶Ａupload_url`縲∥ccess token縲〉efresh token縲…lient secret縺ｯ菫晏ｭ倥＠縺ｾ縺帙ｓ縲・
- `status`
- `remote_status`
- `publish_id`
- `uploaded_at`
- `last_checked_at`
- `retry_count`
- `last_error`
- `error_code`

### retry縺ｨ驥崎､・亟豁｢

- retry蟇ｾ雎｡縺ｯ荳譎ら噪縺ｪ騾壻ｿ｡螟ｱ謨励》imeout縲・29縲∝・隧ｦ陦悟庄閭ｽ縺ｪ5xx縺ｧ縺吶・- 隱崎ｨｼ繧ｨ繝ｩ繝ｼ縲∵ｨｩ髯蝉ｸ崎ｶｳ縲（nvalid parameter縲∝虚逕ｻ蠖｢蠑上お繝ｩ繝ｼ縲｝ending share荳企剞縺ｪ縺ｩ縺ｯ辟｡髯甚etry縺励∪縺帙ｓ縲・- 譌｢蟄倥・ `publish_id` 縺後≠繧翫∝・逅・ｸｭ繝ｻInbox蛻ｰ驕疲ｸ医∩繝ｻ螳御ｺ・ｸ医∩縺ｮ蝣ｴ蜷医∵眠縺励＞繧｢繝・・繝ｭ繝ｼ繝峨・髢句ｧ九＠縺ｾ縺帙ｓ縲・- Force Reupload縺ｯ螳溯｣・＠縺ｦ縺・∪縺帙ｓ縲・
### 繝ｭ繧ｰ

TikTok蟆ら畑繝ｭ繧ｰ縺ｯ `logs/tiktok.log` 縺ｫ菫晏ｭ倥＆繧後∪縺吶Ｕoken縲…lient secret縲∥uthorization code縲…allback URL蜈ｨ譁・「pload URL縺ｯ險倬鹸縺励∪縺帙ｓ縲・
## FAQ

### OpenAI API縺ｯ菴ｿ縺・∪縺吶°・・

菴ｿ縺・∪縺帙ｓ縲・hatGPT縺ｫ縺ｯ繝ｦ繝ｼ繧ｶ繝ｼ縺梧焔蜍輔〒雋ｼ繧贋ｻ倥￠縺ｾ縺吶・

### 閾ｪ蜍墓兜遞ｿ縺励∪縺吶°・・

縺励∪縺帙ｓ縲１hase4.5縺ｧ縺ｯ閾ｪ蜍墓兜遞ｿ縺ｯ螳溯｣・＠縺ｦ縺・∪縺帙ｓ縲・

### 逕ｻ蜒冗函謌植PI縺ｯ菴ｿ縺・∪縺吶°・・

菴ｿ縺・∪縺帙ｓ縲ら判蜒上・繝ｭ繝ｳ繝励ヨ繧偵さ繝斐・縺励※縲∽ｻｻ諢上・逕ｻ蜒冗函謌舌ヤ繝ｼ繝ｫ縺ｧ菴ｿ縺・燕謠舌〒縺吶・

### JSON縺悟｣翫ｌ縺ｦ縺・ｋ縺ｨ縺ｩ縺・↑繧翫∪縺吶°・・

譌･譛ｬ隱槭・繧ｨ繝ｩ繝ｼ繝｡繝・そ繝ｼ繧ｸ繧定｡ｨ遉ｺ縺励√ヵ繧｡繧､繝ｫ菫晏ｭ倥・陦後＞縺ｾ縺帙ｓ縲・

## 繧｢繝・・繝・・繝亥ｱ･豁ｴ

- 0.7.4 Phase7.4: 繧ｸ繝｣繝ｳ繝ｫ驟堺ｸ九・繧ｫ繝・ざ繝ｪ邂｡逅・・嚴螻､繝輔ぅ繝ｫ繧ｿ繝ｼ縲∬､・粋繝輔ぅ繝ｫ繧ｿ繝ｼ縲∵悴蛻・｡樊紛逅・∽ｸ諡ｬ繧ｫ繝・ざ繝ｪ螟画峩縲√き繝・ざ繝ｪ蛻･Analytics縺ｫ蟇ｾ蠢・- 0.7.3 Phase7.2縲・.3: Project Analytics縲，SV縺ｨ繝励Ο繧ｸ繧ｧ繧ｯ繝育ｴ蝉ｻ倥￠縲∝句挨謌千ｸｾ縲∵隼蝟・署譯医∫ｶ夂ｷｨ蛟呵｣懊〆ouTube/TikTok讓ｪ譁ｭ豈碑ｼ・↓蟇ｾ蠢・- 0.7.1 Phase7.1: AI繧｢繝峨ヰ繧､繧ｶ繝ｼ縲ヽule Engine縺ｫ繧医ｋ縺翫☆縺吶ａ繝・・繝・繧ｿ繧､繝医Ν縲∝宛菴懃岼讓吶√ヰ繝・ず縲∵隼蝟・署譯医↓蟇ｾ蠢・- 0.7.0 Phase7: Analytics繧ｿ繝悶，SV蛻・梵縲√Λ繝ｳ繧ｭ繝ｳ繧ｰ縲√ず繝｣繝ｳ繝ｫ蛻・梵縲√ち繧､繝医Ν蛻・梵縲√げ繝ｩ繝輔∬ｩ穂ｾ｡縲，SV繧ｨ繧ｯ繧ｹ繝昴・繝医↓蟇ｾ蠢・
- 0.6.5 Phase6.5: Cinematic Motion Engine縲ヽandom Motion縲゜en Burns縲√ヨ繝ｩ繝ｳ繧ｸ繧ｷ繝ｧ繝ｳ縲＾verlay縲´ight Effect縺ｫ蟇ｾ蠢・
- 0.6.0 Phase6: 繧ｪ繝ｼ繝励ル繝ｳ繧ｰ/繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ閾ｪ蜍戊ｿｽ蜉縲√ず繝｣繝ｳ繝ｫ蛻･縺ｮ邱城寔邱ｨ蜍慕判逕滓・縲・・分螟画峩縲…hapter.txt逕滓・縺ｫ蟇ｾ蠢・
- 0.5.3.5 Phase5.3.5: 蟾ｦ蛛ｴ繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｨ邏譚千ｮ｡逅・・蜿悶ｊ霎ｼ縺ｿ貂医∩逕ｻ蜒上お繝ｪ繧｢繧堤ｸｦ蟷・ｪｿ謨ｴ蜿ｯ閭ｽ縺ｫ螟画峩縺励∝叙繧願ｾｼ縺ｿ貂医∩逕ｻ蜒上・鬮倥＆蜈･蜉帙ｒ霑ｽ蜉
- 0.5.3.4 Phase5.3.4: YouTube/TikTok蛻･縺ｮ繧ｿ繧ｰ菫晏ｭ倥”ashtags.txt縺九ｉ縺ｮ閾ｪ蜍募・蜉帙∝宛菴懊Γ繝｢縲√ユ繝ｼ繝・繧ｿ繧ｰ縺ｮ繝ｯ繝ｳ繧ｯ繝ｪ繝・け繧ｳ繝斐・縺ｫ蟇ｾ蠢・
- 0.5.3.3 Phase5.3.3: 蟄怜ｹ輔・荳倶ｽ咲ｽｮ繧偵す繝ｧ繝ｼ繝亥虚逕ｻUI縺ｫ驥阪↑繧翫↓縺上＞螳牙・菴咲ｽｮ縺ｸ隱ｿ謨ｴ
- 0.5.3.2 Phase5.3.2: STEP6蟄怜ｹ輔・蜑企勁縲∫樟蝨ｨ繝励Ο繧ｸ繧ｧ繧ｯ繝域ｻ槫惠縲∵ｬ｡縺ｫ謚ｼ縺呎桃菴懊・繝上う繝ｩ繧､繝医ｒ霑ｽ蜉
- 0.5.2 Phase5.2: 逕ｻ蜒丈ｸ諡ｬ蜿悶ｊ霎ｼ縺ｿ縲√ラ繝ｩ繝・げ・・ラ繝ｭ繝・・縲，trl+V雋ｼ繧贋ｻ倥￠縲￣NG閾ｪ蜍募､画鋤縲・01.png蠖｢蠑上∈縺ｮ閾ｪ蜍輔Μ繝阪・繝縲√し繝繝阪う繝ｫ荳隕ｧ縺ｨ鬆・分螟画峩
- 0.5.1 Phase5.1: 逕ｻ蜒冗函謌舌・繝ｭ繝ｳ繝励ヨ荳諡ｬ繧ｳ繝斐・縲∫判蜒乗椢謨ｰ閾ｪ蜍募ｯｾ蠢懊∝・騾夂判蜒乗擅莉ｶ邱ｨ髮・√ユ繝ｳ繝励Ξ繝ｼ繝亥挨逕ｻ蜒乗擅莉ｶ蟇ｾ蠢・
- 0.5.0 Phase5: ASS蟄怜ｹ慕函謌舌：Fmpeg蟄怜ｹ慕┥縺崎ｾｼ縺ｿ縲∝ｭ怜ｹ戊ｨｭ螳壹，hatGPT JSON蟄怜ｹ募ｽ｢蠑乗隼蝟・
- 0.4.6 Phase4.6: BGM閾ｪ蜍戊ｿｽ蜉縲。GM髻ｳ驥剰ｨｭ螳壹。GM繝輔ぉ繝ｼ繝峨う繝ｳ/繝輔ぉ繝ｼ繝峨い繧ｦ繝・
- 0.4.5 Phase4.5: 蜩∬ｳｪ謾ｹ蝟・√Ο繧ｰ縲√し繝ｳ繝励Ν縲∫腸蠅・メ繧ｧ繝・け縲｝ytest霑ｽ蜉
- 0.4.0 Phase4: JSON隗｣譫舌〃OICEVOX縲：Fmpeg縲∝虚逕ｻ繝励Ξ繝薙Η繝ｼ
- 0.3.0 Phase3: 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨．ashboard縲√ユ繝ｳ繝励Ξ繝ｼ繝・
- 0.2.0 Phase2: PySide6蛹悶√・繝ｭ繧ｸ繧ｧ繧ｯ繝育ｮ｡逅・√ロ繧ｿ邂｡逅・
- 0.1.0 Phase1: Tkinter MVP

## 莉雁ｾ後・繝ｭ繝ｼ繝峨・繝・・

- 逕ｻ蜒冗函謌植PI騾｣謳ｺ
- video-use譛ｬ螳溯｣・
- SQLite菫晏ｭ・
- 謚慕ｨｿ螻･豁ｴ邂｡逅・
- 謚慕ｨｿ繧ｹ繧ｱ繧ｸ繝･繝ｼ繝ｫ邂｡逅・
- 閾ｪ蜍墓兜遞ｿ
- 蛻・梵繝繝・す繝･繝懊・繝・

Phase6縺ｧ縺ｯ縲∫判蜒冗函謌植PI縲＾penAI API縲，laude API縲；emini API縲∬・蜍墓兜遞ｿ縲∬・蜍募ｭ怜ｹ慕函謌植I縲仝hisper騾｣謳ｺ縲∝ｭ怜ｹ輔い繝九Γ繝ｼ繧ｷ繝ｧ繝ｳ縲∬､・焚BGM縲√ず繝｣繝ｳ繝ｫ蛻･BGM縲∝柑譫憺浹縺ｯ陦後▲縺ｦ縺・∪縺帙ｓ縲・
## Story AI Provider

Phase 8 adds optional AI story generation inside Story Composer. Phase 8.1 adds Gemini through the official Google Gen AI SDK while keeping Manual, Mock, and OpenAI providers available.

- Default provider: Gemini
- Default Gemini model: `gemini-3.5-flash-lite`
- Gemini presets: Economy (`gemini-3.5-flash-lite`), Balanced (`gemini-3.5-flash`), Quality (`gemini-3.6-flash`)
- OpenAI presets remain available: Economy (`gpt-5.6-luna`), Balanced (`gpt-5.6-terra`), Quality (`gpt-5.6-sol`)
- Gemini uses the official `google-genai` SDK and Structured Outputs with the shared Story JSON schema.
- OpenAI uses the official OpenAI Python SDK and Responses API with Structured Outputs.
- Chat Completions, browser automation, ChatGPT session reuse, unofficial endpoints, provider failover, and paid-model auto-switching are not used.
- Generated stories are first saved as `projects/<project>/story_generated_candidate.json`.
- `story.json` is replaced only after the user clicks `Use Generated Story`.
- `Export to Factory`, Automated Production, image generation, VOICEVOX, render, and upload do not start automatically.

### Gemini API setup and billing safety

1. Create a Gemini API key in Google AI Studio.
2. Copy `.env.example` to `.env`.
3. Set:

```env
GEMINI_API_KEY=
```

Gemini Free-tier-only mode is ON by default. Before a Gemini request can start, the app requires both user confirmations:

- Google AI Studio shows this API key's project is on the Free Tier.
- Billing is not enabled for this project.

The app stores only confirmation booleans/timestamps and a short irreversible API-key fingerprint. It never stores the Gemini API key in `settings.json`, project files, Story files, generation state, production state, or logs.

Free Tier availability is separated from billing safety:

- Model Free Tier availability means the official catalog has a Free Tier entry for the selected model.
- Project Tier and Billing status are user-confirmed because the app cannot safely infer them from the API.
- Local usage counts are only app-side safety caps, not Google-side remaining quota.
- The default local safety cap is 10 Gemini Story requests per UTC day.

If Free-tier-only is ON, generation is blocked for unknown/custom/paid-only models, missing confirmations, local cap reached, quota exhausted, or unknown charge risk. The app does not switch to OpenAI or a paid Gemini model automatically.

### OpenAI API setup

1. Create or use an OpenAI API account.
2. Create an API key in the OpenAI dashboard.
3. Copy `.env.example` to `.env`.
4. Set:

```env
OPENAI_API_KEY=
```

OpenAI API billing is separate from ChatGPT Plus. The app shows estimated cost before generation and records token usage when the SDK returns it. Estimates are not the final invoice amount.

### Story generation files

- `story_generation.json`: provider, model, status, retry count, token metrics, and cost estimate snapshot.
- `gemini_story_usage.json`: local Gemini safety counter. This is not Google quota.
- `story_generated_candidate.json`: validated generated Story waiting for user adoption.
- `story.json`: the canonical Story Composer source, updated only by manual import/save or `Use Generated Story`.
- `logs/story_provider.log`: sanitized provider lifecycle log. API keys, prompts, raw responses, and full Story text are not logged.

### Retry, Resume, and Cancel

- Retry is bounded and only for transient provider/network errors.
- Refusal, content filtering, invalid key, invalid model, quota/billing, invalid schema, and malformed structured output are not retried indefinitely.
- If generation was interrupted, Story Composer shows the saved state. Resume restores state only; retry starts a new API request and records the previous generation ID.
- Cancel prevents new retries and does not adopt partial Story output.

### Troubleshooting

- `GEMINI_API_KEY is not configured`: add it to `.env` or the process environment.
- `gemini_project_tier_unconfirmed`: confirm Free Tier in Google AI Studio before generating.
- `gemini_billing_unconfirmed`: confirm billing is disabled before generating.
- `gemini_key_confirmation_required`: the API key changed or was not confirmed; reconfirm Free Tier and billing status.
- `gemini_quota_exhausted`: stop for the day or wait for Google quota reset; the app will not auto-switch providers.
- `OPENAI_API_KEY is not configured`: add it to `.env` or the process environment when using OpenAI.
- `missing_openai_sdk`: run `python -m pip install -r requirements.txt`.
- `provider_refusal` or `content_filter`: edit the theme/request and try again.
- `structured_output_missing`: the model did not return data matching the schema; try again or select another model.
