"""
Smart music module — finds and adds suitable background music.
Can search for royalty-free music by mood/genre or use user-uploaded tracks.
"""

import subprocess
import logging
import re
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Free royalty-free music from Pixabay Music API
PIXABAY_MUSIC_URL = "https://pixabay.com/music/search/"


@dataclass
class MusicSuggestion:
    """A music suggestion based on video analysis."""
    mood: str
    tempo: str
    genre: str
    reason: str


def analyze_video_mood(video_path: str) -> MusicSuggestion:
    """Analyze video to suggest appropriate music mood.

    Uses video duration and scene changes to estimate pacing/energy.
    """
    from modules.clipper import get_video_duration, detect_scenes

    duration = get_video_duration(video_path)
    scenes = detect_scenes(video_path, threshold=0.3)
    scene_count = len(scenes)

    # Estimate pacing from scene frequency
    if duration > 0:
        scenes_per_minute = (scene_count / duration) * 60
    else:
        scenes_per_minute = 0

    # Determine mood based on pacing
    if scenes_per_minute > 15:
        mood = "energetic"
        tempo = "fast"
        genre = "electronic"
        reason = "High scene frequency suggests energetic content"
    elif scenes_per_minute > 8:
        mood = "upbeat"
        tempo = "medium"
        genre = "pop"
        reason = "Moderate pacing suggests upbeat content"
    elif scenes_per_minute > 3:
        mood = "cinematic"
        tempo = "medium"
        genre = "cinematic"
        reason = "Steady pacing suggests cinematic/documentary style"
    else:
        mood = "calm"
        tempo = "slow"
        genre = "ambient"
        reason = "Low scene frequency suggests calm/reflective content"

    # Short videos tend to be more energetic
    if duration < 30:
        if mood == "calm":
            mood = "upbeat"
            tempo = "medium"

    return MusicSuggestion(mood=mood, tempo=tempo, genre=genre, reason=reason)


def generate_background_tone(output_path: str, duration: float,
                             mood: str = "cinematic") -> str:
    """Generate a simple background tone/ambient track using ffmpeg.

    This creates a basic ambient background when no music is available.
    Better than silence but not as good as real music.
    """
    # Generate a subtle ambient background using ffmpeg's built-in synth
    if mood in ("energetic", "upbeat"):
        # Higher frequency, more rhythmic
        freq = 220
        filter_chain = (
            f"sine=frequency={freq}:duration={duration},"
            f"tremolo=f=4:d=0.3,"
            f"volume=0.15"
        )
    elif mood == "cinematic":
        # Deep, atmospheric
        freq = 110
        filter_chain = (
            f"sine=frequency={freq}:duration={duration},"
            f"tremolo=f=0.5:d=0.4,"
            f"volume=0.1"
        )
    else:
        # Calm, barely there
        freq = 80
        filter_chain = (
            f"sine=frequency={freq}:duration={duration},"
            f"tremolo=f=0.2:d=0.5,"
            f"volume=0.08"
        )

    result = subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"anoisesrc=d={duration}:c=pink:a=0.02",
         "-f", "lavfi", "-i", f"aevalsrc={filter_chain}",
         "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=shortest[out]",
         "-map", "[out]",
         "-c:a", "aac", "-b:a", "128k",
         output_path],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        # Fallback: just silence
        subprocess.run(
            ["ffmpeg", "-y",
             "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
             "-c:a", "aac", output_path],
            capture_output=True, text=True, timeout=15,
        )

    return output_path


def add_smart_music(video_path: str, output_path: str,
                    user_music_path: str | None = None,
                    mood: str | None = None) -> str:
    """Add background music to video intelligently.

    Priority:
    1. User-uploaded music (if provided)
    2. Music from library (if available)
    3. Generated ambient background

    Args:
        video_path: Input video path
        output_path: Output video path
        user_music_path: Optional user-provided music file
        mood: Optional mood override
    """
    from modules.clipper import get_video_duration
    from modules.audio import list_music

    duration = get_video_duration(video_path)

    # Determine music source
    music_path = None

    if user_music_path and Path(user_music_path).exists():
        music_path = user_music_path
        logger.info(f"Using user-provided music: {music_path}")
    else:
        # Check music library
        library = list_music()
        if library:
            music_path = library[0].path
            logger.info(f"Using library music: {library[0].name}")

    if music_path:
        # Mix user/library music with video audio
        result = subprocess.run(
            ["ffmpeg", "-y", "-threads", "0",
             "-i", video_path,
             "-i", music_path,
             "-filter_complex",
             f"[1:a]aloop=loop=-1:size={int(duration * 44100)},"
             f"atrim=0:{duration},volume=0.15[music];"
             f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
             "-map", "0:v", "-map", "[aout]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest",
             output_path],
            capture_output=True, text=True, timeout=120,
        )

        if result.returncode == 0 and Path(output_path).exists():
            return output_path

        # If audio mixing fails (e.g., no audio in original), try without mixing
        result = subprocess.run(
            ["ffmpeg", "-y", "-threads", "0",
             "-i", video_path,
             "-i", music_path,
             "-filter_complex",
             f"[1:a]aloop=loop=-1:size={int(duration * 44100)},"
             f"atrim=0:{duration},volume=0.3[music]",
             "-map", "0:v", "-map", "[music]",
             "-c:v", "copy", "-c:a", "aac",
             "-shortest",
             output_path],
            capture_output=True, text=True, timeout=120,
        )

        if result.returncode == 0 and Path(output_path).exists():
            return output_path

    # Fallback: generate ambient background
    if not mood:
        suggestion = analyze_video_mood(video_path)
        mood = suggestion.mood

    work_dir = Path(output_path).parent
    ambient_path = str(work_dir / "_ambient_bg.aac")
    generate_background_tone(ambient_path, duration, mood)

    result = subprocess.run(
        ["ffmpeg", "-y", "-threads", "0",
         "-i", video_path,
         "-i", ambient_path,
         "-filter_complex",
         f"[0:a][1:a]amix=inputs=2:duration=first[aout]",
         "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac",
         "-shortest",
         output_path],
        capture_output=True, text=True, timeout=120,
    )

    Path(ambient_path).unlink(missing_ok=True)

    if result.returncode == 0 and Path(output_path).exists():
        return output_path

    # If everything fails, copy original
    import shutil
    shutil.copy(video_path, output_path)
    return output_path
