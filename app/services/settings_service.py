from __future__ import annotations

import json

from config import AppPaths
from models import AppSettings, DEFAULT_GENRES


class SettingsService:
    """settings.jsonの読み書きを担当します。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> AppSettings:
        path = self.paths.settings_path
        if not path.exists():
            return AppSettings(save_dir=str(self.paths.base_dir), genres=DEFAULT_GENRES.copy())

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings(save_dir=str(self.paths.base_dir), genres=DEFAULT_GENRES.copy())

        return AppSettings(
            default_duration=data.get("default_duration", "90秒"),
            default_image_count=int(data.get("default_image_count", 5)),
            save_dir=data.get("save_dir") or str(self.paths.base_dir),
            genres=data.get("genres") or DEFAULT_GENRES.copy(),
            video_editor_engine=data.get("video_editor_engine", "ffmpeg"),
            voicevox_url=data.get("voicevox_url", "http://127.0.0.1:50021"),
            voicevox_speaker_id=int(data.get("voicevox_speaker_id", 3)),
            ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
            output_width=int(data.get("output_width", 1080)),
            output_height=int(data.get("output_height", 1920)),
            seconds_per_image=int(data.get("seconds_per_image", 5)),
            zoom_enabled=bool(data.get("zoom_enabled", True)),
            bgm_enabled=bool(data.get("bgm_enabled", True)),
            bgm_volume_percent=int(data.get("bgm_volume_percent", 20)),
            intro_enabled=bool(data.get("intro_enabled", False)),
            ending_enabled=bool(data.get("ending_enabled", False)),
            intro_duration_seconds=int(data.get("intro_duration_seconds", 3)),
            ending_duration_seconds=int(data.get("ending_duration_seconds", 3)),
            intro_motion=data.get("intro_motion", "Slow Zoom In"),
            ending_motion=data.get("ending_motion", "Slow Zoom Out"),
            intro_audio_mode=data.get("intro_audio_mode", "Original"),
            ending_audio_mode=data.get("ending_audio_mode", "Original"),
            intro_bgm_volume_percent=int(data.get("intro_bgm_volume_percent", 20)),
            ending_bgm_volume_percent=int(data.get("ending_bgm_volume_percent", 20)),
            subtitles_enabled=bool(data.get("subtitles_enabled", True)),
            subtitle_font_size=int(data.get("subtitle_font_size", 64)),
            subtitle_position=data.get("subtitle_position", "下"),
            subtitle_outline=int(data.get("subtitle_outline", 4)),
            subtitle_shadow_enabled=bool(data.get("subtitle_shadow_enabled", True)),
            title_enabled=bool(data.get("title_enabled", False)),
            title_size=int(data.get("title_size", 72)),
            title_position=data.get("title_position", "上"),
            title_bg_enabled=bool(data.get("title_bg_enabled", True)),
            title_duration=data.get("title_duration", "常に表示"),
            title_preset=data.get("title_preset", "宇宙ドキュメンタリー風"),
            title_highlight_enabled=bool(data.get("title_highlight_enabled", True)),
            title_bg_opacity=int(data.get("title_bg_opacity", 50)),
            title_padding=int(data.get("title_padding", 15)),
            title_width_percent=int(data.get("title_width_percent", 90)),
            title_line_spacing=int(data.get("title_line_spacing", 10)),
            motion_style=data.get("motion_style", "Random Motion"),
            zoom_speed=data.get("zoom_speed", "Normal"),
            transition_type=data.get("transition_type", "Cross Fade"),
            overlay_opacity=int(data.get("overlay_opacity", 30)),
            light_effect=data.get("light_effect", "OFF"),
            image_generation_provider=data.get("image_generation_provider", "cloudflare_workers_ai"),
            image_generation_model=data.get("image_generation_model", "@cf/black-forest-labs/flux-1-schnell"),
            image_generation_steps=int(data.get("image_generation_steps", 4)),
            image_generation_max_images_per_run=int(data.get("image_generation_max_images_per_run", 8)),
            image_generation_max_retries_per_image=int(data.get("image_generation_max_retries_per_image", 2)),
            image_generation_daily_request_limit=int(data.get("image_generation_daily_request_limit", 20)),
            image_generation_project_limit=int(data.get("image_generation_project_limit", 40)),
            image_prompt_optimizer_enabled=bool(data.get("image_prompt_optimizer_enabled", True)),
            image_prompt_template_mode=str(data.get("image_prompt_template_mode", "auto")),
            image_manual_prompt_template=str(data.get("image_manual_prompt_template", "generic_space")),
            default_story_provider=str(data.get("default_story_provider", "gemini")),
            default_story_model=str(data.get("default_story_model", "gemini-3.5-flash-lite")),
            default_reasoning_effort=str(data.get("default_reasoning_effort", "low")),
            default_max_output_tokens=int(data.get("default_max_output_tokens", 4096)),
            story_provider_retry_count=int(data.get("story_provider_retry_count", 2)),
            story_provider_timeout_seconds=int(data.get("story_provider_timeout_seconds", 60)),
            default_gemini_model=str(data.get("default_gemini_model", "gemini-3.5-flash-lite")),
            gemini_free_tier_only=bool(data.get("gemini_free_tier_only", True)),
            gemini_project_free_tier_confirmed=bool(data.get("gemini_project_free_tier_confirmed", False)),
            gemini_project_free_tier_confirmed_at=str(data.get("gemini_project_free_tier_confirmed_at", "")),
            gemini_billing_disabled_confirmed=bool(data.get("gemini_billing_disabled_confirmed", False)),
            gemini_billing_disabled_confirmed_at=str(data.get("gemini_billing_disabled_confirmed_at", "")),
            gemini_confirmation_key_fingerprint=str(data.get("gemini_confirmation_key_fingerprint", "")),
            gemini_confirmation_version=str(data.get("gemini_confirmation_version", "1.0")),
            gemini_local_daily_request_cap=int(data.get("gemini_local_daily_request_cap", 10)),
            gemini_retry_count=int(data.get("gemini_retry_count", 2)),
            gemini_timeout_seconds=int(data.get("gemini_timeout_seconds", 60)),
            gemini_temperature=float(data.get("gemini_temperature", 0.7)),
            gemini_max_output_tokens=int(data.get("gemini_max_output_tokens", 4096)),
            image_common_conditions=data.get(
                "image_common_conditions",
                "・9:16\n・4K\n・文字なし\n・リアル\n・映画風\n・ドキュメンタリー風",
            ),
        )

    def save(self, settings: AppSettings) -> None:
        self.paths.settings_path.write_text(
            json.dumps(settings.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
