from __future__ import annotations

from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class VideoUseEditor(VideoEditor):
    """browser-use/video-use統合用の予約クラスです。現時点では実処理を行いません。"""

    engine_name = "video-use"

    def render(self, request: VideoEditRequest) -> VideoEditResult:
        return VideoEditResult(
            success=False,
            message="VideoUseEditorは未実装です。将来 browser-use/video-use 統合をここに追加します。",
        )
