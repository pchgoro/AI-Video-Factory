from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from services.image_import_service import ImageImportError, ImageImportService


def _make_image(path: Path, color: QColor, image_format: str = "PNG") -> None:
    image = QImage(12, 12, QImage.Format_RGB32)
    image.fill(color)
    assert image.save(str(path), image_format)


def test_image_file_converts_to_png(tmp_path) -> None:
    source = tmp_path / "source.jpg"
    _make_image(source, QColor("red"), "JPG")
    project_dir = tmp_path / "project"
    (project_dir / "images").mkdir(parents=True)

    imported = ImageImportService().import_files(project_dir, [source], "overwrite")

    assert imported[0].path == project_dir / "images" / "001.png"
    assert imported[0].path.exists()
    assert not QImage(str(imported[0].path)).isNull()


def test_image_file_saves_with_numbered_name(tmp_path) -> None:
    source = tmp_path / "source.png"
    _make_image(source, QColor("blue"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    ImageImportService().import_files(project_dir, [source], "overwrite")

    assert (project_dir / "images" / "001.png").exists()


def test_existing_images_can_be_appended(tmp_path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _make_image(first, QColor("red"))
    _make_image(second, QColor("green"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    service = ImageImportService()
    service.import_files(project_dir, [first], "overwrite")

    service.import_files(project_dir, [second], "add")

    assert (project_dir / "images" / "001.png").exists()
    assert (project_dir / "images" / "002.png").exists()


def test_move_image_renumbers_sequence(tmp_path) -> None:
    red = tmp_path / "red.png"
    green = tmp_path / "green.png"
    _make_image(red, QColor("red"))
    _make_image(green, QColor("green"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    service = ImageImportService()
    imported = service.import_files(project_dir, [red, green], "overwrite")

    service.move_image(imported[1].path, -1)

    images_dir = project_dir / "images"
    assert (images_dir / "001.png").exists()
    assert (images_dir / "002.png").exists()
    assert QImage(str(images_dir / "001.png")).pixelColor(0, 0).green() > 100


def test_unsupported_image_format_raises_japanese_error(tmp_path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("not image", encoding="utf-8")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with pytest.raises(ImageImportError, match="対応していない画像形式です。"):
        ImageImportService().import_files(project_dir, [source], "overwrite")
