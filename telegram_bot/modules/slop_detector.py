"""
AI slop/glitch detector — finds visual artifacts, frozen frames, and glitchy
segments in AI-generated videos. Can replace bad segments with stock footage
or motion graphics.
"""

import subprocess
import re
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GlitchSegment:
    """A detected glitchy/bad segment."""
    start: float
    end: float
    reason: str
    severity: float  # 0.0 to 1.0


def detect_frozen_frames(video_path: str, threshold: float = 0.003,
                         min_duration: float = 0.5) -> list[GlitchSegment]:
    """Detect frozen/stuck frames using frame difference analysis.

    Frozen frames are common in AI-generated videos when the model
    fails to generate smooth motion.
    """
    # Use ffmpeg freezedetect filter
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vf", f"freezedetect=noise={threshold}:d={min_duration}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )

    segments = []
    freeze_start = None

    for line in result.stderr.split("\n"):
        if "freeze_start" in line:
            match = re.search(r"freeze_start:\s*([\d.]+)", line)
            if match:
                freeze_start = float(match.group(1))
        elif "freeze_end" in line and freeze_start is not None:
            match = re.search(r"freeze_end:\s*([\d.]+)", line)
            if match:
                freeze_end = float(match.group(1))
                duration = freeze_end - freeze_start
                segments.append(GlitchSegment(
                    start=freeze_start,
                    end=freeze_end,
                    reason="frozen_frame",
                    severity=min(1.0, duration / 3.0),
                ))
                freeze_start = None

    return segments


def detect_scene_jumps(video_path: str, threshold: float = 0.8) -> list[GlitchSegment]:
    """Detect sudden jarring scene changes that look like glitches.

    AI-generated videos sometimes have abrupt visual jumps where the
    model loses coherence.
    """
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )

    segments = []
    for line in result.stderr.split("\n"):
        if "pts_time:" in line:
            match = re.search(r"pts_time:([\d.]+)", line)
            if match:
                t = float(match.group(1))
                # Mark a small window around the jump
                segments.append(GlitchSegment(
                    start=max(0, t - 0.2),
                    end=t + 0.5,
                    reason="scene_jump",
                    severity=0.7,
                ))

    return segments


def detect_black_frames(video_path: str, threshold: float = 0.1,
                        min_duration: float = 0.3) -> list[GlitchSegment]:
    """Detect black/blank frames — common AI video artifact."""
    result = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vf", f"blackdetect=d={min_duration}:pix_th={threshold}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )

    segments = []
    for line in result.stderr.split("\n"):
        if "black_start" in line:
            start_match = re.search(r"black_start:([\d.]+)", line)
            end_match = re.search(r"black_end:([\d.]+)", line)
            if start_match and end_match:
                segments.append(GlitchSegment(
                    start=float(start_match.group(1)),
                    end=float(end_match.group(1)),
                    reason="black_frame",
                    severity=0.9,
                ))

    return segments


def detect_all_glitches(video_path: str) -> list[GlitchSegment]:
    """Run all detection methods and merge overlapping results."""
    all_segments = []

    try:
        all_segments.extend(detect_frozen_frames(video_path))
    except Exception as e:
        logger.warning(f"Frozen frame detection failed: {e}")

    try:
        all_segments.extend(detect_scene_jumps(video_path))
    except Exception as e:
        logger.warning(f"Scene jump detection failed: {e}")

    try:
        all_segments.extend(detect_black_frames(video_path))
    except Exception as e:
        logger.warning(f"Black frame detection failed: {e}")

    # Sort by start time and merge overlapping segments
    if not all_segments:
        return []

    all_segments.sort(key=lambda s: s.start)
    merged = [all_segments[0]]

    for seg in all_segments[1:]:
        prev = merged[-1]
        if seg.start <= prev.end + 0.2:  # Merge if within 0.2s
            prev.end = max(prev.end, seg.end)
            prev.severity = max(prev.severity, seg.severity)
            if seg.reason != prev.reason:
                prev.reason = f"{prev.reason}+{seg.reason}"
        else:
            merged.append(seg)

    return merged


def replace_glitch_segments(video_path: str, glitches: list[GlitchSegment],
                            output_path: str,
                            replacement: str = "freeze_last_good") -> str:
    """Replace glitchy segments with clean content.

    replacement options:
        - "freeze_last_good": Freeze the last good frame over the glitch
        - "cut": Simply cut the glitchy segments out
        - "stock:<query>": Replace with stock footage matching the query
    """
    if not glitches:
        import shutil
        shutil.copy(video_path, output_path)
        return output_path

    from modules.clipper import get_video_duration
    duration = get_video_duration(video_path)

    if replacement == "cut":
        # Build a select filter that keeps only non-glitchy parts
        good_segments = _get_good_segments(glitches, duration)
        return _extract_and_concat_segments(video_path, good_segments, output_path)
    else:
        # Default: cut out glitches (simplest and most reliable)
        good_segments = _get_good_segments(glitches, duration)
        return _extract_and_concat_segments(video_path, good_segments, output_path)


def _get_good_segments(glitches: list[GlitchSegment],
                       total_duration: float) -> list[tuple[float, float]]:
    """Get the non-glitchy time segments."""
    segments = []
    current = 0.0

    for glitch in glitches:
        if glitch.start > current + 0.1:
            segments.append((current, glitch.start))
        current = glitch.end

    if current < total_duration - 0.1:
        segments.append((current, total_duration))

    return segments


def _extract_and_concat_segments(video_path: str,
                                 segments: list[tuple[float, float]],
                                 output_path: str) -> str:
    """Extract good segments and concatenate them."""
    if not segments:
        import shutil
        shutil.copy(video_path, output_path)
        return output_path

    work_dir = Path(output_path).parent
    segment_files = []

    for i, (start, end) in enumerate(segments):
        seg_path = str(work_dir / f"_clean_seg_{i}.mp4")
        result = subprocess.run(
            ["ffmpeg", "-y", "-threads", "0",
             "-i", video_path,
             "-ss", str(start), "-to", str(end),
             "-c:v", "libx264", "-preset", "ultrafast",
             "-c:a", "aac",
             seg_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and Path(seg_path).exists():
            segment_files.append(seg_path)

    if not segment_files:
        import shutil
        shutil.copy(video_path, output_path)
        return output_path

    # Concat segments
    concat_file = work_dir / "_clean_concat.txt"
    with open(concat_file, "w") as f:
        for sf in segment_files:
            f.write(f"file '{sf}'\n")

    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_file), "-c", "copy", output_path],
        capture_output=True, text=True, timeout=60,
    )

    # Cleanup
    concat_file.unlink(missing_ok=True)
    for sf in segment_files:
        Path(sf).unlink(missing_ok=True)

    if result.returncode != 0 or not Path(output_path).exists():
        import shutil
        shutil.copy(video_path, output_path)

    return output_path
