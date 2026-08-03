from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from models import ProjectInfo
from services.project_service import ProjectService

from .models import Story


FACTORY_EXPORT_FILES = [
    "title.txt",
    "script.txt",
    "voice.txt",
    "image_prompts.txt",
    "subtitles.txt",
    "hashtags.txt",
    "memo.txt",
]


@dataclass
class FactoryExportPreview:
    title: str
    narration: str
    subtitles: str
    image_prompts: str
    hashtags: str
    memo: str
    subtitle_count: int
    image_prompt_count: int
    target_files: list[str]
    existing_files: list[str]
    new_files: list[str]


@dataclass
class FactoryExportResult:
    exported_at: str
    backup_dir: Path
    files: list[str] = field(default_factory=list)


class StoryFactoryAdapter:
    def __init__(self, project_service: ProjectService) -> None:
        self.project_service = project_service

    def preview(self, project: ProjectInfo, story: Story) -> FactoryExportPreview:
        values = self._build_file_values(story)
        existing = [name for name in FACTORY_EXPORT_FILES if (project.path / name).exists()]
        new = [name for name in FACTORY_EXPORT_FILES if not (project.path / name).exists()]
        return FactoryExportPreview(
            title=values["title.txt"].strip(),
            narration=values["voice.txt"].strip(),
            subtitles=values["subtitles.txt"].strip(),
            image_prompts=values["image_prompts.txt"].strip(),
            hashtags=values["hashtags.txt"].strip(),
            memo=values["memo.txt"].strip(),
            subtitle_count=len(story.scenes),
            image_prompt_count=len([scene for scene in story.scenes if scene.image_prompt.strip()]),
            target_files=FACTORY_EXPORT_FILES.copy(),
            existing_files=existing,
            new_files=new,
        )

    def export(self, project: ProjectInfo, story: Story) -> FactoryExportResult:
        values = self._build_file_values(story)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = project.path / "backups" / f"story_export_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        try:
            metadata_path = project.path / "project.json"
            if metadata_path.exists():
                shutil.copy2(metadata_path, backup_dir / "project.json")
            for name in FACTORY_EXPORT_FILES:
                target = project.path / name
                if target.exists():
                    shutil.copy2(target, backup_dir / name)
            for name, text in values.items():
                target = project.path / name
                self._atomic_write(target, text)
                written.append(target)
            exported_at = datetime.now().isoformat(timespec="seconds")
            image_prompts = [scene.image_prompt.strip() for scene in sorted(story.scenes, key=lambda item: item.scene_index)]
            updates = {
                "title": story.title,
                "topic": story.title or project.topic,
                "image_count": len(image_prompts) or project.image_count,
                "content_source": "story_composer",
                "content_exported_at": exported_at,
            }
            self.project_service.update_metadata(project.path, updates)
        except Exception:
            for path in written:
                backup = backup_dir / path.name
                if backup.exists():
                    shutil.copy2(backup, path)
                else:
                    path.unlink(missing_ok=True)
            metadata_backup = backup_dir / "project.json"
            if metadata_backup.exists():
                shutil.copy2(metadata_backup, project.path / "project.json")
            raise
        return FactoryExportResult(
            exported_at=exported_at,
            backup_dir=backup_dir,
            files=FACTORY_EXPORT_FILES.copy(),
        )

    def _build_file_values(self, story: Story) -> dict[str, str]:
        scenes = sorted(story.scenes, key=lambda item: item.scene_index)
        narration = "\n".join(scene.narration.strip() for scene in scenes if scene.narration.strip())
        image_prompts = "\n\n".join(scene.image_prompt.strip() for scene in scenes if scene.image_prompt.strip())
        subtitles = [
            {
                "start": float(scene.start_time),
                "end": float(scene.end_time),
                "text": scene.subtitle.strip() or scene.narration.strip(),
            }
            for scene in scenes
        ]
        hashtags = " ".join(tag if tag.startswith("#") else f"#{tag}" for tag in story.tags if tag.strip())
        memo_lines = ["Story Composer memo:", story.memo.strip(), "", "Scene notes:"]
        for scene in scenes:
            if scene.notes.strip():
                memo_lines.append(f"{scene.scene_index}. {scene.notes.strip()}")
        return {
            "title.txt": story.title.strip() + "\n",
            "script.txt": narration + "\n",
            "voice.txt": narration + "\n",
            "image_prompts.txt": image_prompts + "\n",
            "subtitles.txt": json.dumps(subtitles, ensure_ascii=False, indent=2) + "\n",
            "hashtags.txt": hashtags + "\n",
            "memo.txt": "\n".join(memo_lines).strip() + "\n",
        }

    def _atomic_write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
        tmp.replace(path)
