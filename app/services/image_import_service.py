from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage


class ImageImportError(Exception):
    """画像取り込みでユーザーへ表示する日本語エラーです。"""


@dataclass(frozen=True)
class ImportedImage:
    path: Path
    index: int


class ImageImportService:
    """画像をPNGへ変換し、001.png形式で保存・並び替えします。"""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def import_files(self, project_dir: Path, files: list[Path], mode: str = "add") -> list[ImportedImage]:
        if not files:
            return []
        images_dir = self._images_dir(project_dir)
        images_dir.mkdir(parents=True, exist_ok=True)
        source_paths = [Path(path) for path in files]
        for path in source_paths:
            self._validate_source(path)

        if mode == "overwrite":
            self._clear_images(images_dir)
            start_index = 1
        elif mode == "add":
            start_index = self.next_index(images_dir)
        else:
            raise ImageImportError("画像取り込み方法が正しくありません。")

        imported: list[ImportedImage] = []
        for offset, source_path in enumerate(source_paths):
            target_index = start_index + offset
            target_path = images_dir / f"{target_index:03d}.png"
            self._save_as_png(source_path, target_path)
            imported.append(ImportedImage(target_path, target_index))
        return imported

    def import_qimage(self, project_dir: Path, image: QImage, mode: str = "add") -> ImportedImage:
        if image.isNull():
            raise ImageImportError("クリップボードに画像がありません。")
        images_dir = self._images_dir(project_dir)
        images_dir.mkdir(parents=True, exist_ok=True)
        if mode == "overwrite":
            self._clear_images(images_dir)
            index = 1
        elif mode == "add":
            index = self.next_index(images_dir)
        else:
            raise ImageImportError("画像取り込み方法が正しくありません。")
        target_path = images_dir / f"{index:03d}.png"
        if not image.save(str(target_path), "PNG"):
            raise ImageImportError("画像の保存に失敗しました。")
        return ImportedImage(target_path, index)

    def list_images(self, project_dir: Path) -> list[Path]:
        images_dir = self._images_dir(project_dir)
        if not images_dir.exists():
            return []
        return sorted(path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png")

    def has_images(self, project_dir: Path) -> bool:
        return bool(self.list_images(project_dir))

    def next_index(self, images_dir: Path) -> int:
        indexes = [self._image_index(path) for path in self.list_images(images_dir.parent)]
        return max([index for index in indexes if index is not None], default=0) + 1

    def delete_image(self, image_path: Path) -> None:
        if not image_path.exists():
            return
        image_path.unlink()
        self.renumber_images(image_path.parent)

    def move_image(self, image_path: Path, direction: int) -> None:
        images = self.list_images(image_path.parent.parent)
        try:
            current_index = images.index(image_path)
        except ValueError:
            return
        new_index = current_index + direction
        if new_index < 0 or new_index >= len(images):
            return
        images[current_index], images[new_index] = images[new_index], images[current_index]
        self.rewrite_order(images)

    def renumber_images(self, images_dir: Path) -> None:
        if not images_dir.exists():
            return
        self.rewrite_order(sorted(path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png"))

    def rewrite_order(self, ordered_paths: list[Path]) -> list[Path]:
        if not ordered_paths:
            return []
        images_dir = ordered_paths[0].parent
        temp_paths: list[Path] = []
        for index, path in enumerate(ordered_paths, start=1):
            temp_path = images_dir / f".__image_import_tmp_{index:03d}.png"
            path.replace(temp_path)
            temp_paths.append(temp_path)
        final_paths: list[Path] = []
        for index, temp_path in enumerate(temp_paths, start=1):
            final_path = images_dir / f"{index:03d}.png"
            temp_path.replace(final_path)
            final_paths.append(final_path)
        return final_paths

    def _validate_source(self, path: Path) -> None:
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ImageImportError("対応していない画像形式です。")
        if not path.exists() or not path.is_file():
            raise ImageImportError("画像ファイルが見つかりません。")

    def _save_as_png(self, source_path: Path, target_path: Path) -> None:
        image = QImage(str(source_path))
        if image.isNull():
            raise ImageImportError("画像の読み込みに失敗しました。")
        if not image.save(str(target_path), "PNG"):
            raise ImageImportError("画像の保存に失敗しました。")

    def _clear_images(self, images_dir: Path) -> None:
        if not images_dir.exists():
            return
        for path in images_dir.iterdir():
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                path.unlink()

    def _images_dir(self, project_dir: Path) -> Path:
        images_dir = project_dir / "images"
        if not project_dir.exists():
            raise ImageImportError("画像フォルダが見つかりません。")
        return images_dir

    def _image_index(self, path: Path) -> int | None:
        try:
            return int(path.stem)
        except ValueError:
            return None
