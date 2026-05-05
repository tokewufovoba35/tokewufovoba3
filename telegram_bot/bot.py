"""
Pro Video Editor Telegram Bot — Edit videos like a pro directly from Telegram.

Features:
    - Natural language editing commands (no need to memorize syntax)
    - Auto-clipping (finds highlights, cuts for TikTok/Shorts)
    - Background music & SFX (upload your own)
    - Pro effects (zoom, speed ramps, color grading, transitions)
    - Platform formatting (TikTok, YouTube Shorts, Reels)
    - Text overlays and captions

Commands:
    /start  - Welcome and usage guide
    /help   - Detailed command reference
    /music  - List your uploaded music files
    /sfx    - List your uploaded sound effects
    /status - Check system status
"""

import os
import sys
import logging
import subprocess
import shutil
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))
from modules.nlp import parse_instruction, describe_actions, EditAction
from modules.effects import (
    build_color_grade, build_enhance, build_fade_in, build_fade_out,
    build_film_grain, build_glitch, build_letterbox, build_platform_format,
    build_shake, build_text_overlay, build_vignette, build_zoom_in,
    build_zoom_out, build_blur, FilterChain,
)
from modules.clipper import (
    find_highlights, extract_clip, concatenate_clips, get_video_duration,
)
from modules.audio import (
    add_background_music, add_sfx_at_time, replace_audio,
    save_music, save_sfx, list_music, list_sfx,
    MUSIC_DIR, SFX_DIR,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WORK_DIR = Path(os.environ.get("VIDEO_WORK_DIR", os.path.expanduser("~/videos/telegram_bot")))
WORK_DIR.mkdir(parents=True, exist_ok=True)


def run_ffmpeg(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Run an ffmpeg command."""
    cmd = ["ffmpeg", "-y"] + args
    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def seconds_to_timecode(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    await update.message.reply_text(
        "🎬 *Pro Video Editor Bot*\n\n"
        "I'm your AI video editor. Just tell me what you want in plain English!\n\n"
        "*Quick Start:*\n"
        "1️⃣ Send me a video\n"
        "2️⃣ Tell me what to do:\n\n"
        "💬 *Examples:*\n"
        '• _"Make this into a TikTok clip"_\n'
        '• _"Add slow motion and cinematic color"_\n'
        '• _"Clip the highlights for YouTube Shorts"_\n'
        '• _"Trim from 0:10 to 0:30 and add zoom"_\n'
        '• _"Make it moody with film grain"_\n'
        '• _"Speed up 2x with a warm filter"_\n\n'
        "*Music & SFX:*\n"
        "• Send audio files labeled `music:` or `sfx:` to build your library\n"
        '• Then say _"add background music"_ on any video\n\n'
        "Type /help for the full feature list.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Full help."""
    await update.message.reply_text(
        "*📖 Full Feature List*\n\n"
        "*✂️ Trimming & Clipping:*\n"
        '• `trim 0:10 to 0:30` — Cut a segment\n'
        '• `clip the highlights` — Auto-find best moments\n'
        '• `make TikTok clips` — Auto-clip for TikTok (60s, 9:16)\n\n'
        "*🎨 Effects:*\n"
        "• `zoom in` / `zoom out` — Ken Burns effect\n"
        "• `slow motion` — 0.5x speed\n"
        "• `speed 2x` — Speed up\n"
        "• `speed ramp` — Dynamic speed changes\n"
        "• `fade in` / `fade out` — Fades\n"
        "• `glitch` — Glitch/datamosh\n"
        "• `shake` — Camera shake\n"
        "• `film grain` — Analog look\n"
        "• `letterbox` — Cinematic bars\n"
        "• `vignette` — Dark edges\n"
        "• `blur` — Gaussian blur\n\n"
        "*🎨 Color Grading:*\n"
        "• `warm` / `cool` / `vintage` / `cinematic`\n"
        "• `moody` / `dramatic` / `neon` / `pastel`\n"
        "• `black and white` / `sepia`\n"
        "• `high contrast` / `saturated`\n\n"
        "*🎵 Audio:*\n"
        '• `add background music` — Uses your uploaded music\n'
        '• `add sfx` — Add sound effects\n'
        '• `mute` — Remove all audio\n'
        '• `extract audio` — Get audio as MP3\n\n'
        "*📱 Platform Formatting:*\n"
        "• `for TikTok` — 9:16, 1080x1920, max 60s\n"
        "• `for YouTube Shorts` — 9:16, max 60s\n"
        "• `for Instagram Reels` — 9:16, max 90s\n"
        "• `for YouTube` — 16:9, 1920x1080\n\n"
        "*📝 Text:*\n"
        '• `add text "Your text here"` — Text overlay\n'
        "• `add captions` — Auto-generate subtitles\n\n"
        "*🔧 Utilities:*\n"
        "• `compress` — Reduce file size\n"
        "• `resize 720p` — Scale resolution\n"
        "• `rotate 90` — Rotate\n"
        "• `reverse` — Play backwards\n"
        "• `enhance` — Auto-improve quality\n\n"
        "*💡 Tips:*\n"
        "• Combine commands! _\"cinematic color with zoom and slow mo for TikTok\"_\n"
        "• Upload music: send audio with caption `music: Song Name`\n"
        "• Upload SFX: send audio with caption `sfx: Effect Name`",
        parse_mode="Markdown",
    )


async def music_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List uploaded music."""
    music_files = list_music()
    if not music_files:
        await update.message.reply_text(
            "🎵 *Your Music Library is empty*\n\n"
            "Upload audio files with the caption `music: Song Name` to add them.\n"
            "Supported: MP3, WAV, OGG, M4A, FLAC, AAC",
            parse_mode="Markdown",
        )
    else:
        lines = ["🎵 *Your Music Library:*\n"]
        for m in music_files:
            dur = seconds_to_timecode(m.duration)
            lines.append(f"• `{m.name}` ({dur})")
        lines.append(f"\n_{len(music_files)} track(s)_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def sfx_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List uploaded SFX."""
    sfx_files = list_sfx()
    if not sfx_files:
        await update.message.reply_text(
            "🔊 *Your SFX Library is empty*\n\n"
            "Upload audio files with the caption `sfx: Effect Name` to add them.\n"
            "Supported: MP3, WAV, OGG, M4A, FLAC, AAC",
            parse_mode="Markdown",
        )
    else:
        lines = ["🔊 *Your SFX Library:*\n"]
        for s in sfx_files:
            dur = f"{s.duration:.1f}s"
            lines.append(f"• `{s.name}` ({dur})")
        lines.append(f"\n_{len(sfx_files)} effect(s)_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """System status."""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None
    music_count = len(list_music())
    sfx_count = len(list_sfx())

    await update.message.reply_text(
        f"*System Status:*\n"
        f"• ffmpeg: {'✓' if ffmpeg_ok else '✗ NOT FOUND'}\n"
        f"• ffprobe: {'✓' if ffprobe_ok else '✗ NOT FOUND'}\n"
        f"• Music library: {music_count} track(s)\n"
        f"• SFX library: {sfx_count} effect(s)\n"
        f"• Work dir: `{WORK_DIR}`",
        parse_mode="Markdown",
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming video files."""
    message = update.message
    video = message.video or message.document

    if not video:
        return

    # Check if this is a video file
    if message.document:
        mime = message.document.mime_type or ""
        if not mime.startswith("video/"):
            return

    await message.reply_text("📥 Downloading video...")

    file = await context.bot.get_file(video.file_id)
    file_ext = ".mp4"
    if hasattr(video, "file_name") and video.file_name:
        file_ext = Path(video.file_name).suffix or ".mp4"

    video_path = WORK_DIR / f"{video.file_unique_id}{file_ext}"
    await file.download_to_drive(str(video_path))

    context.user_data["last_video"] = str(video_path)
    duration = get_video_duration(str(video_path))
    file_size_mb = video_path.stat().st_size / (1024 * 1024)

    # Check if there's a caption with editing instructions
    if message.caption:
        caption = message.caption.strip()
        if caption and not caption.startswith(("music:", "sfx:")):
            await message.reply_text(
                f"📹 Video received ({file_size_mb:.1f} MB, {seconds_to_timecode(duration)})\n"
                f"⚙️ Processing: _{caption}_",
                parse_mode="Markdown",
            )
            await execute_edit(message, context, caption, str(video_path))
            return

    await message.reply_text(
        f"📹 Video saved ({file_size_mb:.1f} MB, {seconds_to_timecode(duration)})\n\n"
        f"Now tell me what to do! Examples:\n"
        f'• _"Make this into a TikTok clip"_\n'
        f'• _"Add cinematic color and slow mo"_\n'
        f'• _"Clip the best moments"_\n'
        f'• _"Trim 0:10 to 0:30"_',
        parse_mode="Markdown",
    )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uploaded audio files (music/SFX)."""
    message = update.message
    audio = message.audio or message.voice or message.document

    if not audio:
        return

    # Check if document is audio
    if message.document:
        mime = message.document.mime_type or ""
        if not (mime.startswith("audio/") or mime in ("application/ogg",)):
            return

    caption = (message.caption or "").strip()

    # Determine if this is music or SFX
    if caption.lower().startswith("music:"):
        name = caption[6:].strip() or "untitled"
        asset_type = "music"
    elif caption.lower().startswith("sfx:"):
        name = caption[4:].strip() or "untitled"
        asset_type = "sfx"
    else:
        # Default: ask or store as music
        name = getattr(audio, "title", None) or getattr(audio, "file_name", "untitled")
        name = Path(name).stem
        asset_type = "music"

    await message.reply_text(f"📥 Saving {asset_type}: _{name}_...", parse_mode="Markdown")

    file = await context.bot.get_file(audio.file_id)
    file_ext = ".mp3"
    if hasattr(audio, "file_name") and audio.file_name:
        file_ext = Path(audio.file_name).suffix or ".mp3"

    temp_path = WORK_DIR / f"temp_audio{file_ext}"
    await file.download_to_drive(str(temp_path))

    if asset_type == "music":
        asset = save_music(str(temp_path), name)
        await message.reply_text(
            f"🎵 Music saved: *{asset.name}* ({seconds_to_timecode(asset.duration)})\n"
            f"Say _\"add background music\"_ on any video to use it!",
            parse_mode="Markdown",
        )
    else:
        asset = save_sfx(str(temp_path), name)
        await message.reply_text(
            f"🔊 SFX saved: *{asset.name}* ({asset.duration:.1f}s)\n"
            f"Say _\"add sfx\"_ on any video to use it!",
            parse_mode="Markdown",
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages as editing commands."""
    message = update.message
    text = message.text.strip()

    if not text:
        return

    # Find the video to edit
    video_path = None

    if message.reply_to_message:
        video_msg = message.reply_to_message
        video = video_msg.video or video_msg.document
        if video:
            file = await context.bot.get_file(video.file_id)
            file_ext = ".mp4"
            if hasattr(video, "file_name") and video.file_name:
                file_ext = Path(video.file_name).suffix or ".mp4"
            video_path = str(WORK_DIR / f"{video.file_unique_id}{file_ext}")
            if not Path(video_path).exists():
                await file.download_to_drive(video_path)

    if not video_path:
        video_path = context.user_data.get("last_video")

    if not video_path or not Path(video_path).exists():
        await message.reply_text(
            "📹 No video found. Send me a video first, then tell me how to edit it!"
        )
        return

    await execute_edit(message, context, text, video_path)


async def execute_edit(message, context: ContextTypes.DEFAULT_TYPE,
                       instruction: str, video_path: str) -> None:
    """Parse instruction and execute editing actions."""
    # Parse the instruction
    actions = parse_instruction(instruction)
    plan = describe_actions(actions)

    # Show the plan
    await message.reply_text(f"🎬 *Edit Plan:*\n{plan}\n\n⚙️ Processing...", parse_mode="Markdown")

    try:
        output_path = await process_actions(actions, video_path, context)

        if output_path and Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            if file_size > 50 * 1024 * 1024:
                await message.reply_text(
                    f"⚠️ Output is too large for Telegram ({file_size_mb:.1f} MB > 50 MB).\n"
                    f"Try: _\"compress\"_ or trim a shorter segment.",
                    parse_mode="Markdown",
                )
            elif output_path.endswith((".mp3", ".wav", ".ogg")):
                with open(output_path, "rb") as f:
                    await message.reply_audio(audio=f)
            elif output_path.endswith(".gif"):
                with open(output_path, "rb") as f:
                    await message.reply_animation(animation=f)
            elif output_path.endswith((".jpg", ".png")):
                with open(output_path, "rb") as f:
                    await message.reply_photo(photo=f)
            else:
                duration = get_video_duration(output_path)
                with open(output_path, "rb") as f:
                    await message.reply_video(
                        video=f,
                        caption=f"✅ Done! ({file_size_mb:.1f} MB, {seconds_to_timecode(duration)})",
                    )

            # Store output as new "last video" for chaining edits
            context.user_data["last_video"] = output_path
        else:
            await message.reply_text("❌ Something went wrong — no output generated.")

    except TimeoutError:
        await message.reply_text("⏰ Processing timed out. Try a shorter video or simpler edit.")
    except Exception as e:
        logger.error(f"Error processing: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")


async def process_actions(actions: list[EditAction], video_path: str,
                          context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Execute a list of editing actions on a video."""
    current_path = video_path
    stem = Path(video_path).stem
    ext = Path(video_path).suffix
    video_duration = get_video_duration(video_path)

    video_filters = []
    audio_filters = []
    need_reencode = False

    for action in actions:
        if action.action == "trim":
            start = action.params["start"]
            end = action.params["end"]
            output = str(WORK_DIR / f"{stem}_trimmed{ext}")
            result = run_ffmpeg([
                "-i", current_path,
                "-ss", str(start), "-to", str(end),
                "-c", "copy", output,
            ])
            if result.returncode != 0:
                raise RuntimeError(f"Trim failed: {result.stderr[-300:]}")
            current_path = output
            video_duration = end - start

        elif action.action == "auto_clip":
            max_clips = action.params.get("max_clips", 5)
            platform_actions = [a for a in actions if a.action == "format_platform"]
            max_dur = 60.0
            if platform_actions:
                max_dur = platform_actions[0].params.get("max_duration") or 60.0

            clips = find_highlights(current_path, max_clips=max_clips,
                                    clip_duration=min(15.0, max_dur / max_clips),
                                    max_total_duration=max_dur)

            if len(clips) == 1 and clips[0].start == 0:
                pass  # Video is already short enough
            else:
                clip_paths = []
                for i, clip in enumerate(clips):
                    clip_output = str(WORK_DIR / f"{stem}_clip{i}{ext}")
                    extract_clip(current_path, clip, clip_output)
                    clip_paths.append(clip_output)

                if len(clip_paths) > 1:
                    output = str(WORK_DIR / f"{stem}_clipped{ext}")
                    concatenate_clips(clip_paths, output)
                    current_path = output
                elif clip_paths:
                    current_path = clip_paths[0]

                video_duration = get_video_duration(current_path)

                # Clean up individual clips
                for cp in clip_paths:
                    if cp != current_path:
                        Path(cp).unlink(missing_ok=True)

        elif action.action == "format_platform":
            platform_filters = build_platform_format(action.params)
            video_filters.extend(platform_filters)
            need_reencode = True

            # Enforce max duration
            max_dur = action.params.get("max_duration")
            if max_dur and video_duration > max_dur:
                output = str(WORK_DIR / f"{stem}_dur{ext}")
                result = run_ffmpeg([
                    "-i", current_path,
                    "-t", str(max_dur),
                    "-c", "copy", output,
                ])
                if result.returncode == 0:
                    current_path = output
                    video_duration = max_dur

        elif action.action == "speed":
            mult = action.params["multiplier"]
            video_filters.append(f"setpts={1/mult}*PTS")
            if 0.5 <= mult <= 2.0:
                audio_filters.append(f"atempo={mult}")
            elif mult > 2.0:
                # Chain atempo filters (each max 2.0)
                remaining = mult
                while remaining > 2.0:
                    audio_filters.append("atempo=2.0")
                    remaining /= 2.0
                audio_filters.append(f"atempo={remaining}")
            else:
                remaining = mult
                while remaining < 0.5:
                    audio_filters.append("atempo=0.5")
                    remaining /= 0.5
                audio_filters.append(f"atempo={remaining}")
            need_reencode = True

        elif action.action == "effect":
            effect_type = action.params["type"]
            if effect_type == "zoom_in":
                video_filters.append(build_zoom_in(video_duration))
            elif effect_type == "zoom_out":
                video_filters.append(build_zoom_out(video_duration))
            elif effect_type == "fade_in":
                video_filters.append(build_fade_in(1.0))
            elif effect_type == "fade_out":
                video_filters.append(build_fade_out(1.0, video_duration))
            elif effect_type == "fade_in_out":
                video_filters.append(build_fade_in(1.0))
                video_filters.append(build_fade_out(1.0, video_duration))
            elif effect_type == "film_grain":
                video_filters.append(build_film_grain())
            elif effect_type == "vignette":
                video_filters.append(build_vignette())
            elif effect_type == "glitch":
                video_filters.append(build_glitch())
            elif effect_type == "shake":
                video_filters.append(build_shake())
            elif effect_type == "blur":
                video_filters.append(build_blur())
            elif effect_type == "letterbox":
                video_filters.append(build_letterbox())
            elif effect_type == "cinematic":
                video_filters.append(build_vignette())
                video_filters.append(build_film_grain())
            need_reencode = True

        elif action.action == "color_grade":
            video_filters.append(build_color_grade(action.params["style"]))
            need_reencode = True

        elif action.action == "text_overlay":
            video_filters.append(build_text_overlay(action.params["text"]))
            need_reencode = True

        elif action.action == "auto_captions":
            # Basic subtitle placeholder — would need speech-to-text in production
            video_filters.append(
                "drawtext=text='[Captions require speech-to-text API]'"
                ":fontsize=24:fontcolor=white:borderw=2:bordercolor=black"
                ":x=(w-text_w)/2:y=h-80"
            )
            need_reencode = True

        elif action.action == "enhance":
            video_filters.extend(build_enhance())
            need_reencode = True

        elif action.action == "compress":
            output = str(WORK_DIR / f"{stem}_compressed{ext}")
            result = run_ffmpeg([
                "-i", current_path,
                "-vcodec", "libx264", "-crf", "28",
                "-preset", "fast",
                "-acodec", "aac", "-b:a", "128k",
                output,
            ])
            if result.returncode != 0:
                raise RuntimeError(f"Compress failed: {result.stderr[-300:]}")
            current_path = output

        elif action.action == "reverse":
            output = str(WORK_DIR / f"{stem}_reversed{ext}")
            result = run_ffmpeg([
                "-i", current_path,
                "-vf", "reverse", "-af", "areverse",
                output,
            ])
            if result.returncode != 0:
                raise RuntimeError(f"Reverse failed: {result.stderr[-300:]}")
            current_path = output

        elif action.action == "mute":
            output = str(WORK_DIR / f"{stem}_muted{ext}")
            result = run_ffmpeg(["-i", current_path, "-an", "-c:v", "copy", output])
            if result.returncode != 0:
                raise RuntimeError(f"Mute failed: {result.stderr[-300:]}")
            current_path = output

        elif action.action == "resize":
            height = action.params["height"]
            video_filters.append(f"scale=-2:{height}")
            need_reencode = True

        elif action.action == "rotate":
            degrees = action.params["degrees"]
            transpose_map = {"90": "1", "180": "2,transpose=2", "270": "2"}
            t = transpose_map.get(str(degrees))
            if t:
                video_filters.append(f"transpose={t}")
                need_reencode = True

        elif action.action == "add_music":
            music_files = list_music()
            if music_files:
                # Use first available music file
                music = music_files[0]
                output = str(WORK_DIR / f"{stem}_music{ext}")
                add_background_music(current_path, music.path, output)
                current_path = output
            else:
                raise ValueError(
                    "No music in your library! Upload an audio file with caption "
                    "`music: Song Name` first."
                )

        elif action.action == "add_sfx":
            sfx_files = list_sfx()
            if sfx_files:
                sfx = sfx_files[0]
                output = str(WORK_DIR / f"{stem}_sfx{ext}")
                add_sfx_at_time(current_path, sfx.path, output, timestamp=0.0)
                current_path = output
            else:
                raise ValueError(
                    "No SFX in your library! Upload an audio file with caption "
                    "`sfx: Effect Name` first."
                )

        elif action.action == "unknown":
            raise ValueError(
                "I couldn't understand that instruction. Try something like:\n"
                '• "trim 0:10 to 0:30"\n'
                '• "make it cinematic for TikTok"\n'
                '• "add slow motion and zoom"\n'
                '• "clip the highlights"\n\n'
                "Type /help for the full list."
            )

    # Apply accumulated video/audio filters
    if need_reencode and (video_filters or audio_filters):
        output = str(WORK_DIR / f"{stem}_edited{ext}")
        cmd = ["-i", current_path]

        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])
        if audio_filters:
            cmd.extend(["-af", ",".join(audio_filters)])

        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
        if not audio_filters:
            cmd.extend(["-c:a", "aac"])
        cmd.append(output)

        result = run_ffmpeg(cmd, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Processing failed: {result.stderr[-500:]}")
        current_path = output

    return current_path


def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set.")
        print("Set it with: export TELEGRAM_BOT_TOKEN='your-token-from-botfather'")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("Warning: ffmpeg not found. Install with: pkg install ffmpeg (Termux)")

    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("music", music_command))
    application.add_handler(CommandHandler("sfx", sfx_command))
    application.add_handler(CommandHandler("status", status_command))

    # Video handler
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    # Audio handler (for music/SFX uploads)
    application.add_handler(MessageHandler(
        filters.AUDIO | filters.VOICE | filters.Document.AUDIO,
        handle_audio,
    ))

    # Text handler (editing instructions)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🎬 Pro Video Editor Bot started! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
