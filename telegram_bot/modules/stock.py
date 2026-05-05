"""
Stock footage module — search and download free stock videos from Pexels.
Requires a free Pexels API key (https://www.pexels.com/api/).
"""

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
STOCK_DIR = Path(os.path.expanduser("~/videos/telegram_bot/stock"))
STOCK_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StockVideo:
    """A stock video result."""
    id: int
    url: str
    download_url: str
    width: int
    height: int
    duration: int
    description: str


def search_stock_videos(query: str, orientation: str = "landscape",
                        min_duration: int = 3, max_results: int = 5) -> list[StockVideo]:
    """Search Pexels for stock videos.
    
    Args:
        query: Search term (e.g. "nature", "city", "technology")
        orientation: "landscape", "portrait", or "square"
        min_duration: Minimum video duration in seconds
        max_results: Maximum results to return
    
    Returns:
        List of StockVideo objects
    """
    if not HAS_REQUESTS:
        raise RuntimeError("requests library not installed. Run: pip install requests")

    if not PEXELS_API_KEY:
        raise ValueError(
            "Pexels API key not set. Get a free key at https://www.pexels.com/api/\n"
            "Then set: export PEXELS_API_KEY='your-key'"
        )

    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": max_results,
        "size": "medium",
    }

    response = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers, params=params, timeout=15,
    )

    if response.status_code != 200:
        raise RuntimeError(f"Pexels API error: {response.status_code} {response.text[:200]}")

    data = response.json()
    results = []

    for video in data.get("videos", []):
        if video.get("duration", 0) < min_duration:
            continue

        # Get the best quality file
        video_files = video.get("video_files", [])
        best_file = None
        for vf in video_files:
            if vf.get("quality") == "hd" or (not best_file and vf.get("quality") == "sd"):
                best_file = vf

        if best_file:
            results.append(StockVideo(
                id=video["id"],
                url=video.get("url", ""),
                download_url=best_file["link"],
                width=best_file.get("width", 1920),
                height=best_file.get("height", 1080),
                duration=video.get("duration", 0),
                description=video.get("url", "").split("/")[-2].replace("-", " ") if video.get("url") else query,
            ))

    return results[:max_results]


def download_stock_video(stock_video: StockVideo, output_dir: str | None = None) -> str:
    """Download a stock video.
    
    Returns:
        Path to downloaded file
    """
    if not HAS_REQUESTS:
        raise RuntimeError("requests library not installed")

    save_dir = Path(output_dir) if output_dir else STOCK_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    output_path = save_dir / f"stock_{stock_video.id}.mp4"

    if output_path.exists():
        return str(output_path)

    response = requests.get(stock_video.download_url, stream=True, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Download failed: HTTP {response.status_code}")

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return str(output_path)


def insert_broll(main_video_path: str, stock_path: str, output_path: str,
                 insert_at: float = 5.0, broll_duration: float = 3.0) -> str:
    """Insert B-roll footage at a specific point in the main video.
    
    The main video's audio continues over the B-roll.
    """
    from modules.clipper import get_video_duration

    main_duration = get_video_duration(main_video_path)
    if insert_at >= main_duration:
        insert_at = main_duration / 2

    # Split main video into before and after
    work_dir = Path(output_path).parent
    before_path = str(work_dir / "_broll_before.mp4")
    after_path = str(work_dir / "_broll_after.mp4")
    broll_clip = str(work_dir / "_broll_clip.mp4")

    # Extract segment before insert point
    subprocess.run(
        ["ffmpeg", "-y", "-i", main_video_path,
         "-t", str(insert_at), "-c", "copy", before_path],
        capture_output=True, text=True, timeout=60,
    )

    # Extract segment after insert point
    subprocess.run(
        ["ffmpeg", "-y", "-i", main_video_path,
         "-ss", str(insert_at), "-c", "copy", after_path],
        capture_output=True, text=True, timeout=60,
    )

    # Trim B-roll to desired duration and keep main audio
    # Use video from stock + audio from main at that timestamp
    subprocess.run(
        ["ffmpeg", "-y",
         "-i", stock_path,
         "-i", main_video_path,
         "-t", str(broll_duration),
         "-map", "0:v",  # video from stock
         "-map", "1:a",  # audio from main
         "-ss", str(insert_at),  # audio position from main
         "-c:v", "libx264", "-preset", "fast",
         "-c:a", "aac",
         "-shortest",
         broll_clip],
        capture_output=True, text=True, timeout=60,
    )

    # Concatenate: before + broll + after
    concat_file = work_dir / "_broll_concat.txt"
    with open(concat_file, "w") as f:
        f.write(f"file '{before_path}'\n")
        if Path(broll_clip).exists():
            f.write(f"file '{broll_clip}'\n")
        f.write(f"file '{after_path}'\n")

    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_file),
         "-c:v", "libx264", "-preset", "fast",
         "-c:a", "aac",
         output_path],
        capture_output=True, text=True, timeout=180,
    )

    # Clean up
    for f in [before_path, after_path, broll_clip, str(concat_file)]:
        Path(f).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"B-roll insert failed: {result.stderr[-300:]}")

    return output_path
