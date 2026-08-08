from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DURATIONS = ["30秒", "60秒", "90秒", "3分"]
DEFAULT_GENRES = ["宇宙", "株", "AIニュース", "歴史", "猫", "偉人"]
DEFAULT_TOPICS = ["ブラックホール", "ホワイトホール", "ダークマター", "量子もつれ", "AIエージェント", "半導体", "保護猫"]
PROGRESS_ITEMS = ["台本", "画像", "音声", "字幕", "動画", "投稿"]
WIZARD_STEPS = ["テーマ入力", "ChatGPT", "回答解析", "画像", "音声", "動画", "投稿"]
JOB_STATUSES = {
    "draft",
    "script_ready",
    "images_ready",
    "audio_ready",
    "video_ready",
    "youtube_uploaded",
    "failed",
}



@dataclass
class AppSettings:
    default_duration: str = "90秒"
    default_image_count: int = 5
    save_dir: str = ""
    genres: list[str] = field(default_factory=lambda: DEFAULT_GENRES.copy())
    video_editor_engine: str = "ffmpeg"
    voicevox_url: str = "http://127.0.0.1:50021"
    voicevox_speaker_id: int = 3
    ffmpeg_path: str = "ffmpeg"
    output_width: int = 1080
    output_height: int = 1920
    seconds_per_image: int = 5
    zoom_enabled: bool = True
    bgm_enabled: bool = True
    bgm_volume_percent: int = 20
    intro_enabled: bool = False
    ending_enabled: bool = False
    intro_duration_seconds: int = 3
    ending_duration_seconds: int = 3
    intro_motion: str = "Slow Zoom In"
    ending_motion: str = "Slow Zoom Out"
    intro_audio_mode: str = "Original"
    ending_audio_mode: str = "Original"
    intro_bgm_volume_percent: int = 20
    ending_bgm_volume_percent: int = 20
    subtitles_enabled: bool = True
    subtitle_font_size: int = 64
    subtitle_position: str = "下"
    subtitle_outline: int = 4
    subtitle_shadow_enabled: bool = True
    title_enabled: bool = False
    title_size: int = 72
    title_position: str = "上"
    title_bg_enabled: bool = True
    title_duration: str = "常に表示"
    title_preset: str = "宇宙ドキュメンタリー風"
    title_highlight_enabled: bool = True
    title_bg_opacity: int = 50
    title_padding: int = 15
    title_width_percent: int = 90
    title_line_spacing: int = 10
    motion_style: str = "Random Motion"
    zoom_speed: str = "Normal"
    transition_type: str = "Cross Fade"
    overlay_opacity: int = 30
    light_effect: str = "OFF"
    image_generation_provider: str = "cloudflare_workers_ai"
    image_generation_model: str = "@cf/black-forest-labs/flux-1-schnell"
    image_generation_steps: int = 4
    image_generation_max_images_per_run: int = 8
    image_generation_max_retries_per_image: int = 2
    image_generation_daily_request_limit: int = 20
    image_generation_project_limit: int = 40
    image_prompt_optimizer_enabled: bool = True
    image_prompt_template_mode: str = "auto"
    image_manual_prompt_template: str = "generic_space"
    default_story_provider: str = "gemini"
    default_story_model: str = "gemini-3.5-flash-lite"
    default_reasoning_effort: str = "low"
    default_max_output_tokens: int = 4096
    story_provider_retry_count: int = 2
    story_provider_timeout_seconds: int = 60
    default_gemini_model: str = "gemini-3.5-flash-lite"
    gemini_free_tier_only: bool = True
    gemini_project_free_tier_confirmed: bool = False
    gemini_project_free_tier_confirmed_at: str = ""
    gemini_billing_disabled_confirmed: bool = False
    gemini_billing_disabled_confirmed_at: str = ""
    gemini_confirmation_key_fingerprint: str = ""
    gemini_confirmation_version: str = "1.0"
    gemini_local_daily_request_cap: int = 10
    gemini_retry_count: int = 2
    gemini_timeout_seconds: int = 60
    gemini_temperature: float = 0.7
    gemini_max_output_tokens: int = 4096
    youtube_add_to_category_playlist: bool = True
    youtube_create_playlist_if_missing: bool = True
    youtube_playlist_privacy_status: str = "private"
    youtube_voicevox_credit_enabled: bool = True
    youtube_ai_disclosure_enabled: bool = True
    youtube_category_id: str = "28"
    image_common_conditions: str = "・9:16\n・4K\n・文字なし\n・リアル\n・映画風\n・ドキュメンタリー風"



@dataclass
class PromptTemplate:
    name: str
    genre: str
    style: str
    angle: str
    image_style: str


@dataclass
class ProjectInfo:
    name: str
    path: Path
    topic: str = ""
    title: str = ""
    genre: str = ""
    category: str = ""
    duration: str = ""
    image_count: int = 5
    template_name: str = ""
    series: str = ""
    series_number: int = 1
    tags: list[str] = field(default_factory=list)
    youtube_tags: list[str] = field(default_factory=list)
    tiktok_tags: list[str] = field(default_factory=list)
    posted_date: str = ""
    created_at: str = ""
    updated_at: str = ""
    content_source: str = ""
    content_exported_at: str = ""
    progress: dict[str, bool] = field(default_factory=dict)
    analytics_views: int = 0
    analytics_rating: int = 0
    csv_posted: bool = False
    job: dict[str, object] = field(default_factory=dict)
    youtube_upload: dict[str, object] = field(default_factory=dict)
    tiktok_upload: dict[str, object] = field(default_factory=dict)
    image_generation: dict[str, object] = field(default_factory=dict)


@dataclass
class ParsedChatGptAnswer:
    title: str = ""
    script: str = ""
    voice_text: str = ""
    image_prompts: list[str] = field(default_factory=list)
    subtitles: str = ""
    hashtags: str = ""

    @property
    def narration(self) -> str:
        """旧コード互換用。Phase4では script を正とします。"""
        return self.script


@dataclass
class DashboardStats:
    today_count: int = 0
    in_progress_count: int = 0
    completed_count: int = 0
    posted_count: int = 0
    total_videos: int = 0
    total_projects: int = 0
    genre_counts: dict[str, int] = field(default_factory=dict)
    recent_projects: list[ProjectInfo] = field(default_factory=list)
