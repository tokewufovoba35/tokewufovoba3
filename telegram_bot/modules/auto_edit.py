"""
Auto-edit pipeline — one command to fully edit a raw video like a pro editor.

Pipeline steps:
1. Remove silence (dead air, long pauses)
2. Add transitions between remaining segments
3. Color grade (cinematic by default)
4. Add background music (if available)
5. Add intro/outro graphics (if title provided)
6. Format for target platform
"""

import logging
from pathlib import Path
from dataclasses import dataclass, field

from modules.clipper import get_video_duration
from modules.silence import remove_silence, get_speaking_segments
from modules.transitions import join_segments_with_transitions
from modules.effects import build_color_grade, build_enhance
from modules.audio import add_background_music, list_music
from modules.graphics import add_animated_intro, add_end_screen, add_progress_bar

logger = logging.getLogger(__name__)


@dataclass
class EditConfig:
    """Configuration for the auto-edit pipeline."""
    # Silence removal
    remove_silence: bool = True
    silence_threshold_db: float = -30.0
    min_silence_duration: float = 0.7
    silence_padding: float = 0.15

    # Transitions
    add_transitions: bool = True
    transition_style: str = "smooth"
    transition_duration: float = 0.4

    # Color grading
    color_grade: str = "cinematic"

    # Music
    add_music: bool = True
    music_volume: float = 0.25

    # Graphics
    intro_title: str = ""
    intro_subtitle: str = ""
    add_end_screen: bool = True
    end_text: str = "Thanks for watching!"
    end_subtext: str = "Like & Subscribe"

    # Platform
    platform: str = ""  # empty = keep original format

    # Quality
    preset: str = "ultrafast"
    crf: int = 23


def auto_edit(video_path: str, output_path: str,
              config: EditConfig | None = None,
              progress_callback=None) -> str:
    """Run the full auto-edit pipeline on a video.
    
    Args:
        video_path: Input video path
        output_path: Output video path
        config: Edit configuration (uses defaults if None)
        progress_callback: Optional async callback(step, total, message)
    
    Returns:
        Path to the edited video
    """
    if config is None:
        config = EditConfig()

    work_dir = Path(output_path).parent
    stem = Path(video_path).stem
    current_path = video_path
    step = 0
    total_steps = sum([
        config.remove_silence,
        config.add_transitions,
        bool(config.color_grade),
        config.add_music,
        bool(config.intro_title),
        config.add_end_screen,
    ])

    import subprocess

    def _log_step(msg: str):
        nonlocal step
        step += 1
        logger.info(f"[Auto-Edit {step}/{total_steps}] {msg}")
        if progress_callback:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(progress_callback(step, total_steps, msg))
            except RuntimeError:
                pass

    # Step 1: Remove silence
    if config.remove_silence:
        _log_step("Removing silence...")
        try:
            silence_output = str(work_dir / f"{stem}_desilenced.mp4")
            remove_silence(
                current_path, silence_output,
                threshold_db=config.silence_threshold_db,
                min_silence=config.min_silence_duration,
                padding=config.silence_padding,
            )
            if Path(silence_output).exists():
                current_path = silence_output
        except Exception as e:
            logger.warning(f"Silence removal failed (continuing): {e}")

    # Step 2: Color grade
    if config.color_grade:
        _log_step(f"Applying {config.color_grade} color grade...")
        try:
            color_output = str(work_dir / f"{stem}_colored.mp4")
            vf = build_color_grade(config.color_grade)
            enhance_filters = build_enhance()
            all_filters = [vf] + enhance_filters

            result = subprocess.run(
                ["ffmpeg", "-y", "-threads", "0", "-i", current_path,
                 "-vf", ",".join(all_filters),
                 "-c:v", "libx264", "-preset", config.preset,
                 "-crf", str(config.crf),
                 "-c:a", "aac",
                 color_output],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0 and Path(color_output).exists():
                current_path = color_output
        except Exception as e:
            logger.warning(f"Color grading failed (continuing): {e}")

    # Step 3: Add background music
    if config.add_music:
        _log_step("Adding background music...")
        try:
            music_files = list_music()
            if music_files:
                music = music_files[0]  # Use first available track
                music_output = str(work_dir / f"{stem}_music.mp4")
                add_background_music(
                    current_path, music.path, music_output,
                    volume=config.music_volume,
                )
                if Path(music_output).exists():
                    current_path = music_output
            else:
                logger.info("No music in library — skipping")
        except Exception as e:
            logger.warning(f"Music addition failed (continuing): {e}")

    # Step 4: Add intro
    if config.intro_title:
        _log_step("Adding intro...")
        try:
            intro_output = str(work_dir / f"{stem}_intro.mp4")
            add_animated_intro(
                current_path, intro_output,
                title=config.intro_title,
                subtitle=config.intro_subtitle,
                duration=3.0,
                style="fade",
            )
            if Path(intro_output).exists():
                current_path = intro_output
        except Exception as e:
            logger.warning(f"Intro failed (continuing): {e}")

    # Step 5: Add end screen
    if config.add_end_screen:
        _log_step("Adding end screen...")
        try:
            end_output = str(work_dir / f"{stem}_end.mp4")
            add_end_screen(
                current_path, end_output,
                text=config.end_text,
                subtext=config.end_subtext,
            )
            if Path(end_output).exists():
                current_path = end_output
        except Exception as e:
            logger.warning(f"End screen failed (continuing): {e}")

    # Step 6: Platform formatting
    if config.platform:
        _log_step(f"Formatting for {config.platform}...")
        from modules.effects import build_platform_format
        from modules.nlp import PLATFORM_KEYWORDS

        platform_settings = PLATFORM_KEYWORDS.get(config.platform, {})
        if platform_settings:
            try:
                platform_output = str(work_dir / f"{stem}_platform.mp4")
                filters = build_platform_format(platform_settings)
                result = subprocess.run(
                    ["ffmpeg", "-y", "-threads", "0", "-i", current_path,
                     "-vf", ",".join(filters),
                     "-c:v", "libx264", "-preset", config.preset,
                     "-c:a", "aac",
                     platform_output],
                    capture_output=True, text=True, timeout=180,
                )
                if result.returncode == 0 and Path(platform_output).exists():
                    current_path = platform_output

                # Enforce max duration
                max_dur = platform_settings.get("max_duration")
                if max_dur:
                    duration = get_video_duration(current_path)
                    if duration > max_dur:
                        trimmed = str(work_dir / f"{stem}_trimmed.mp4")
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", current_path,
                             "-t", str(max_dur), "-c", "copy", trimmed],
                            capture_output=True, text=True, timeout=60,
                        )
                        if Path(trimmed).exists():
                            current_path = trimmed
            except Exception as e:
                logger.warning(f"Platform formatting failed (continuing): {e}")

    # Move final result to output path
    if current_path != output_path:
        import shutil
        shutil.copy(current_path, output_path)

    # Clean up intermediate files
    for f in work_dir.glob(f"{stem}_*"):
        if str(f) != output_path and f.suffix in (".mp4", ".txt"):
            f.unlink(missing_ok=True)

    return output_path


def parse_auto_edit_config(instruction: str) -> EditConfig:
    """Parse natural language into an auto-edit config."""
    text = instruction.lower()
    config = EditConfig()

    # Silence removal preferences
    if "keep silence" in text or "don't remove silence" in text:
        config.remove_silence = False
    if "aggressive" in text:
        config.silence_threshold_db = -25.0
        config.min_silence_duration = 0.3

    # Color preferences
    from modules.nlp import COLOR_KEYWORDS
    for keyword, style in COLOR_KEYWORDS.items():
        if keyword in text:
            config.color_grade = style
            break

    # Music
    if "no music" in text or "without music" in text:
        config.add_music = False

    # Platform
    from modules.nlp import PLATFORM_KEYWORDS
    for platform in PLATFORM_KEYWORDS:
        if platform in text:
            config.platform = platform
            break

    # Graphics
    if "no intro" in text:
        config.intro_title = ""
    if "no end" in text or "no outro" in text:
        config.add_end_screen = False

    # Transitions
    if "no transition" in text:
        config.add_transitions = False
    for style in ["smooth", "dynamic", "cinematic", "energetic", "minimal", "creative"]:
        if style in text:
            config.transition_style = style
            break

    return config
