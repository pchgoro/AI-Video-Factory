from __future__ import annotations

from pathlib import Path

from models import AppSettings, ProjectInfo
from services.compilation_service import BrandingSegmentOptions, CompilationService
from services.subtitle_service import SubtitleError, SubtitleService
from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class VideoRenderService:
    """アプリ本体と動画編集エンジンの間に置く薄いサービスです。"""

    def __init__(self, editor: VideoEditor, settings: AppSettings) -> None:
        self.editor = editor
        self.settings = settings
        self.subtitle_service = SubtitleService()
        self.compilation_service = CompilationService(
            ffmpeg_path=settings.ffmpeg_path,
            width=settings.output_width,
            height=settings.output_height,
        )

    def render_project(
        self,
        project: ProjectInfo,
        subtitles_path: Path | None = None,
        generate_subtitles: bool = True,
    ) -> VideoEditResult:
        bgm_path = self._find_bgm_file(self._bgm_dir_for_project(project.path))
        branding_bgm_path = self._first_bgm_file(self._bgm_dir_for_project(project.path))
        intro_path = self._find_intro_file(self._intro_dir_for_project(project.path))
        ending_path = self._find_ending_file(self._ending_dir_for_project(project.path))
        overlay_path = self._find_overlay_file(self._overlay_dir_for_project(project.path))
        needs_branding = intro_path is not None or ending_path is not None
        output_path = project.path / "video" / "final.mp4"
        body_output_path = project.path / "video" / "final_body.mp4"
        if subtitles_path is not None and not subtitles_path.exists():
            subtitles_path = None
        if generate_subtitles and (self.settings.subtitles_enabled or self.settings.title_enabled):
            try:
                subtitles_path = self.subtitle_service.generate_for_project(project.path, self.settings)
            except SubtitleError as exc:
                return VideoEditResult(False, str(exc))

        images_dir = project.path / "images"
        extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        images = []
        if images_dir.exists():
            images = sorted(path for path in images_dir.iterdir() if path.suffix.lower() in extensions and path.is_file())
        image_count = len(images)
        image_motions = self._determine_image_motions(project, image_count, self.settings.motion_style)

        request = VideoEditRequest(
            project_dir=project.path,
            images_dir=images_dir,
            audio_dir=project.path / "audio",
            video_dir=project.path / "video",
            output_path=body_output_path if needs_branding else output_path,
            width=self.settings.output_width,
            height=self.settings.output_height,
            seconds_per_image=self.settings.seconds_per_image,
            zoom_enabled=self.settings.zoom_enabled,
            bgm_path=bgm_path,
            bgm_volume=max(0.0, min(1.0, self.settings.bgm_volume_percent / 100)),
            subtitles_path=subtitles_path,
            image_motions=image_motions,
            zoom_speed=self.settings.zoom_speed,
            transition_type=self.settings.transition_type,
            overlay_path=overlay_path,
            overlay_opacity=self.settings.overlay_opacity,
            light_effect=self.settings.light_effect,
        )
        result = self.editor.render(request)
        if not result.success or not needs_branding:
            return result
        if not request.output_path.exists():
            return VideoEditResult(False, "本編動画の生成に失敗しました。final_body.mp4 が見つかりません。", command=result.command)
        media_paths = [path for path in [intro_path, request.output_path, ending_path] if path is not None]
        segment_options: dict[Path, BrandingSegmentOptions] = {}
        if intro_path is not None:
            segment_options[intro_path] = BrandingSegmentOptions(
                duration=self.settings.intro_duration_seconds,
                motion=self.settings.intro_motion,
                audio_mode=self.settings.intro_audio_mode,
                bgm_volume=max(0.0, min(1.0, self.settings.intro_bgm_volume_percent / 100)),
            )
        if ending_path is not None:
            segment_options[ending_path] = BrandingSegmentOptions(
                duration=self.settings.ending_duration_seconds,
                motion=self.settings.ending_motion,
                audio_mode=self.settings.ending_audio_mode,
                bgm_volume=max(0.0, min(1.0, self.settings.ending_bgm_volume_percent / 100)),
            )
        branded_result = self.compilation_service.concat(
            media_paths,
            output_path,
            segment_options=segment_options,
            bgm_path=branding_bgm_path,
        )
        if branded_result.success:
            return VideoEditResult(True, "video/final.mp4 を生成しました。", branded_result.output_path, branded_result.command)
        return branded_result

    def _find_bgm_file(self, bgm_dir: Path) -> Path | None:
        if not self.settings.bgm_enabled:
            return None
        return self._first_bgm_file(bgm_dir)

    def _first_bgm_file(self, bgm_dir: Path) -> Path | None:
        if not bgm_dir.exists():
            return None
        extensions = {".mp3", ".wav"}
        return next((path for path in sorted(bgm_dir.iterdir()) if path.is_file() and path.suffix.lower() in extensions), None)

    def _find_intro_file(self, intro_dir: Path) -> Path | None:
        if not self.settings.intro_enabled:
            return None
        return self.compilation_service.first_asset(intro_dir)

    def _find_ending_file(self, ending_dir: Path) -> Path | None:
        if not self.settings.ending_enabled:
            return None
        return self.compilation_service.first_asset(ending_dir)

    def _bgm_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "bgm"
        return project_dir.parent / "assets" / "bgm"

    def _intro_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "intro"
        return project_dir.parent / "assets" / "intro"

    def _ending_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "ending"
        return project_dir.parent / "assets" / "ending"

    def _overlay_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "overlay"
        return project_dir.parent / "assets" / "overlay"

    def _find_overlay_file(self, overlay_dir: Path) -> Path | None:
        if not overlay_dir.exists():
            return None
        extensions = {".mp4", ".png", ".jpg", ".jpeg", ".webp"}
        return next((path for path in sorted(overlay_dir.iterdir()) if path.is_file() and path.suffix.lower() in extensions), None)

    def _load_image_prompts(self, project_dir: Path) -> list[str]:
        path = project_dir / "image_prompts.txt"
        if not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []
        blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
        if not blocks:
            blocks = [line.strip() for line in content.splitlines() if line.strip()]
        return blocks

    def _determine_image_motions(self, project: ProjectInfo, image_count: int, motion_style: str) -> list[str]:
        if motion_style == "Static":
            return ["Static"] * image_count
        elif motion_style == "Slow Zoom In":
            return ["Slow Zoom In"] * image_count
        elif motion_style == "Slow Zoom Out":
            return ["Slow Zoom Out"] * image_count
        elif motion_style == "Pan Left":
            return ["Pan Left"] * image_count
        elif motion_style == "Pan Right":
            return ["Pan Right"] * image_count
        elif motion_style == "Pan Up":
            return ["Pan Up"] * image_count
        elif motion_style == "Pan Down":
            return ["Pan Down"] * image_count
        elif motion_style == "Ken Burns":
            return ["Ken Burns"] * image_count
        elif motion_style == "Random Motion":
            import hashlib
            import random
            available_styles = ["Slow Zoom In", "Slow Zoom Out", "Pan Left", "Pan Right", "Pan Up", "Pan Down", "Ken Burns"]
            seed = int(hashlib.sha256(project.name.encode("utf-8")).hexdigest()[:12], 16)
            rng = random.Random(seed)
            prompts = self._load_image_prompts(project.path)
            chosen_styles = []
            last_style = None
            for index in range(image_count):
                scene_style = self._scene_motion_for_prompt(prompts[index] if index < len(prompts) else "", index)
                candidates = [s for s in available_styles if s != last_style]
                if scene_style in candidates and rng.random() < 0.7:
                    style = scene_style
                else:
                    style = rng.choice(candidates)
                chosen_styles.append(style)
                last_style = style
            return chosen_styles
        elif motion_style == "Scene Motion":
            prompts = self._load_image_prompts(project.path)
            motions = []
            for i in range(image_count):
                prompt = prompts[i] if i < len(prompts) else ""
                prompt_lower = prompt.lower()
                if any(k in prompt_lower for k in ["ブラックホール", "black hole", "blackhole", "吸い込まれる"]):
                    motions.append("Slow Zoom In")
                elif any(k in prompt_lower for k in ["宇宙船", "ロケット", "spaceship", "rocket", "船"]):
                    motions.append("Slow Zoom Out")
                elif any(k in prompt_lower for k in ["銀河", "星雲", "宇宙", "galaxy", "nebula", "space", "星", "star"]):
                    # Vary pan style based on index
                    pans = ["Pan Left", "Pan Right", "Pan Up", "Pan Down"]
                    motions.append(pans[i % len(pans)])
                else:
                    # Cyclic fallback
                    defaults = ["Slow Zoom In", "Pan Left", "Slow Zoom Out", "Pan Down", "Ken Burns"]
                    motions.append(defaults[i % len(defaults)])
            return motions
        return ["Random Motion"] * image_count

    def _scene_motion_for_prompt(self, prompt: str, index: int) -> str:
        prompt_lower = prompt.lower()
        if any(k in prompt_lower for k in ["ブラックホール", "black hole", "blackhole", "吸い込まれる"]):
            return "Slow Zoom In"
        if any(k in prompt_lower for k in ["宇宙船", "ロケット", "spaceship", "rocket", "船"]):
            return "Slow Zoom Out"
        if any(k in prompt_lower for k in ["銀河", "星雲", "宇宙", "galaxy", "nebula", "space", "星", "star"]):
            pans = ["Pan Left", "Pan Right", "Pan Up", "Pan Down"]
            return pans[index % len(pans)]
        defaults = ["Slow Zoom In", "Pan Left", "Slow Zoom Out", "Pan Down", "Ken Burns"]
        return defaults[index % len(defaults)]
