"""
Video downloader module — downloads videos from URLs using yt-dlp.
Supports hundreds of sites. Attempts watermark-free download where possible.
"""

import subprocess
import shutil
import re
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = Path.home() / "videos" / "telegram_bot" / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# URL pattern for detecting links in messages
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\')\]]+',
    re.IGNORECASE,
)


@dataclass
class DownloadedVideo:
    """A downloaded video file."""
    path: str
    title: str
    duration: float
    url: str
    index: int


def has_ytdlp() -> bool:
    """Check if yt-dlp is available."""
    return shutil.which("yt-dlp") is not None


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from a text message."""
    return URL_PATTERN.findall(text)


def download_video(url: str, index: int = 0, output_dir: str | None = None) -> DownloadedVideo:
    """Download a video from a URL using yt-dlp.

    Tries to get the best quality without watermark.

    Args:
        url: Video URL
        index: Clip index for ordering
        output_dir: Directory to save to (default: DOWNLOAD_DIR)

    Returns:
        DownloadedVideo with path and metadata
    """
    if not has_ytdlp():
        raise RuntimeError(
            "yt-dlp is not installed. Install it with: pip install yt-dlp"
        )

    save_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(save_dir / f"clip_{index:03d}_%(title).50s.%(ext)s")

    # Build yt-dlp command — prefer no-watermark formats
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        "--no-overwrites",
        "--max-filesize", "100M",
        "--socket-timeout", "30",
    ]

    # For TikTok: try to get without watermark
    if "tiktok" in url.lower():
        cmd.extend(["--extractor-args", "tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com"])

    cmd.append(url)

    logger.info(f"Downloading: {url}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        error_msg = result.stderr[-300:] if result.stderr else "Unknown error"
        raise RuntimeError(f"Download failed: {error_msg}")

    # Find the downloaded file
    downloaded = None
    for f in sorted(save_dir.glob(f"clip_{index:03d}_*")):
        if f.suffix in (".mp4", ".mkv", ".webm"):
            downloaded = f
            break

    if not downloaded:
        # Try to find any recently created file
        files = sorted(save_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
        for f in files:
            if f.suffix in (".mp4", ".mkv", ".webm") and f.stat().st_size > 1000:
                downloaded = f
                break

    if not downloaded:
        raise RuntimeError("Download appeared to succeed but no video file found")

    # Get title from filename
    title = downloaded.stem
    if title.startswith(f"clip_{index:03d}_"):
        title = title[len(f"clip_{index:03d}_"):]

    # Get duration
    from modules.clipper import get_video_duration
    duration = get_video_duration(str(downloaded))

    return DownloadedVideo(
        path=str(downloaded),
        title=title,
        duration=duration,
        url=url,
        index=index,
    )


def download_multiple(urls: list[str], output_dir: str | None = None) -> list[DownloadedVideo]:
    """Download multiple videos, maintaining order.

    Args:
        urls: List of video URLs in desired order
        output_dir: Directory to save to

    Returns:
        List of DownloadedVideo in the same order as input URLs
    """
    results = []
    for i, url in enumerate(urls):
        try:
            video = download_video(url, index=i, output_dir=output_dir)
            results.append(video)
            logger.info(f"Downloaded {i+1}/{len(urls)}: {video.title} ({video.duration:.1f}s)")
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            # Continue with remaining URLs
    return results


def merge_downloaded_clips(clips: list[DownloadedVideo], output_path: str,
                           add_transitions: bool = True,
                           transition_style: str = "cinematic") -> str:
    """Merge downloaded clips in order with transitions.

    Args:
        clips: Downloaded clips in order
        output_path: Output file path
        add_transitions: Whether to add transitions between clips
        transition_style: Style of transitions

    Returns:
        Path to merged video
    """
    if not clips:
        raise ValueError("No clips to merge")

    clip_paths = [c.path for c in clips]

    if len(clip_paths) == 1:
        import shutil as _shutil
        _shutil.copy(clip_paths[0], output_path)
        return output_path

    if add_transitions:
        from modules.transitions import join_segments_with_transitions
        return join_segments_with_transitions(
            clip_paths, output_path,
            style=transition_style,
            transition_duration=0.5,
        )
    else:
        # Simple concatenation
        work_dir = Path(output_path).parent
        concat_file = work_dir / "_merge_concat.txt"
        with open(concat_file, "w") as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")

        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_file), "-c", "copy", output_path],
            capture_output=True, text=True, timeout=120,
        )
        concat_file.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(f"Merge failed: {result.stderr[-300:]}")

        return output_path
