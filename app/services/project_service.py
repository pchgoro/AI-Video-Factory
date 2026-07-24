from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from config import AppPaths
from models import ParsedChatGptAnswer, ProjectInfo


PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class ProjectService:
    """プロジェクトの作成、検索用メタデータ、素材ファイル保存を担当します。"""

    IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.logger = logging.getLogger("ai_video_factory")

    def list_projects(self) -> list[ProjectInfo]:
        self.paths.projects_dir.mkdir(parents=True, exist_ok=True)
        projects = [self.load_project(path) for path in self.paths.projects_dir.iterdir() if path.is_dir()]
        return sorted(projects, key=lambda item: item.updated_at or item.created_at or item.name, reverse=True)

    def create_project(
        self,
        topic: str,
        genre: str,
        duration: str,
        image_count: int,
        prompt: str,
        template_name: str = "",
        tags: list[str] | None = None,
        series: str | None = None,
        category: str = "",
    ) -> ProjectInfo:
        series_name = (series or topic).strip()
        series_number = self.next_series_number(series_name)
        folder_name = self._next_project_folder_name(series_name, series_number)
        project_dir = self.paths.projects_dir / folder_name
        project_dir.mkdir(parents=True, exist_ok=False)
        for sub_dir in ["images", "audio", "video", "thumbnail"]:
            (project_dir / sub_dir).mkdir(exist_ok=True)

        now = self._now()
        metadata = {
            "topic": topic,
            "title": "",
            "genre": genre,
            "category": category,
            "duration": duration,
            "image_count": image_count,
            "template_name": template_name,
            "series": series_name,
            "series_number": series_number,
            "tags": tags or [],
            "youtube_tags": tags or [],
            "tiktok_tags": [],
            "posted_date": "",
            "created_at": now,
            "updated_at": now,
        }
        self._write_metadata(project_dir, metadata)
        self.save_texts(
            project_dir,
            {
                "topic.txt": f"{topic}\n",
                "chatgpt_prompt.txt": prompt + "\n",
                "raw_chatgpt.txt": "",
                "title.txt": "",
                "script.txt": "",
                "image_prompts.txt": "",
                "voice.txt": "",
                "subtitles.txt": "",
                "hashtags.txt": "",
                "memo.txt": "制作メモ:\n",
            },
            touch_metadata=False,
        )
        self.logger.info("プロジェクト作成: %s", project_dir)
        return self.load_project(project_dir)

    def delete_project(self, project: ProjectInfo) -> None:
        """指定プロジェクトのフォルダを削除します。呼び出し側で確認を済ませてから使います。"""
        if not project.path.exists():
            return
        if project.path.parent.resolve() != self.paths.projects_dir.resolve():
            raise ValueError("projectsフォルダ外のプロジェクトは削除できません。")
        shutil.rmtree(project.path)
        self.logger.info("プロジェクト削除: %s", project.path)

    def create_projects_from_topics(
        self,
        topics: list[str],
        genre: str,
        category: str,
        duration: str,
        image_count: int,
        template_name: str,
        prompt_builder,
        tags: list[str] | None = None,
    ) -> list[ProjectInfo]:
        projects = []
        for topic in topics:
            prompt = prompt_builder(topic)
            projects.append(self.create_project(topic, genre, duration, image_count, prompt, template_name, tags, topic, category))
        return projects

    def load_project(self, path: Path) -> ProjectInfo:
        metadata = self._read_metadata(path)
        info = ProjectInfo(
            name=path.name,
            path=path,
            topic=str(metadata.get("topic") or self._read_text(path / "topic.txt").strip()),
            title=str(metadata.get("title") or self._read_text(path / "title.txt").strip()),
            genre=str(metadata.get("genre", "")),
            category=str(metadata.get("category", "")),
            duration=str(metadata.get("duration", "")),
            image_count=int(metadata.get("image_count", 5)),
            template_name=str(metadata.get("template_name", "")),
            series=str(metadata.get("series", "")),
            series_number=int(metadata.get("series_number", 1)),
            tags=list(metadata.get("tags", [])) if isinstance(metadata.get("tags", []), list) else [],
            youtube_tags=list(metadata.get("youtube_tags", metadata.get("tags", []))) if isinstance(metadata.get("youtube_tags", metadata.get("tags", [])), list) else [],
            tiktok_tags=list(metadata.get("tiktok_tags", [])) if isinstance(metadata.get("tiktok_tags", []), list) else [],
            posted_date=str(metadata.get("posted_date", "")),
            created_at=str(metadata.get("created_at", "")),
            updated_at=str(metadata.get("updated_at", "")),
        )
        info.progress = self.detect_progress(path, info.image_count)
        analytics = metadata.get("analytics", {})
        if isinstance(analytics, dict):
            records = [value for value in analytics.values() if isinstance(value, dict)]
            info.analytics_views = max([int(value.get("views", 0) or 0) for value in records], default=0)
            info.analytics_rating = int(metadata.get("analytics_rating", 0) or 0)
        posting_status = metadata.get("posting_status", {})
        info.csv_posted = bool(isinstance(posting_status, dict) and posting_status.get("csv_confirmed"))
        return info

    def save_chatgpt_import(self, project: ProjectInfo, raw_text: str, parsed: ParsedChatGptAnswer) -> None:
        title = parsed.title.strip()
        self.save_texts(
            project.path,
            {
                "raw_chatgpt.txt": raw_text.strip() + "\n",
                "topic.txt": (title or project.topic).strip() + "\n",
                "title.txt": title + "\n",
                "script.txt": parsed.script.strip() + "\n",
                "voice.txt": (parsed.voice_text or parsed.script).strip() + "\n",
                "image_prompts.txt": "\n\n".join(parsed.image_prompts).strip() + "\n",
                "subtitles.txt": parsed.subtitles.strip() + "\n",
                "hashtags.txt": parsed.hashtags.strip() + "\n",
            },
        )
        metadata_updates: dict[str, object] = {"title": title, "image_count": len(parsed.image_prompts) or project.image_count}
        if title:
            metadata_updates["topic"] = title
        self.update_metadata(project.path, metadata_updates)
        self.logger.info("ChatGPT回答保存: %s", project.path)

    def save_preview_files(self, project: ProjectInfo, values: dict[str, str]) -> None:
        self.save_texts(project.path, values)

    def save_tags(self, project: ProjectInfo, tags: list[str]) -> ProjectInfo:
        self.update_metadata(project.path, {"tags": tags, "youtube_tags": tags})
        return self.load_project(project.path)

    def save_platform_tags(
        self,
        project: ProjectInfo,
        youtube_tags: list[str] | None = None,
        tiktok_tags: list[str] | None = None,
    ) -> ProjectInfo:
        updates: dict[str, object] = {}
        if youtube_tags is not None:
            updates["youtube_tags"] = youtube_tags
            updates["tags"] = youtube_tags
        if tiktok_tags is not None:
            updates["tiktok_tags"] = tiktok_tags
        self.update_metadata(project.path, updates)
        return self.load_project(project.path)

    def save_topic(self, project: ProjectInfo, topic: str) -> ProjectInfo:
        clean_topic = topic.strip()
        if not clean_topic:
            raise ValueError("テーマを入力してください。")
        self.save_texts(project.path, {"topic.txt": clean_topic + "\n"}, touch_metadata=False)
        self.update_metadata(project.path, {"topic": clean_topic})
        return self.load_project(project.path)

    def update_project_classification(
        self,
        project: ProjectInfo,
        genre: str | None = None,
        category: str | None = None,
        series: str | None = None,
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> ProjectInfo:
        updates: dict[str, object] = {}
        if genre is not None:
            updates["genre"] = genre
        if category is not None:
            updates["category"] = category
        if series is not None:
            updates["series"] = series
        tags = list(project.tags)
        for tag in add_tags or []:
            clean = tag.strip().lstrip("#")
            if clean and clean not in tags:
                tags.append(clean)
        remove_set = {tag.strip().lstrip("#") for tag in remove_tags or [] if tag.strip()}
        if remove_set:
            tags = [tag for tag in tags if tag.strip().lstrip("#") not in remove_set]
        if add_tags or remove_tags:
            updates["tags"] = tags
            updates["youtube_tags"] = tags
        self.update_metadata(project.path, updates)
        return self.load_project(project.path)

    def bulk_update_classification(
        self,
        projects: list[ProjectInfo],
        genre: str = "",
        category: str = "",
        series: str = "",
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> list[ProjectInfo]:
        updated = []
        for project in projects:
            updated.append(
                self.update_project_classification(
                    project,
                    genre=genre or None,
                    category=category or None,
                    series=series or None,
                    add_tags=add_tags,
                    remove_tags=remove_tags,
                )
            )
        return updated

    def save_texts(self, project_dir: Path, values: dict[str, str], touch_metadata: bool = True) -> None:
        project_dir.mkdir(parents=True, exist_ok=True)
        for file_name, text in values.items():
            (project_dir / file_name).write_text(text, encoding="utf-8")
        if touch_metadata:
            self.update_metadata(project_dir, {})

    def update_metadata(self, project_dir: Path, updates: dict[str, object]) -> None:
        metadata = self._read_metadata(project_dir)
        metadata.update(updates)
        metadata["updated_at"] = self._now()
        self._write_metadata(project_dir, metadata)

    def detect_progress(self, path: Path, image_count: int | None = None) -> dict[str, bool]:
        expected_images = image_count or int(self._read_metadata(path).get("image_count", 3) or 3)
        return {
            "台本": bool(self._read_text(path / "script.txt").strip()),
            "画像": self.generated_image_count(path / "images", expected_images) >= expected_images,
            "音声": (path / "audio" / "voice.wav").exists(),
            "字幕": (path / "video" / "subtitles.ass").exists(),
            "動画": (path / "video" / "final.mp4").exists(),
            "投稿": (path / "posted.txt").exists(),
        }

    def image_prompt_items(self, project: ProjectInfo) -> list[tuple[int, str, bool]]:
        prompts = [block.strip() for block in re.split(r"\n\s*\n", self._read_text(project.path / "image_prompts.txt")) if block.strip()]
        if not prompts:
            prompts = [line.strip() for line in self._read_text(project.path / "image_prompts.txt").splitlines() if line.strip()]
        count = max(project.image_count, len(prompts), 3)
        items = []
        for index in range(1, count + 1):
            prompt = prompts[index - 1] if index - 1 < len(prompts) else ""
            items.append((index, prompt, self.is_image_generated(project.path / "images", index)))
        return items

    def asset_statuses(self, project: ProjectInfo) -> list[tuple[str, str, Path]]:
        items: list[tuple[str, str, Path]] = []
        for index, _prompt, generated in self.image_prompt_items(project):
            items.append((f"画像{index}", "生成済" if generated else "未生成", project.path / "images"))
        items.append(("音声", "生成済" if (project.path / "audio" / "voice.wav").exists() else "未生成", project.path / "audio"))
        subtitle_status = "生成済" if (project.path / "video" / "subtitles.ass").exists() else "未生成"
        if (project.path / "video" / "final.mp4").exists() and (project.path / "video" / "subtitles.ass").exists():
            subtitle_status = "焼き込み済み"
        items.append(("字幕", subtitle_status, project.path / "video"))
        items.append(("動画", "生成済" if (project.path / "video" / "final.mp4").exists() else "未生成", project.path / "video"))
        return items

    def mark_image_generated(self, project: ProjectInfo, index: int) -> Path:
        images_dir = project.path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        image_path = images_dir / f"{index:03d}.png"
        if not image_path.exists():
            image_path.write_bytes(PLACEHOLDER_PNG)
        return image_path

    def generated_image_count(self, images_dir: Path, expected_count: int) -> int:
        return sum(1 for index in range(1, expected_count + 1) if self.is_image_generated(images_dir, index))

    def is_image_generated(self, images_dir: Path, index: int) -> bool:
        stem = f"{index:03d}"
        return any((images_dir / f"{stem}{extension}").exists() for extension in self.IMAGE_EXTENSIONS)

    def open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def next_series_number(self, series: str) -> int:
        numbers = []
        for project in self.list_projects():
            if project.series == series:
                numbers.append(project.series_number)
        return max(numbers, default=0) + 1

    def _next_project_folder_name(self, series: str, series_number: int) -> str:
        date_text = datetime.now().strftime("%Y-%m-%d")
        slug = self._make_slug(series)
        base_name = f"{date_text}_{slug}{series_number:03d}"
        candidate = base_name
        suffix = 2
        while (self.paths.projects_dir / candidate).exists():
            candidate = f"{base_name}_{suffix}"
            suffix += 1
        return candidate

    def _make_slug(self, topic: str) -> str:
        normalized = unicodedata.normalize("NFKC", topic).strip().lower()
        ascii_slug = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_slug).strip("_")
        if slug:
            return slug[:40]
        compact = re.sub(r"\s+", "", normalized)
        safe = re.sub(r'[<>:"/\\|?*]+', "", compact)
        return (safe or "project")[:24]

    def _read_metadata(self, path: Path) -> dict[str, object]:
        metadata_path = path / "project.json"
        if not metadata_path.exists():
            return {}
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_metadata(self, project_dir: Path, metadata: dict[str, object]) -> None:
        (project_dir / "project.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
