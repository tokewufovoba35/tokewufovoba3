"""
Silence removal module — detects and removes silent segments from video.
Uses ffmpeg's silencedetect filter to find quiet parts and cuts them out.
"""

import subprocess
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SilentSegment:
    """A detected silent segment."""
    start: float
    end: float
    duration: float


def detect_silence(video_path: str, threshold_db: float = -30.0,
                   min_duration: float = 0.5) -> list[SilentSegment]:
    """Detect silent segments in a video.
    
    Args:
        video_path: Path to video file
        threshold_db: Volume threshold in dB (below = silence). Default -30dB.
        min_duration: Minimum silence duration in seconds to detect. Default 0.5s.
    
    Returns:
        List of SilentSegment objects
    """
    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-af",
         f"silencedetect=noise={threshold_db}dB:d={min_duration}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )

    segments = []
    silence_start = None

    for line in result.stderr.split("\n"):
        if "silence_start:" in line:
            match = re.search(r"silence_start:\s*(-?\d+\.?\d*)", line)
            if match:
                silence_start = float(match.group(1))
        elif "silence_end:" in line and silence_start is not None:
            match = re.search(r"silence_end:\s*(-?\d+\.?\d*)", line)
            dur_match = re.search(r"silence_duration:\s*(-?\d+\.?\d*)", line)
            if match:
                silence_end = float(match.group(1))
                duration = float(dur_match.group(1)) if dur_match else silence_end - silence_start
                segments.append(SilentSegment(
                    start=silence_start,
                    end=silence_end,
                    duration=duration,
                ))
                silence_start = None

    return segments


def get_speaking_segments(video_path: str, threshold_db: float = -30.0,
                          min_silence: float = 0.5,
                          padding: float = 0.1) -> list[tuple[float, float]]:
    """Get segments where there IS audio (non-silent parts).
    
    Args:
        video_path: Path to video
        threshold_db: Silence threshold
        min_silence: Minimum silence duration to cut
        padding: Extra time to keep around speech (avoids cutting words)
    
    Returns:
        List of (start, end) tuples for non-silent segments
    """
    from modules.clipper import get_video_duration
    
    duration = get_video_duration(video_path)
    if duration <= 0:
        return [(0, 0)]

    silent_segments = detect_silence(video_path, threshold_db, min_silence)

    if not silent_segments:
        return [(0.0, duration)]

    # Build speaking segments (inverse of silent segments)
    speaking = []
    current_start = 0.0

    for seg in silent_segments:
        # Add speaking segment before this silence
        speech_end = seg.start + padding
        if speech_end > current_start + 0.1:  # Only add if meaningful
            speaking.append((current_start, min(speech_end, seg.start)))
        current_start = max(0, seg.end - padding)

    # Add final segment after last silence
    if current_start < duration - 0.1:
        speaking.append((current_start, duration))

    return speaking


def remove_silence(video_path: str, output_path: str,
                   threshold_db: float = -30.0,
                   min_silence: float = 0.5,
                   padding: float = 0.15,
                   transition: str = "none") -> str:
    """Remove silent parts from a video.
    
    Args:
        video_path: Input video
        output_path: Output path
        threshold_db: Volume threshold (lower = more aggressive)
        min_silence: Minimum silence duration to remove
        padding: Keep this much silence around speech (prevents hard cuts)
        transition: "none", "crossfade", or "fade" between segments
    
    Returns:
        Path to output file
    """
    speaking_segments = get_speaking_segments(
        video_path, threshold_db, min_silence, padding
    )

    if not speaking_segments:
        raise RuntimeError("No speaking segments detected — video may be entirely silent")

    if len(speaking_segments) == 1 and speaking_segments[0][0] == 0:
        # No silence to remove
        import shutil
        shutil.copy(video_path, output_path)
        return output_path

    # Create individual segment files
    stem = Path(video_path).stem
    ext = Path(video_path).suffix
    work_dir = Path(output_path).parent
    segment_paths = []

    for i, (start, end) in enumerate(speaking_segments):
        seg_path = str(work_dir / f"{stem}_seg{i}{ext}")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-ss", str(start), "-to", str(end),
             "-c", "copy", seg_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and Path(seg_path).exists():
            segment_paths.append(seg_path)

    if not segment_paths:
        raise RuntimeError("Failed to extract speaking segments")

    # Concatenate segments
    if transition == "crossfade" and len(segment_paths) > 1:
        # Use xfade filter for crossfade transitions
        _concatenate_with_crossfade(segment_paths, output_path)
    else:
        # Simple concat
        concat_file = work_dir / f"{stem}_concat.txt"
        with open(concat_file, "w") as f:
            for path in segment_paths:
                f.write(f"file '{path}'\n")

        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_file), "-c", "copy", output_path],
            capture_output=True, text=True, timeout=120,
        )

        concat_file.unlink(missing_ok=True)

        if result.returncode != 0:
            # Fallback: re-encode
            result = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", str(concat_file), "-c:v", "libx264", "-c:a", "aac",
                 output_path],
                capture_output=True, text=True, timeout=180,
            )

    # Clean up segment files
    for seg_path in segment_paths:
        Path(seg_path).unlink(missing_ok=True)

    if not Path(output_path).exists():
        raise RuntimeError("Failed to produce output after silence removal")

    return output_path


def _concatenate_with_crossfade(segment_paths: list[str], output_path: str,
                                 fade_duration: float = 0.3) -> None:
    """Concatenate segments with crossfade transitions."""
    if len(segment_paths) <= 1:
        import shutil
        shutil.copy(segment_paths[0], output_path)
        return

    # For crossfade, we need to re-encode and use xfade filter
    # Build complex filter chain
    n = len(segment_paths)
    inputs = []
    for path in segment_paths:
        inputs.extend(["-i", path])

    # Build xfade filter chain
    filter_parts = []
    current_label = "[0:v]"

    for i in range(1, n):
        next_label = f"[{i}:v]"
        out_label = f"[v{i}]" if i < n - 1 else "[vout]"
        filter_parts.append(
            f"{current_label}{next_label}xfade=transition=fade:duration={fade_duration}:offset=0{out_label}"
        )
        current_label = out_label

    # Audio crossfade
    audio_current = "[0:a]"
    for i in range(1, n):
        next_audio = f"[{i}:a]"
        out_audio = f"[a{i}]" if i < n - 1 else "[aout]"
        filter_parts.append(
            f"{audio_current}{next_audio}acrossfade=d={fade_duration}{out_audio}"
        )
        audio_current = out_audio

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-c:a", "aac",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        # Fallback to simple concat
        concat_file = Path(output_path).parent / "concat_xfade.txt"
        with open(concat_file, "w") as f:
            for path in segment_paths:
                f.write(f"file '{path}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_file), "-c", "copy", output_path],
            capture_output=True, text=True, timeout=120,
        )
        concat_file.unlink(missing_ok=True)
