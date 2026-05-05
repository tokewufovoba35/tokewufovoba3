"""
Transitions module — adds transitions between video segments.
Supports crossfade, wipe, slide, zoom, and more.
"""

import subprocess
from pathlib import Path


# Available xfade transitions in ffmpeg
TRANSITIONS = [
    "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite",
    "radial", "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circleopen", "circleclose", "vertopen", "vertclose",
    "horzopen", "horzclose", "dissolve", "pixelize",
    "diagtl", "diagtr", "diagbl", "diagbr",
]

# Transition presets for different moods
TRANSITION_PRESETS = {
    "smooth": ["fade", "dissolve", "smoothleft", "smoothright"],
    "dynamic": ["wipeleft", "slideright", "circlecrop", "radial"],
    "cinematic": ["fadeblack", "dissolve", "fade"],
    "energetic": ["wipeleft", "wiperight", "slideleft", "slideright", "pixelize"],
    "minimal": ["fade", "fadeblack"],
    "creative": ["circlecrop", "circleopen", "circleclose", "radial", "diagtl"],
}


def get_transition_for_style(style: str = "smooth", index: int = 0) -> str:
    """Get a transition name based on style and position."""
    transitions = TRANSITION_PRESETS.get(style, TRANSITION_PRESETS["smooth"])
    return transitions[index % len(transitions)]


def add_transition_between(video1_path: str, video2_path: str, output_path: str,
                           transition: str = "fade",
                           duration: float = 0.5) -> str:
    """Add a transition between two video clips.
    
    Args:
        video1_path: First video
        video2_path: Second video
        output_path: Output path
        transition: Transition type (from TRANSITIONS list)
        duration: Transition duration in seconds
    """
    # Get duration of first video to calculate offset
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video1_path],
        capture_output=True, text=True,
    )
    try:
        video1_duration = float(result.stdout.strip())
    except ValueError:
        video1_duration = 5.0

    offset = max(0, video1_duration - duration)

    cmd = [
        "ffmpeg", "-y",
        "-i", video1_path,
        "-i", video2_path,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset}[vout];"
        f"[0:a][1:a]acrossfade=d={duration}[aout]",
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Transition failed: {result.stderr[-300:]}")

    return output_path


def join_segments_with_transitions(segment_paths: list[str], output_path: str,
                                    style: str = "smooth",
                                    transition_duration: float = 0.5) -> str:
    """Join multiple video segments with transitions between each.
    
    Args:
        segment_paths: List of video file paths
        output_path: Final output path
        style: Transition style preset
        transition_duration: Duration of each transition
    """
    if not segment_paths:
        raise ValueError("No segments to join")

    if len(segment_paths) == 1:
        import shutil
        shutil.copy(segment_paths[0], output_path)
        return output_path

    # Join segments pairwise with transitions
    work_dir = Path(output_path).parent
    current = segment_paths[0]

    for i in range(1, len(segment_paths)):
        transition_name = get_transition_for_style(style, i - 1)
        intermediate = str(work_dir / f"_trans_step_{i}.mp4")

        try:
            add_transition_between(
                current, segment_paths[i], intermediate,
                transition=transition_name,
                duration=transition_duration,
            )
        except RuntimeError:
            # Fallback: simple concat without transition
            concat_file = work_dir / f"_concat_{i}.txt"
            with open(concat_file, "w") as f:
                f.write(f"file '{current}'\n")
                f.write(f"file '{segment_paths[i]}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", str(concat_file), "-c", "copy", intermediate],
                capture_output=True, text=True, timeout=60,
            )
            concat_file.unlink(missing_ok=True)

        # Clean up previous intermediate
        if i > 1 and Path(current).name.startswith("_trans_step_"):
            Path(current).unlink(missing_ok=True)

        current = intermediate

    # Move final result to output path
    if current != output_path:
        Path(current).rename(output_path)

    # Clean up any remaining intermediates
    for f in work_dir.glob("_trans_step_*.mp4"):
        f.unlink(missing_ok=True)

    return output_path
