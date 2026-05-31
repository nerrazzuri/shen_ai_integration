from pathlib import Path

from shenai_health_scan.generate_videos import generate_static_videos


def test_generate_static_videos_writes_progress_and_processing_assets(tmp_path):
    paths = [Path(p) for p in generate_static_videos(
        tmp_path, width=80, height=60, fps=1, duration_sec=1.0)]

    assert len(paths) == 11
    assert (tmp_path / "progress_10.mp4") in paths
    assert (tmp_path / "progress_100.mp4") in paths
    assert (tmp_path / "processing_result.mp4") in paths
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
