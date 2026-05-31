from __future__ import annotations

import argparse
from pathlib import Path

from .robot_io.videos import VideoAssetManager


def generate_static_videos(output_dir, width: int = 1280, height: int = 720,
                           fps: int = 24, duration_sec: float = 2.0):
    assets = VideoAssetManager(output_dir, width=width, height=height,
                               fps=fps, duration_sec=duration_sec)
    return assets.ensure_static_videos()


def main():
    parser = argparse.ArgumentParser(
        description="Generate static Shen.AI robot face-screen MP4 assets.")
    parser.add_argument("--output-dir", required=True,
                        help="Directory to write progress_*.mp4 and processing_results.mp4")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--duration-sec", type=float, default=2.0)
    args = parser.parse_args()

    paths = generate_static_videos(
        Path(args.output_dir),
        width=args.width,
        height=args.height,
        fps=args.fps,
        duration_sec=args.duration_sec,
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
