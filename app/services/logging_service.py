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
