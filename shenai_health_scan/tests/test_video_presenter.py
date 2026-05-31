from shenai_health_scan.robot_io.video_presenter import VideoScreenPresenter


class FakeAssets:
    def progress_video_path(self, percent):
        return f"progress_{percent}.mp4"

    def processing_video_path(self):
        return "processing_result.mp4"

    def result_video_path(self, vitals):
        return f"result_{int(vitals['heart_rate_bpm'])}.mp4"


def test_presenter_plays_progress_video_once_per_ten_percent_bucket():
    played = []
    presenter = VideoScreenPresenter(FakeAssets(), lambda path, loop: played.append((path, loop)))

    presenter.show("measuring", {"progress": 0.05})
    presenter.show("measuring", {"progress": 0.10})
    presenter.show("measuring", {"progress": 0.19})
    presenter.show("measuring", {"progress": 0.20})
    presenter.show("measuring", {"progress": 1.00})
    presenter.show("measuring", {"progress": 1.00})

    assert played == [
        ("progress_10.mp4", True),
        ("progress_20.mp4", True),
        ("progress_100.mp4", True),
    ]


def test_presenter_plays_processing_and_generated_result_videos():
    played = []
    presenter = VideoScreenPresenter(FakeAssets(), lambda path, loop: played.append((path, loop)))

    presenter.show("processing_results", {})
    presenter.show("result_card", {"vitals": {"heart_rate_bpm": 63}})

    assert played == [
        ("processing_result.mp4", False),
        ("result_63.mp4", False),
    ]


def test_presenter_resets_progress_buckets_for_new_scan():
    played = []
    presenter = VideoScreenPresenter(FakeAssets(), lambda path, loop: played.append((path, loop)))

    presenter.show("measuring", {"progress": 1.0})
    presenter.show("coaching", {})
    presenter.show("measuring", {"progress": 0.1})

    assert played == [("progress_100.mp4", True), ("progress_10.mp4", True)]
