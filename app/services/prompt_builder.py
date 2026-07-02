from __future__ import annotations

import json

from models import PromptTemplate


def build_chatgpt_prompt(
    topic: str,
    duration: str,
    genre: str,
    image_count: int,
    template: PromptTemplate | None = None,
) -> str:
    """ChatGPTへ手動貼り付けするJSON出力専用プロンプトを生成します。"""
    style = template.style if template else "知的で引き込まれるショート動画ドキュメンタリー"
    angle = template.angle if template else "中学生にも分かる説明で、最後まで見たくなる構成"
    image_style = template.image_style if template else "cinematic documentary style, 4K look, highly detailed"
    schema = {
        "title": "",
        "script": "",
        "voice_text": "",
        "image_prompts": ["" for _ in range(image_count)],
        "subtitles": [{"start": 0.0, "end": 2.8, "text": ""}],
        "hashtags": [""],
    }

    return f"""あなたはTikTok / YouTube Shorts向けの短尺動画構成作家です。
次の条件で、ショート動画制作に使う素材を作成してください。

【テーマ】
{topic}

【動画条件】
- 動画時間：{duration}
- ジャンル：{genre}
- 顔出しなし
- TikTok / YouTube Shorts向け
- 縦動画
- 日本語ナレーション
- 中学生にも分かる説明
- 動画時間に応じて script の長さを調整する
- voice_text は実際に読み上げるナレーション全文にする
- 文体：{style}
- 構成方針：{angle}

【画像プロンプト条件】
- image_prompts は必ず {image_count} 個
- 画像プロンプトは英語
- 画像比率は 9:16
- 画像内に文字、字幕、ロゴ、透かしを入れない
- {image_style}

【出力ルール】
- JSON以外の説明文を一切出さない
- Markdownのコードブロックも使わない
- 必ず次のキーを持つJSONだけを返す
- script と voice_text は同じ内容にする
- subtitles は voice_text で実際に読み上げる文章を、時刻ごとに短く区切ったものにする
- subtitles の text はナレーションに無い別文、要約、補足説明にしない
- subtitles は start / end / text を持つ配列にする
- subtitles の start と end は `"0:00"` のような文字列ではなく、必ず 0.0 や 2.8 のような秒数の数値にする
- 1字幕は1〜2行程度、表示時間は約2〜4秒、スマホ縦動画で読みやすい短い文にする
- subtitles 全体を順番につなげると voice_text とほぼ同じ本文になるようにする
- hashtags は文字列配列にする

【JSON形式】
{json.dumps(schema, ensure_ascii=False, indent=2)}
"""
