from pathlib import Path

from shenai_health_scan.robot_io.videos import VideoAssetManager, progress_bucket


def test_progress_bucket_uses_completed_ten_percent_steps():
    assert progress_bucket(0.0) is None
    assert progress_bucket(0.099) is None
    assert progress_bucket(0.10) == 10
    assert progress_bucket(0.19) == 10
    assert progress_bucket(0.20) == 20
    assert progress_bucket(0.999) == 90
    assert progress_bucket(1.0) == 100


def test_video_asset_manager_creates_local_mp4_files(tmp_path):
    assets = VideoAssetManager(tmp_path, width=160, height=90,
                               fps=2, duration_sec=0.5)

    progress = Path(assets.progress_video_path(10))
    processing = Path(assets.processing_video_path())
    result = Path(assets.result_video_path({
        "heart_rate_bpm": 63,
        "systolic_bp_mmhg": 126,
        "diastolic_bp_mmhg": 79,
    }))

    assert progress.name == "progress_10.mp4"
    assert processing.name == "processing_result.mp4"
    assert result.name.startswith("result_")
    assert all(p.suffix == ".mp4" and p.stat().st_size > 0
               for p in (progress, processing, result))


def test_video_asset_manager_can_pre_generate_static_robot_videos(tmp_path):
    assets = VideoAssetManager(tmp_path, width=80, height=60,
                               fps=1, duration_sec=1.0)

    paths = [Path(p) for p in assets.ensure_static_videos()]

    assert len(paths) == 11
    assert {p.name for p in paths} == {
        "progress_10.mp4", "progress_20.mp4", "progress_30.mp4",
        "progress_40.mp4", "progress_50.mp4", "progress_60.mp4",
        "progress_70.mp4", "progress_80.mp4", "progress_90.mp4",
        "progress_100.mp4", "processing_result.mp4",
    }
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)


def test_video_asset_manager_can_reference_pre_generated_static_videos(tmp_path):
    assets = VideoAssetManager(tmp_path, generate_missing_static=False)

    progress = Path(assets.progress_video_path(10))
    processing = Path(assets.processing_video_path())

    assert progress == tmp_path / "progress_10.mp4"
    assert processing == tmp_path / "processing_result.mp4"
    assert not progress.exists()
    assert not processing.exists()


def test_video_asset_manager_can_write_result_video_to_separate_runtime_dir(tmp_path):
    static_dir = tmp_path / "pc3_static"
    result_dir = tmp_path / "runtime_results"
    assets = VideoAssetManager(static_dir, result_root=result_dir,
                               generate_missing_static=False,
                               width=80, height=60, fps=1, duration_sec=1.0)

    progress = Path(assets.progress_video_path(10))
    result = Path(assets.result_video_path({"heart_rate_bpm": 63}))

    assert progress == static_dir / "progress_10.mp4"
    assert not progress.exists()
    assert result.parent == result_dir
    assert result.exists()
