
# Phase8.1 Gemini Story Provider（完了）

## 目的

Story AI Provider基盤へGemini Providerを追加し、Free-tier-onlyを初期ONにして無料枠優先でStory生成できるようにする。

## 実装

- Gemini Story Provider
- Google Gen AI SDK + Structured Outputs
- Gemini model catalog: `gemini-3.5-flash-lite` / `gemini-3.5-flash` / `gemini-3.6-flash`
- default providerをGeminiへ変更
- Free-tier-only guard
- Project Tier Free / Billing disabled のユーザー確認
- API key fingerprintによる確認無効化
- local usage safety cap
- Gemini固有error / finish reason分類
- Gemini usage metrics
- Story Composer UI統合
- Manual / Mock / OpenAI Provider維持

# Phase7 Automated Production Orchestrator（完了）

## 目的

有効な `story.json` から、選択した工程を順番に実行し、動画完成・投稿準備までをワンクリックで進められるようにする。

## 実装

- ProductionRun / ProductionStepモデル
- Step dependency管理
- Step Adapterによる既存Service再利用
- Preflight / Dry Run
- Existing artifact reuse
- Stale artifact判定
- Resume / Retry / Cancel
- `production_run.json` のatomic保存
- `.production.lock` による同一project二重Run防止
- Automated Production専用Widget
- `logs/production.log`

# Phase6 Story Composer（完了）

## 目的

テーマからタイトル、構成、ナレーション、字幕、画像プロンプトをまとめた `story.json` を作成し、明示Exportで既存Factoryへ接続できるようにする。

## 実装

- Story / Sceneモデル
- `projects/<project>/story.json` と `story_manifest.json`
- ManualPromptProviderによる手動AI用Prompt生成
- Story JSON parse / validation
- Resume / Reset
- StoryFactoryAdapterによる明示Export
- Export Preview
- バックアップ付きFactoryファイルExport
- Story Composer専用Widget
- 既存ChatGPT取込との共存

# Phase5.2 Prompt Library + Theme Templates（完了）

## 目的

画像生成promptの品質指定・構図・テーマ別ルールをコードから分離し、YAMLテンプレートで管理できるようにする。

## 実装

- YAMLベースの `prompt_library/` を追加
- `generic_space` と `black_hole` / `star` / `planet` / `galaxy` / `nebula` / `solar_system` テーマを追加
- template schema検証、安全なYAML読み込み、単一継承とmergeに対応
- project topic / title / category / genre / series / tags / image promptの重み付きAuto判定を追加
- Manual template選択とproject.jsonへの保存に対応
- Prompt Optimizerへtemplate rule、scene選択、原文優先、長さ制御を統合
- manifestへtemplate判定、適用/skipルール、scene情報を保存
- AI Image Generation欄にTemplate Mode、Manual Template、Resolved Template、Reload Templatesを追加

﻿# AI Video Factory Roadmap

# Phase5.1 Image Prompt Optimizer（完了）

## 目的

Cloudflare Workers AIへ送る画像promptを、原文を守ったままルールベースで改善する

## 実装

- `image_prompts.txt` の原文promptを正本として保持
- Prompt Optimizer ON/OFF
- Optimizer OFF時は原文promptをそのまま送信
- sceneごとの構図差別化
- 原文指定と衝突する構図・写実・no text指定の回避
- 重複品質語句の除去
- Cloudflare公式 `maxLength: 2048` に合わせた段階的prompt圧縮
- Original / Optimized prompt preview
- Applied / Skipped / Removed rules表示
- Optimized promptコピー
- manifestへのoptimizer詳細保存

# Phase5 AI Image Generation・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
菫晏ｭ俶ｸ医∩縺ｮ逕ｻ蜒上・繝ｭ繝ｳ繝励ヨ縺九ｉ縲，loudflare Workers AI縺ｧ荳崎ｶｳ逕ｻ蜒上□縺代ｒ逕滓・縺ｧ縺阪ｋ繧医≧縺ｫ縺吶ｋ

## 螳溯｣・
- provider髱樔ｾ晏ｭ倥・Image Generation蝓ｺ逶､
- Cloudflare Workers AI provider
- `@cf/black-forest-labs/flux-1-schnell` 蟇ｾ蠢・- `image_prompts.txt` 縺九ｉ縺ｮ逕ｻ蜒冗函謌・- `projects/<project>/images/001.png` 蠖｢蠑丈ｿ晏ｭ・- 譌｢蟄倡判蜒峻kip
- 迥ｶ諷九・manifest菫晏ｭ・- retry / cancel / 蛻ｩ逕ｨ荳企剞
- 譛蟆城剞縺ｮAI Image Generation UI

## Vision

AI Video Factory 縺ｯ縲√ユ繝ｼ繝槭ｒ蜈･蜉帙☆繧九□縺代〒繧ｷ繝ｧ繝ｼ繝亥虚逕ｻ繧貞濠閾ｪ蜍輔〒蛻ｶ菴懊〒縺阪ｋ Windows 繝・せ繧ｯ繝医ャ繝励い繝励Μ繧堤岼謖・＠縺ｾ縺吶・

譛邨ら岼讓吶・

繝・・繝槫・蜉・
竊・
蜿ｰ譛ｬ菴懈・
竊・
逕ｻ蜒冗函謌・
竊・
髻ｳ螢ｰ逕滓・
竊・
蜍慕判逕滓・
竊・
謚慕ｨｿ

縺ｾ縺ｧ繧・0蛻・ｻ･蜀・〒螳御ｺ・〒縺阪ｋ縺薙→縺ｧ縺吶・

---

# Phase1・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

蜍慕判繝励Ο繧ｸ繧ｧ繧ｯ繝育ｮ｡逅・・蝓ｺ遉弱ｒ菴懊ｋ

## 螳溯｣・

- 繝・・繝槫・蜉・
- 蜍慕判譎る俣驕ｸ謚・
- 繧ｸ繝｣繝ｳ繝ｫ驕ｸ謚・
- ChatGPT逕ｨ繝励Ο繝ｳ繝励ヨ逕滓・
- 繝励Ο繧ｸ繧ｧ繧ｯ繝医ヵ繧ｩ繝ｫ繝菴懈・
- topic.txt逕滓・
- README菴懈・

---

# Phase2・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

蜍慕判蛻ｶ菴懊ｒ邂｡逅・〒縺阪ｋ繧医≧縺ｫ縺吶ｋ

## 螳溯｣・

- AI Video Factory縺ｸ蜷咲ｧｰ螟画峩
- 繝繝ｼ繧ｯ繝｢繝ｼ繝蔚I
- 繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ
- 繝阪ち邂｡逅・
- ChatGPT蝗樒ｭ斐う繝ｳ繝昴・繝・
- 蝗樒ｭ碑ｧ｣譫・
- 騾ｲ謐礼ｮ｡逅・
- 繝・Φ繝励Ξ繝ｼ繝育ｮ｡逅・
- 繝輔か繝ｫ繝邂｡逅・
- VideoEditor險ｭ險・

---

# Phase3・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

蜍慕判蛻ｶ菴懊ｒ荳譛ｬ驕薙↓縺吶ｋ

## 螳溯｣・

- 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝・
- STEP陦ｨ遉ｺ
- Dashboard
- 荳諡ｬ繝阪ち邂｡逅・
- 繧ｷ繝ｪ繝ｼ繧ｺ邂｡逅・
- 繝励Ξ繝薙Η繝ｼ邱ｨ髮・
- 繧ｿ繧ｰ邂｡逅・
- 繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢
- 蜈･蜉幄｣懷ｮ・

---

# Phase4・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

蜍慕判蛻ｶ菴懊ｒ蜊願・蜍募喧縺吶ｋ

## 螳溯｣・

- ChatGPT JSON蜃ｺ蜉・
- JSON閾ｪ蜍戊ｧ｣譫・
- VOICEVOX騾｣謳ｺ
- FFmpeg騾｣謳ｺ
- 蜍慕判逕滓・
- 蜍慕判繝励Ξ繝薙Η繝ｼ
- 逕ｻ蜒上・繝ｭ繝ｳ繝励ヨ邂｡逅・
- README譖ｴ譁ｰ

## 螳御ｺ・＠縺滉ｽ懈･ｭ

- GitHub繝ｪ繝昴ず繝医Μ菴懈・
- Git蛻晏屓Push
- FFmpeg蟆主・
- PATH險ｭ螳・
- FFmpeg蜍穂ｽ懃｢ｺ隱・
- VOICEVOX蟆主・
- VOICEVOX Engine蜍穂ｽ懃｢ｺ隱・
- AI Video Factory縺ｧ蜍慕判逕滓・謌仙粥
- DEVELOPMENT_RULES.md菴懈・

---

# Phase4.5・井ｺ亥ｮ夲ｼ・

## 逶ｮ逧・

蜩∬ｳｪ蜷台ｸ翫・螳牙ｮ壼喧

## 螳溯｣・ｺ亥ｮ・

- 繝舌げ菫ｮ豁｣
- 繝ｪ繝輔ぃ繧ｯ繧ｿ繝ｪ繝ｳ繧ｰ
- 蜍穂ｽ懃｢ｺ隱・
- 繝・せ繝郁ｿｽ蜉
- 繧ｵ繝ｳ繝励Ν繝・・繧ｿ霑ｽ蜉
- 繝ｭ繧ｰ讖溯・霑ｽ蜉
- 迺ｰ蠅・メ繧ｧ繝・け
- README謾ｹ蝟・
- 繝舌・繧ｸ繝ｧ繝ｳ邂｡逅・

---

# Phase4.6・井ｺ亥ｮ夲ｼ・

## 逶ｮ逧・

蜍慕判蜩∬ｳｪ蜷台ｸ・

## 螳溯｣・ｺ亥ｮ・

- BGM霑ｽ蜉
- BGM髻ｳ驥剰ｨｭ螳・
- BGM閾ｪ蜍輔Ν繝ｼ繝・
- BGM繝輔ぉ繝ｼ繝峨い繧ｦ繝・
- assets/bgm蟇ｾ蠢・

---

# Phase5・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

蟄怜ｹ募ｯｾ蠢・

## 螳溯｣・

- 蟄怜ｹ慕┥縺崎ｾｼ縺ｿ
- 蟄怜ｹ輔し繧､繧ｺ險ｭ螳・
- 蟄怜ｹ穂ｽ咲ｽｮ險ｭ螳・
- 蟄怜ｹ桧N/OFF
- 蟄怜ｹ輔い繧ｦ繝医Λ繧､繝ｳ險ｭ螳・
- 蟄怜ｹ募ｽｱ險ｭ螳・
- ChatGPT JSON縺ｮ譎る俣莉倥″蟄怜ｹ募ｽ｢蠑・
- ASS蟄怜ｹ慕函謌・

---

# Phase5.1・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

逕ｻ蜒冗函謌舌Ρ繝ｼ繧ｯ繝輔Ο繝ｼ謾ｹ蝟・

## 螳溯｣・

- 逕ｻ蜒冗函謌舌・繝ｭ繝ｳ繝励ヨ荳諡ｬ繧ｳ繝斐・
- 逕ｻ蜒乗椢謨ｰ險ｭ螳壹↓蠢懊§縺溘・繝ｭ繝ｳ繝励ヨ謨ｰ縺ｮ閾ｪ蜍募､画峩
- 逕ｻ蜒丞・騾壽擅莉ｶ縺ｮ邱ｨ髮・
- 繝・Φ繝励Ξ繝ｼ繝亥挨逕ｻ蜒乗擅莉ｶ縺ｮ蜿肴丐
- 繧ｳ繝斐・蜑阪・繝励Ξ繝薙Η繝ｼ縺ｨ邱ｨ髮・
- ChatGPT縺ｸ1蝗櫁ｲｼ繧九□縺代〒隍・焚逕ｻ蜒上ｒ逕滓・縺ｧ縺阪ｋ蠖｢蠑上∈謾ｹ蝟・

---

# Phase5.2・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

逕ｻ蜒丞叙繧願ｾｼ縺ｿ菴懈･ｭ繧貞柑邇・喧縺吶ｋ

## 螳溯｣・

- 逕ｻ蜒上ラ繝ｩ繝・げ・・ラ繝ｭ繝・・蜿悶ｊ霎ｼ縺ｿ
- 繝輔ぃ繧､繝ｫ驕ｸ謚槫叙繧願ｾｼ縺ｿ
- Ctrl+V雋ｼ繧贋ｻ倥￠蟇ｾ蠢・
- PNG閾ｪ蜍募､画鋤
- 001.png蠖｢蠑上∈縺ｮ閾ｪ蜍輔Μ繝阪・繝
- 繧ｵ繝繝阪う繝ｫ荳隕ｧ
- 逕ｻ蜒城・分螟画峩

---

# Phase5.3・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

蜍慕判繧ｿ繧､繝医Ν繧ｪ繝ｼ繝舌・繝ｬ繧､讖溯・

## 螳溯｣・

- 繧ｿ繧､繝医Ν陦ｨ遉ｺ讖溯・
- 蜊企乗・閭梧勹莉倥″繧ｿ繧､繝医Ν陦ｨ遉ｺ
- 陦ｨ遉ｺ譎る俣險ｭ螳夲ｼ亥ｸｸ縺ｫ陦ｨ遉ｺ / 3遘・/ 5遘・/ 10遘抵ｼ・
- 繧ｿ繧､繝医Ν菴咲ｽｮ險ｭ螳夲ｼ井ｸ・/ 荳ｭ螟ｮ / 荳具ｼ・
- 繧ｿ繧､繝医ΝON/OFF險ｭ螳・

---

# Phase5.3.1・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

繧ｿ繧､繝医Ν繝・じ繧､繝ｳ蠑ｷ蛹厄ｼ医ョ繧ｶ繧､繝ｳ繝励Μ繧ｻ繝・ヨ縲・㍾隕∬ｪ槫ｼｷ隱ｿ縲∬レ譎ｯ繝懊ャ繧ｯ繧ｹ謾ｹ蝟・↑縺ｩ・・

## 螳溯｣・

- 繧ｿ繧､繝医Ν繝・じ繧､繝ｳ繝励Μ繧ｻ繝・ヨ・医す繝ｳ繝励Ν / 諠・ｱ逡ｪ邨・｢ｨ / 螳・ｮ吶ラ繧ｭ繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ鬚ｨ / 繝九Η繝ｼ繧ｹ鬚ｨ / 繧､繝ｳ繝代け繝亥ｼｷ繧・ｼ・
- 驥崎ｦ∬ｪ槫ｼｷ隱ｿ險俶ｳ包ｼ・縲舌疏 縺ｧ蝗ｲ縺ｾ繧後◆邂・園縺ｮ繧ｫ繝ｩ繝ｼ・・し繧､繧ｺ螟画峩・・
- 閭梧勹繝懊ャ繧ｯ繧ｹ縺ｮ繧ｫ繧ｹ繧ｿ繝槭う繧ｺ・磯乗・蠎ｦ縲∽ｽ咏區縲∵ｨｪ蟷・縲∬｡碁俣・・
- 諠・ｱ逡ｪ邨・｢ｨ繝ｻ繧､繝ｳ繝代け繝亥ｼｷ繧√↓縺翫￠繧倶ｸ贋ｸ玖｣・｣ｾ繝ｩ繧､繝ｳ・遺煤・・
- 邨ｵ譁・ｭ励ｄ迚ｹ谿願ｨ伜捷縺ｮ繧ｵ繝昴・繝亥ｼｷ蛹悶√♀繧医・蟾ｦ蟇・○陦ｨ遉ｺ蟇ｾ蠢・

---

# Phase5.3.2・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨・蠕ｮ菫ｮ豁｣
## 螳溯｣・
- 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨°繧唄TEP6蟄怜ｹ輔ｒ蜑企勁
- STEP螳御ｺ・ｾ後↓迴ｾ蝨ｨ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝医∈貊槫惠縺吶ｋ繧医≧縺ｫ菫ｮ豁｣
- 谺｡縺ｫ謚ｼ縺吶・繧ｿ繝ｳ繝ｻ蜈･蜉帶ｬ・ｒ繝上う繝ｩ繧､繝医☆繧九ぎ繧､繝峨ｒ霑ｽ蜉
---

# Phase5.3.3・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
繧ｷ繝ｧ繝ｼ繝亥虚逕ｻUI縺ｫ驥阪↑繧翫↓縺上＞蟄怜ｹ穂ｽ咲ｽｮ縺ｸ隱ｿ謨ｴ縺吶ｋ
## 螳溯｣・
- 蟄怜ｹ輔・荳倶ｽ咲ｽｮ繧堤判髱｢荳ｭ螟ｮ縺ｮ蟆代＠荳九∈遘ｻ蜍・
- TikTok / YouTube Shorts縺ｮ隧ｳ邏ｰ陦ｨ遉ｺ縺ｨ驥阪↑繧翫↓縺上＞螳牙・菴咲ｽｮ縺ｸ螟画峩
---

# Phase5.3.4・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

謚慕ｨｿ貅門ｙ逕ｨ縺ｮ繝｡繝｢縺ｨ繧ｿ繧ｰ繧ｳ繝斐・菴懈･ｭ繧貞柑邇・喧縺吶ｋ

## 螳溯｣・

- YouTube繧ｿ繧ｰ菫晏ｭ倥→TikTok繧ｿ繧ｰ菫晏ｭ倥ｒ蛻・屬
- `hashtags.txt` 縺九ｉYouTube蜷代￠繧ｿ繧ｰ繧・`#` 縺ｪ縺励・繧ｫ繝ｳ繝槫玄蛻・ｊ縺ｧ閾ｪ蜍募・蜉・
- `hashtags.txt` 縺九ｉTikTok蜷代￠繧ｿ繧ｰ繧・`#` 莉倥″縺ｧ閾ｪ蜍募・蜉帙＠縲～#VOICEVOX` 繧定・蜍戊ｿｽ蜉
- 荳諡ｬ繝阪ち邂｡逅・・荳九↓10蛟九・蛻ｶ菴懊Γ繝｢谺・ｒ霑ｽ蜉
- 繝｡繝｢縲√ユ繝ｼ繝槭〆ouTube繧ｿ繧ｰ縲ゝikTok繧ｿ繧ｰ縺ｮ繝ｯ繝ｳ繧ｯ繝ｪ繝・け繧ｳ繝斐・縺ｫ蟇ｾ蠢・
- 蟾ｦ蛛ｴ縺ｮ謫堺ｽ懊お繝ｪ繧｢繧偵せ繧ｯ繝ｭ繝ｼ繝ｫ蜿ｯ閭ｽ縺ｫ螟画峩

---

# Phase5.3.5・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

逕ｻ髱｢蜀・・荳隕ｧ繧ｨ繝ｪ繧｢縺檎強縺上※隕句・繧後ｋ蝠城｡後ｒ謾ｹ蝟・☆繧・

## 螳溯｣・

- 蟾ｦ蛛ｴ縺ｮ繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｨ荳諡ｬ繝阪ち邂｡逅・・邵ｦ蟷・ｒ隱ｿ謨ｴ縺ｧ縺阪ｋ繧医≧縺ｫ螟画峩
- 邏譚千ｮ｡逅・・蜿悶ｊ霎ｼ縺ｿ貂医∩逕ｻ蜒上お繝ｪ繧｢縺ｨ邏譚蝉ｸ隕ｧ縺ｮ邵ｦ蟷・ｒ隱ｿ謨ｴ縺ｧ縺阪ｋ繧医≧縺ｫ螟画峩
- 蜿悶ｊ霎ｼ縺ｿ貂医∩逕ｻ蜒上お繝ｪ繧｢縺ｫ鬮倥＆蜈･蜉帙ｒ霑ｽ蜉縺励∵焚蛟､縺ｧ邵ｦ蟷・ｒ螟画峩縺ｧ縺阪ｋ繧医≧縺ｫ菫ｮ豁｣

---

# Phase6・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

繝悶Λ繝ｳ繝牙喧縺ｨ邱城寔邱ｨ蜍慕判菴懈・縺ｫ蟇ｾ蠢懊＠縲∝虚逕ｻ驥冗肇繝ｯ繝ｼ繧ｯ繝輔Ο繝ｼ繧貞ｼｷ蛹悶☆繧・

## 螳溯｣・

- 繧ｪ繝ｼ繝励ル繝ｳ繧ｰ閾ｪ蜍戊ｿｽ蜉
- 繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ閾ｪ蜍戊ｿｽ蜉
- `assets/intro` / `assets/ending` 蟇ｾ蠢・
- 險ｭ螳夂判髱｢縺ｫ繧ｪ繝ｼ繝励ル繝ｳ繧ｰ/繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰON/OFF繧定ｿｽ蜉
- 繝帙・繝/蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨→蜷後§髫主ｱ､縺ｫ邱城寔邱ｨ繧ｿ繝悶ｒ霑ｽ蜉
- 繧ｸ繝｣繝ｳ繝ｫ縺斐→縺ｮ螳梧・貂医∩蜍慕判荳隕ｧ繧定ｿｽ蜉
- 邱城寔邱ｨ縺ｧ縺､縺ｪ縺仙虚逕ｻ鬆・ｒ荳贋ｸ九・繧ｿ繝ｳ縺ｧ螟画峩縺ｧ縺阪ｋ繧医≧縺ｫ蟇ｾ蠢・
- FFmpeg concat 縺ｫ繧医ｋ邱城寔邱ｨ蜍慕判逕滓・
- 邱城寔邱ｨ縺ｸ縺ｮ繧ｪ繝ｼ繝励ル繝ｳ繧ｰ/繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ霑ｽ蜉
- `exports/series/<series>_complete.mp4` 蜃ｺ蜉・
- `chapter.txt` 逕滓・

---

# Phase6.5・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

髱呎ｭ｢逕ｻ縺九ｉ逕滓・縺吶ｋ蜍慕判縺ｫ譏逕ｻ鬚ｨ繝ｻ繝峨く繝･繝｡繝ｳ繧ｿ繝ｪ繝ｼ鬚ｨ縺ｮ蜍輔″繧定ｿｽ蜉縺吶ｋ

## 螳溯｣・

- Motion Style險ｭ螳壹ｒ霑ｽ蜉
- Static / Slow Zoom In / Slow Zoom Out / Pan / Ken Burns / Random Motion 縺ｫ蟇ｾ蠢・
- Random Motion縺ｧ逕ｻ蜒上＃縺ｨ縺ｫ逡ｰ縺ｪ繧区ｼ泌・繧定・蜍暮←逕ｨ
- 蜷後§貍泌・縺碁｣邯壹＠縺ｪ縺・ｈ縺・↓蛻ｶ蠕｡
- 逕ｻ蜒上・繝ｭ繝ｳ繝励ヨ縺ｮ蜀・ｮｹ縺ｫ蠢懊§縺欖cene Motion繧貞渚譏
- 繧ｺ繝ｼ繝騾溷ｺｦ險ｭ螳壹ｒ霑ｽ蜉
- Fade / Cross Fade / Zoom Fade / Slide / None 縺ｮ繝医Λ繝ｳ繧ｸ繧ｷ繝ｧ繝ｳ縺ｫ蟇ｾ蠢・
- `assets/overlay` 繝輔か繝ｫ繝繧定ｿｽ蜉
- mp4 / png / jpg / webp 縺ｮ繧ｪ繝ｼ繝舌・繝ｬ繧､邏譚舌↓蟇ｾ蠢・
- Light Effect險ｭ螳壹ｒ霑ｽ蜉
- 邏譚千ｮ｡逅・・繧ｵ繝繝阪う繝ｫ荳隕ｧ縺ｫMotion蜷阪ｒ陦ｨ遉ｺ
- FFmpeg縺ｮ縺ｿ縺ｧMotion Engine繧貞ｮ溯｣・

---

# Phase7・亥ｮ御ｺ・ｼ・

## 逶ｮ逧・

繝√Ε繝ｳ繝阪Ν蛻・梵繝ｻ驕句霧繝繝・す繝･繝懊・繝峨↓蟇ｾ蠢懊＠縲，SV縺縺代〒蜍慕判謌千ｸｾ繧呈滑謠｡縺ｧ縺阪ｋ繧医≧縺ｫ縺吶ｋ

## 螳溯｣・

- Analytics繧ｿ繝冶ｿｽ蜉
- YouTube Studio / TikTok Studio CSV繧､繝ｳ繝昴・繝・
- 邱丞虚逕ｻ謨ｰ縲∫ｷ丞・逕滓焚縲∝ｹｳ蝮・・逕滓焚縲∵怙鬮・譛菴主・逕滓焚縲√＞縺・・縲√さ繝｡繝ｳ繝医∫紫縺ｮ閾ｪ蜍暮寔險・
- 蜀咲函謨ｰ縲√＞縺・・縲√さ繝｡繝ｳ繝医√＞縺・・邇・√さ繝｡繝ｳ繝育紫縺ｮTOP10繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ
- 繝励Ο繧ｸ繧ｧ繧ｯ繝域ュ蝣ｱ繧貞茜逕ｨ縺励◆繧ｸ繝｣繝ｳ繝ｫ蛻・梵
- 繧ｿ繧､繝医Ν鬆ｻ蜃ｺ繝ｯ繝ｼ繝牙・譫・
- 繧ｿ繧､繝医Ν繝代ち繝ｼ繝ｳ蛻・梵
- matplotlib縺ｫ繧医ｋ繧ｰ繝ｩ繝戊｡ｨ遉ｺ
- 蟷ｳ蝮・・逕滓焚縺ｨ蟷ｳ蝮・＞縺・・邇・ｒ蜈・↓縺励◆5谿ｵ髫手ｩ穂ｾ｡
- 繝ｫ繝ｼ繝ｫ繝吶・繧ｹ縺ｮAI Video Factory繧ｳ繝｡繝ｳ繝・
- 繧ｿ繧､繝医Ν縲√ず繝｣繝ｳ繝ｫ縲∝・逕滓焚莉･荳翫∵兜遞ｿ譌･縲∬ｩ穂ｾ｡縺ｫ繧医ｋ讀懃ｴ｢
- 蛻・梵邨先棡CSV繧ｨ繧ｯ繧ｹ繝昴・繝・

---

# Phase7.1・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・

Analytics繝・・繧ｿ繧貞・縺ｫ縲∵ｬ｡縺ｫ菴懊ｋ縺ｹ縺榊虚逕ｻ繝・・繝槭→蛻ｶ菴懈隼蝟・｡医ｒ繝ｫ繝ｼ繝ｫ繝吶・繧ｹ縺ｧ謠先｡医☆繧・

## 螳溯｣・

- AI繧｢繝峨ヰ繧､繧ｶ繝ｼ繧ｿ繝冶ｿｽ蜉
- 莉頑律縺ｮ蛻・梵陦ｨ遉ｺ
- CSV蛻・梵邨先棡縺九ｉ縺ｮ閾ｪ蜍輔さ繝｡繝ｳ繝育函謌・
- 縺翫☆縺吶ａ繝・・繝櫁｡ｨ遉ｺ
- 縺翫☆縺吶ａ繧ｿ繧､繝医Ν逕滓・
- 谺｡縺ｮ莨∫判謠先｡・
- 謾ｹ蝟・・繧､繝ｳ繝郁｡ｨ遉ｺ
- 蛻ｶ菴懃岼讓吶→騾ｲ謐励ヰ繝ｼ陦ｨ遉ｺ
- 螳溽ｸｾ繝舌ャ繧ｸ陦ｨ遉ｺ
- topics.json 縺ｨ繝励Ο繧ｸ繧ｧ繧ｯ繝域ュ蝣ｱ縺九ｉ繝阪ち蝨ｨ蠎ｫ繧帝寔險・
- 豈取律縺ｮ荳險陦ｨ遉ｺ
- OpenAI API縺ｪ縺ｩ螟夜ΚAI API繧剃ｽｿ繧上↑縺Сule Engine螳溯｣・
---

# Phase7.2・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
CSV蛻・梵邨先棡繧貞推蜍慕判繝励Ο繧ｸ繧ｧ繧ｯ繝医∈邏蝉ｻ倥￠縲∝句挨謌千ｸｾ繧堤｢ｺ隱阪〒縺阪ｋ繧医≧縺ｫ縺吶ｋ

## 螳溯｣・
- YouTube / TikTok CSV縺ｨ繝励Ο繧ｸ繧ｧ繧ｯ繝医・閾ｪ蜍慕ｴ蝉ｻ倥￠
- 譛ｪ邏蝉ｻ倥￠蜍慕判縺ｮ謇句虚邏蝉ｻ倥￠
- 繝励Ο繧ｸ繧ｧ繧ｯ繝医＃縺ｨ縺ｮ謌千ｸｾ菫晏ｭ・- YouTube / TikTok蛟句挨謌千ｸｾ陦ｨ遉ｺ
- 蛟句挨謗ｨ遘ｻ繧ｰ繝ｩ繝慕畑縺ｮ繧ｰ繝ｩ繝輔ョ繝ｼ繧ｿCSV隱ｭ霎ｼ
- 謚慕ｨｿ迥ｶ諷九・閾ｪ蜍慕｢ｺ隱・- YouTube Studio 3繝輔ぃ繧､繝ｫ蜿冶ｾｼ蟇ｾ蠢・
---

# Phase7.3・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
蛟句挨蜍慕判縺ｮ謌千ｸｾ縺九ｉ縲∽ｼｸ縺ｳ縺溽炊逕ｱ縺ｨ谺｡蝗樊隼蝟・｡医ｒ謠先｡医☆繧・
## 螳溯｣・
- 蜍慕判縺斐→縺ｮ5谿ｵ髫手ｩ穂ｾ｡
- 莨ｸ縺ｳ縺溽炊逕ｱ縺ｮ繝ｫ繝ｼ繝ｫ繝吶・繧ｹ蛻・梵
- 谺｡蝗樊隼蝟・｡・- 邯夂ｷｨ繝・・繝樊署譯・- YouTube / TikTok讓ｪ譁ｭ豈碑ｼ・- 繝繝・す繝･繝懊・繝牙ｼｷ蛹・
---

# Phase7.4・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
蜍慕判謨ｰ縺悟｢励∴縺ｦ繧ゅ√ず繝｣繝ｳ繝ｫ繝ｻ繧ｫ繝・ざ繝ｪ繝ｻ繧ｷ繝ｪ繝ｼ繧ｺ縺ｧ邏譌ｩ縺上・繝ｭ繧ｸ繧ｧ繧ｯ繝医ｒ謨ｴ逅・・讀懃ｴ｢縺ｧ縺阪ｋ繧医≧縺ｫ縺吶ｋ

## 螳溯｣・
- 繧ｸ繝｣繝ｳ繝ｫ驟堺ｸ九・繧ｫ繝・ざ繝ｪ邂｡逅・- 繝励Ο繧ｸ繧ｧ繧ｯ繝医∈縺ｮ繧ｫ繝・ざ繝ｪ險ｭ螳・- 繧ｸ繝｣繝ｳ繝ｫ繝ｻ繧ｫ繝・ざ繝ｪ繝ｻ繧ｷ繝ｪ繝ｼ繧ｺ縺ｮ髫主ｱ､繝輔ぅ繝ｫ繧ｿ繝ｼ
- 隍・粋繝輔ぅ繝ｫ繧ｿ繝ｼ
- 譛ｪ蛻・｡槭・繝ｭ繧ｸ繧ｧ繧ｯ繝域紛逅・- 荳諡ｬ繧ｫ繝・ざ繝ｪ螟画峩
- 繧ｫ繝・ざ繝ｪ蛻･Analytics
- AI繧｢繝峨ヰ繧､繧ｶ繝ｼ縺ｸ縺ｮ繧ｫ繝・ざ繝ｪ蜿肴丐

---

# Upload Phase1-3・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
逕滓・貂医∩蜍慕判繧貞・逕滓・縺帙★縲∝ｮ牙・縺ｫYouTube縺ｸPRIVATE繧｢繝・・繝ｭ繝ｼ繝峨〒縺阪ｋ繧医≧縺ｫ縺吶ｋ

## 螳溯｣・
- Job system繧定ｿｽ蜉
- 繝励Ο繧ｸ繧ｧ繧ｯ繝医＃縺ｨ縺ｮ蛻ｶ菴懃憾諷九ｒ `project.json` 縺ｫ豌ｸ邯壼喧
- YouTube upload迥ｶ諷九ｒ蛻ｶ菴懃憾諷九→迢ｬ遶九＠縺ｦ菫晏ｭ・- YouTube Data API v3 / OAuth縺ｫ繧医ｋPRIVATE繧｢繝・・繝ｭ繝ｼ繝・- resumable upload縺ｨretry縺ｫ蟇ｾ蠢・- 驥崎､・い繝・・繝ｭ繝ｼ繝蛾亟豁｢
- Windows Credential Manager繧貞茜逕ｨ縺励◆refresh token菫晏ｭ・- 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨↓譛蟆城剞縺ｮYouTube Upload UI繧定ｿｽ蜉
- `logs/youtube.log` 縺ｮ蟆ら畑繝ｭ繧ｰ繧定ｿｽ蜉

# Phase7 Quality Check（完了）

## 目的

動画生成後から投稿前に、公開してよい状態かを自動検査する品質ゲートを追加する。

## 実装

- Story / text / images / audio / video / publishing の品質検査
- PASS / WARNING / ERROR の判定
- `quality_check.json` への結果保存
- Production Wizard の Quality Check タブ
- YouTube / TikTok アップロード開始前の ERROR ガード
- ffprobe 部分をmock可能にしたテスト

---

# Phase8（完了）
## 逶ｮ逧・

Story AI Provider

## 螳溯｣・

- Story AI Provider interface / Provider Manager
- OpenAI Responses API + Structured Outputs
- `gpt-5.6-luna` default and model presets
- Mock Story Provider for tests
- `story_generation.json` state, retry, resume, cancel
- Candidate Story save and explicit `Use Generated Story`
- Token and cost estimate metrics
- Story Composer minimal AI generation UI

---

# Phase9・井ｺ亥ｮ夲ｼ・

## 逶ｮ逧・

邱ｨ髮・お繝ｳ繧ｸ繝ｳ諡｡蠑ｵ

## 螳溯｣・ｺ亥ｮ・

- browser-use/video-use蟇ｾ蠢・
- VideoEditor諡｡蠑ｵ
- AI邱ｨ髮・お繝ｳ繧ｸ繝ｳ蛻・崛
- 蟆・擂縺ｮ逕ｻ蜒冗函謌舌ヤ繝ｼ繝ｫ蟇ｾ蠢・

---

# Version 1.0・域ｭ｣蠑冗沿・・

## 繧ｴ繝ｼ繝ｫ

繝・・繝槫・蜉・

竊・

ChatGPT

竊・

JSON雋ｼ繧贋ｻ倥￠

竊・

逕ｻ蜒冗函謌・

竊・

VOICEVOX

竊・

BGM

竊・

蟄怜ｹ・

竊・

蜍慕判逕滓・

竊・

繝励Ξ繝薙Η繝ｼ

竊・

謚慕ｨｿ

縺薙・豬√ｌ繧・0蛻・ｻ･蜀・〒螳御ｺ・〒縺阪ｋ縺薙→縲・

---

# Version 2.0・域ｧ区Φ・・

## AI繧ｳ繝ｳ繝・Φ繝・宛菴懊・繝ｩ繝・ヨ繝輔か繝ｼ繝

蟆・擂逧・↓縺ｯ蜍慕判縺縺代〒縺ｪ縺上√さ繝ｳ繝・Φ繝・宛菴懷・菴薙ｒ謾ｯ謠ｴ縺吶ｋ繝励Λ繝・ヨ繝輔か繝ｼ繝縺ｸ逋ｺ螻輔＆縺帙∪縺吶・

### 蟇ｾ蠢應ｺ亥ｮ・

- YouTube Shorts
- TikTok
- Instagram Reels
- X謚慕ｨｿ
- 繝悶Ο繧ｰ險倅ｺ・
- 繧ｵ繝繝阪う繝ｫ逕滓・
- 謚慕ｨｿ蛻・梵
- 謚慕ｨｿ繧ｫ繝ｬ繝ｳ繝繝ｼ
- AI縺ｫ繧医ｋ繝阪ち謠先｡・
- AI縺ｫ繧医ｋ繧ｿ繧､繝医Ν謾ｹ蝟・
- AI縺ｫ繧医ｋ繧ｵ繝繝肴隼蝟・
## Phase6.5 霑ｽ蜉隱ｿ謨ｴ・亥ｮ御ｺ・ｼ・

- Light Effect縺ｮFFmpeg繝輔ぅ繝ｫ繧ｿ繝ｼ讒区枚繧剃ｿｮ豁｣
- 繧､繝ｳ繝医Ο繝ｻ繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ縺ｮ陦ｨ遉ｺ譎る俣繧貞句挨險ｭ螳壼庄閭ｽ縺ｫ螟画峩
- 繧､繝ｳ繝医Ο繝ｻ繧ｨ繝ｳ繝・ぅ繝ｳ繧ｰ縺ｮ繧ｺ繝ｼ繝繧貞句挨險ｭ螳壼庄閭ｽ縺ｫ螟画峩
- 邏譚宣浹螢ｰ縲。GM縲∫ｴ譚宣浹螢ｰ+BGM縲∫┌髻ｳ縺ｨBGM髻ｳ驥上・蛟句挨險ｭ螳壹↓蟇ｾ蠢・

---

---

# Upload Phase4・亥ｮ御ｺ・ｼ・
## 逶ｮ逧・
螳梧・貂医∩縺ｮ `final.mp4` 繧貞・逕滓・縺帙★縲ゝikTok Content Posting API縺ｮUpload Content縺ｧTikTok Inbox縺ｸ螳牙・縺ｫ騾√ｌ繧九ｈ縺・↓縺吶ｋ縲・
## 螳溯｣・
- TikTok OAuth v2 / Desktop Login Kit / PKCE縺ｫ蟇ｾ蠢・- TikTok client secret縺ｨtoken繧淡indows Credential Manager縺ｸ菫晏ｭ・- TikTok Content Posting API Upload Content縺ｫ蟇ｾ蠢・- `final.mp4` 縺ｮ縺ｿ繧探ikTok Inbox縺ｸ繧｢繝・・繝ｭ繝ｼ繝・- TikTok upload迥ｶ諷九ｒ `project.json` 縺ｮ `tiktok_upload` 縺ｫ菫晏ｭ・- `publish_id` 縺ｫ繧医ｋduplicate prevention繧定ｿｽ蜉
- TikTok Status Fetch縺ｫ蟇ｾ蠢・- `SEND_TO_USER_INBOX` 繧偵卦ikTok繧｢繝励Μ縺ｧ謚慕ｨｿ螳御ｺ・′蠢・ｦ√阪→縺励※陦ｨ遉ｺ
- retry縲‘xponential backoff縲∝ｰら畑繝ｭ繧ｰ `logs/tiktok.log` 縺ｫ蟇ｾ蠢・- 蛻ｶ菴懊え繧｣繧ｶ繝ｼ繝峨↓譛蟆城剞縺ｮTikTok Upload UI繧定ｿｽ蜉
