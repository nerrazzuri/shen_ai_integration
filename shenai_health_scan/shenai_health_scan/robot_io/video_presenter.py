from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .videos import progress_bucket


class VideoScreenPresenter:
    def __init__(self, assets, play_video: Callable[[str, bool], None]):
        self._assets = assets
        self._play_video = play_video
        self._last_progress_bucket: Optional[int] = None

    def show(self, view: str, data: Dict[str, Any]) -> None:
        if view == "coaching":
            self._last_progress_bucket = None
            return

        if view == "measuring":
            bucket = progress_bucket(float(data.get("progress", 0.0)))
            if bucket is not None and bucket != self._last_progress_bucket:
                self._last_progress_bucket = bucket
                self._play_video(self._assets.progress_video_path(bucket), True)
            return

        if view == "processing_results":
            self._play_video(self._assets.processing_video_path(), False)
            return

        if view == "result_card" and "vitals" in data:
            self._play_video(self._assets.result_video_path(data["vitals"]), False)
