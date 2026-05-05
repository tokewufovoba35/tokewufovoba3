"""
Audio module — handles background music and SFX mixing.
Users upload their own music/SFX files to the bot.
"""

import subprocess
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class AudioAsset:
    """A stored audio file (music or SFX)."""
    path: str
    name: str
    duration: float
    asset_type: str  # "music" or "sfx"


MUSIC_DIR = Path(os.path.expanduser("~/videos/telegram_bot/music"))
SFX_DIR = Path(os.path.expanduser("~/videos/telegram_bot/sfx"))

MUSIC_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)


def get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file."""
    import shutil
    import re
    if shutil.which("ffprobe"):
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            pass

    # Fallback: use ffmpeg
    result = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-f", "null", "-"],
        capture_output=True, text=True, timeout=30,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
        return h * 3600 + m * 60 + s
    return 0.0


def list_music() -> list[AudioAsset]:
    """List all stored music files."""
    assets = []
    for f in MUSIC_DIR.iterdir():
        if f.suffix in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"):
            assets.append(AudioAsset(
                path=str(f),
                name=f.stem,
                duration=get_audio_duration(str(f)),
                asset_type="music",
            ))
    return assets


def list_sfx() -> list[AudioAsset]:
    """List all stored SFX files."""
    assets = []
    for f in SFX_DIR.iterdir():
        if f.suffix in (".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"):
            assets.append(AudioAsset(
                path=str(f),
                name=f.stem,
                duration=get_audio_duration(str(f)),
                asset_type="sfx",
            ))
    return assets


def save_music(file_path: str, name: str) -> AudioAsset:
    """Save an uploaded music file."""
    dest = MUSIC_DIR / f"{name}{Path(file_path).suffix}"
    if str(file_path) != str(dest):
        Path(file_path).rename(dest)
    duration = get_audio_duration(str(dest))
    return AudioAsset(path=str(dest), name=name, duration=duration, asset_type="music")


def save_sfx(file_path: str, name: str) -> AudioAsset:
    """Save an uploaded SFX file."""
    dest = SFX_DIR / f"{name}{Path(file_path).suffix}"
    if str(file_path) != str(dest):
        Path(file_path).rename(dest)
    duration = get_audio_duration(str(dest))
    return AudioAsset(path=str(dest), name=name, duration=duration, asset_type="sfx")


def add_background_music(video_path: str, music_path: str, output_path: str,
                         volume: float = 0.3, loop: bool = True,
                         fade_out_duration: float = 2.0) -> str:
    """Add background music to video.
    
    Args:
        video_path: Input video file
        music_path: Music file to add
        output_path: Output file path
        volume: Music volume relative to original audio (0.0-1.0)
        loop: Whether to loop music if shorter than video
        fade_out_duration: Duration of fade out at the end
    """
    video_duration = get_audio_duration(video_path)

    # Build complex filter for mixing
    filter_parts = []

    if loop:
        # Loop music to match video duration
        filter_parts.append(
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{video_duration},"
            f"afade=t=out:st={video_duration - fade_out_duration}:d={fade_out_duration},"
            f"volume={volume}[music]"
        )
    else:
        filter_parts.append(
            f"[1:a]afade=t=out:st={max(0, video_duration - fade_out_duration)}:d={fade_out_duration},"
            f"volume={volume}[music]"
        )

    # Mix original audio with music
    filter_parts.append("[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]")

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to add music: {result.stderr[-300:]}")

    return output_path


def add_sfx_at_time(video_path: str, sfx_path: str, output_path: str,
                    timestamp: float = 0.0, volume: float = 0.8) -> str:
    """Add a sound effect at a specific timestamp."""
    filter_complex = (
        f"[1:a]adelay={int(timestamp * 1000)}|{int(timestamp * 1000)},"
        f"volume={volume}[sfx];"
        f"[0:a][sfx]amix=inputs=2:duration=first[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", sfx_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to add SFX: {result.stderr[-300:]}")

    return output_path


def replace_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """Replace video's audio entirely with a new audio track."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to replace audio: {result.stderr[-300:]}")

    return output_path
