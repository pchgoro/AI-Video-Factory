from __future__ import annotations

import logging
from datetime import datetime

from config import AppPaths


def setup_logging(paths: AppPaths) -> logging.Logger:
    """日付別ログファイルを設定します。重複ハンドラは追加しません。"""
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_video_factory")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    log_path = paths.logs_dir / f"{datetime.now().date().isoformat()}.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def setup_youtube_logging(paths: AppPaths) -> logging.Logger:
    """Create a dedicated YouTube upload logger without exposing secrets."""
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_video_factory.youtube")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    handler = logging.FileHandler(paths.logs_dir / "youtube.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def setup_tiktok_logging(paths: AppPaths) -> logging.Logger:
    """Create a dedicated TikTok upload logger without exposing secrets."""
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_video_factory.tiktok")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    handler = logging.FileHandler(paths.logs_dir / "tiktok.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def setup_image_generation_logging(paths: AppPaths) -> logging.Logger:
    """Create a dedicated image generation logger without exposing credentials."""
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_video_factory.image_generation")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    handler = logging.FileHandler(paths.logs_dir / "image_generation.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def setup_production_logging(paths: AppPaths) -> logging.Logger:
    """Create a dedicated production orchestrator logger without exposing secrets."""
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_video_factory.production")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    handler = logging.FileHandler(paths.logs_dir / "production.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def setup_story_provider_logging(paths: AppPaths) -> logging.Logger:
    """Create a dedicated Story AI provider logger without exposing secrets."""
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ai_video_factory.story_provider")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    handler = logging.FileHandler(paths.logs_dir / "story_provider.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger
