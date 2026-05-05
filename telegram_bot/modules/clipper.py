"""
Auto-clipping module — analyzes video and finds interesting segments.
Uses scene detection and audio energy analysis to find highlights.
"""

import subprocess
import json
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Clip:
    """A detected video segment."""
    start: float
    end: float
    score: float
    reason: str


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def get_video_info(video_path: str) -> dict:
    """Get video metadata."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", video_path],
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def detect_scenes(video_path: str, threshold: float = 0.3) -> list[float]:
    """Detect scene changes using ffmpeg's scene filter.
    Returns list of timestamps where scenes change."""
    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vf",
         f"select='gt(scene,{threshold})',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )

    timestamps = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            match = re.search(r"pts_time:(\d+\.?\d*)", line)
            if match:
                timestamps.append(float(match.group(1)))

    return timestamps


def analyze_audio_energy(video_path: str, segment_duration: float = 2.0) -> list[tuple[float, float]]:
    """Analyze audio energy levels in segments.
    Returns list of (timestamp, energy_level) tuples."""
    duration = get_video_duration(video_path)
    if duration <= 0:
        return []

    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-af",
         f"astats=metadata=1:reset={int(segment_duration * 44100)}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )

    # Parse volume levels from astats output
    energy_points = []
    current_time = 0.0
    for line in result.stderr.split("\n"):
        if "RMS level" in line or "Peak level" in line:
            match = re.search(r"(-?\d+\.?\d*)\s*dB", line)
            if match:
                db = float(match.group(1))
                energy_points.append((current_time, db))
                current_time += segment_duration

    return energy_points


def find_highlights(video_path: str, max_clips: int = 5,
                    clip_duration: float = 15.0,
                    max_total_duration: float = 60.0) -> list[Clip]:
    """Find the most interesting segments in a video.
    Combines scene detection and audio analysis."""
    duration = get_video_duration(video_path)
    if duration <= clip_duration:
        return [Clip(start=0, end=duration, score=1.0, reason="Video is short enough as-is")]

    clips = []

    # Get scene changes
    scenes = detect_scenes(video_path)

    # If we have scene changes, create clips around them
    if scenes:
        for scene_time in scenes:
            start = max(0, scene_time - 2)
            end = min(duration, scene_time + clip_duration - 2)
            clips.append(Clip(
                start=start, end=end,
                score=0.7, reason="Scene change detected",
            ))

    # If not enough clips from scenes, divide evenly
    if len(clips) < max_clips:
        segment_len = duration / (max_clips + 1)
        for i in range(max_clips):
            start = segment_len * (i + 0.5)
            end = min(duration, start + clip_duration)
            if not any(abs(c.start - start) < clip_duration / 2 for c in clips):
                clips.append(Clip(
                    start=start, end=end,
                    score=0.5, reason="Evenly distributed segment",
                ))

    # Sort by score and take top N
    clips.sort(key=lambda c: c.score, reverse=True)
    clips = clips[:max_clips]

    # Sort by time for sequential output
    clips.sort(key=lambda c: c.start)

    # Ensure total duration doesn't exceed max
    total = sum(c.end - c.start for c in clips)
    if total > max_total_duration:
        ratio = max_total_duration / total
        for clip in clips:
            clip_len = clip.end - clip.start
            clip.end = clip.start + clip_len * ratio

    return clips


def extract_clip(video_path: str, clip: Clip, output_path: str,
                 extra_filters: list[str] | None = None) -> str:
    """Extract a single clip from the video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", str(clip.start),
        "-to", str(clip.end),
    ]

    if extra_filters:
        cmd.extend(["-vf", ",".join(extra_filters)])
        cmd.extend(["-c:a", "aac"])
    else:
        cmd.extend(["-c", "copy"])

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract clip: {result.stderr[-300:]}")

    return output_path


def concatenate_clips(clip_paths: list[str], output_path: str) -> str:
    """Concatenate multiple clips into one video."""
    # Create concat file
    concat_file = Path(output_path).parent / "concat_list.txt"
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
        # Try with re-encoding if stream copy fails
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_file) if concat_file.exists() else "/dev/null",
             "-c:v", "libx264", "-c:a", "aac", output_path],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to concatenate: {result.stderr[-300:]}")

    return output_path
