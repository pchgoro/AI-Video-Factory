from __future__ import annotations

from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class FutureEditor(VideoEditor):
    """その他のAI動画編集ツールを接続するための予約クラスです。"""

    engine_name = "future"

    def render(self, request: VideoEditRequest) -> VideoEditResult:
        return VideoEditResult(False, "FutureEditorは未実装です。")
