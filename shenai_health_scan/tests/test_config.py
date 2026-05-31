from shenai_health_scan.core.config import ScanConfig

def test_defaults():
    c = ScanConfig.from_dict({})
    assert c.camera_topic == "/aima/hal/sensor/rgbd_head_front/rgb_image"
    assert c.submit_fps == 30
    assert c.offline is False
    assert "service" in c.enabled_triggers

def test_overrides_and_unknown_keys_ignored():
    c = ScanConfig.from_dict({"submit_fps": 25, "api_key": "K", "junk": 1,
                              "screen_static_video_dir": "/pc3/videos",
                              "screen_result_video_dir": "/shared/results",
                              "publisher": {"endpoint": "http://x/y"}})
    assert c.submit_fps == 25 and c.api_key == "K"
    assert c.screen_static_video_dir == "/pc3/videos"
    assert c.screen_result_video_dir == "/shared/results"
    assert c.publisher.endpoint == "http://x/y"
