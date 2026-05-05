"""
Telegram Bot for video-use — Edit videos directly from Telegram.

Commands:
    /start - Welcome message and usage instructions
    /help  - Show available commands and editing options
    /status - Check if ffmpeg and dependencies are available

Usage:
    1. Send a video file to the bot
    2. Reply to the video with an editing command, e.g.:
       - "trim 0:10 to 0:30"
       - "compress"
       - "extract audio"
       - "speed 2x"
       - "resize 720p"
       - "rotate 90"
       - "gif 0:05 to 0:10"
"""

import os
import sys
import logging
import subprocess
import shutil
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WORK_DIR = Path(os.environ.get("VIDEO_WORK_DIR", os.path.expanduser("~/videos/telegram_bot")))
WORK_DIR.mkdir(parents=True, exist_ok=True)


def parse_time(time_str: str) -> str:
    """Parse time string to ffmpeg-compatible format."""
    time_str = time_str.strip()
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:
            return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        elif len(parts) == 3:
            return time_str
    try:
        seconds = int(time_str)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except ValueError:
        return time_str


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    """Run an ffmpeg command and return the result."""
    cmd = ["ffmpeg", "-y"] + args
    logger.info(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    await update.message.reply_text(
        "🎬 *Video Editor Bot*\n\n"
        "Send me a video and I'll edit it for you!\n\n"
        "*How to use:*\n"
        "1. Send a video file\n"
        "2. Reply to it with a command:\n\n"
        "• `trim 0:10 to 0:30` — Cut a segment\n"
        "• `compress` — Reduce file size\n"
        "• `extract audio` — Get audio as MP3\n"
        "• `speed 2x` — Change playback speed\n"
        "• `resize 720p` — Scale to resolution\n"
        "• `rotate 90` — Rotate video\n"
        "• `gif 0:05 to 0:10` — Convert segment to GIF\n"
        "• `mute` — Remove audio\n"
        "• `reverse` — Reverse the video\n\n"
        "Type /help for more details.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information."""
    await update.message.reply_text(
        "*Available Commands:*\n\n"
        "• `trim <start> to <end>` — Extract a segment\n"
        "  Example: `trim 0:10 to 0:30`\n\n"
        "• `compress` — Compress video (reduce bitrate)\n"
        "  Options: `compress low`, `compress medium`, `compress high`\n\n"
        "• `extract audio` — Extract audio track as MP3\n\n"
        "• `speed <multiplier>` — Change speed\n"
        "  Example: `speed 2x`, `speed 0.5x`\n\n"
        "• `resize <resolution>` — Scale video\n"
        "  Options: `resize 480p`, `resize 720p`, `resize 1080p`\n\n"
        "• `rotate <degrees>` — Rotate video\n"
        "  Options: `rotate 90`, `rotate 180`, `rotate 270`\n\n"
        "• `gif <start> to <end>` — Convert to GIF\n"
        "  Example: `gif 0:02 to 0:07`\n\n"
        "• `mute` — Remove audio track\n\n"
        "• `reverse` — Reverse the video\n\n"
        "• `thumbnail <time>` — Extract frame as image\n"
        "  Example: `thumbnail 0:05`\n\n"
        "*Tips:*\n"
        "- Time format: `M:SS` or `H:MM:SS` or seconds\n"
        "- Send video first, then reply with command\n"
        "- Supported: MP4, MOV, AVI, MKV, WebM",
        parse_mode="Markdown",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check system status."""
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    ffprobe_ok = shutil.which("ffprobe") is not None

    status_text = (
        f"*System Status:*\n"
        f"• ffmpeg: {'available' if ffmpeg_ok else 'NOT FOUND'}\n"
        f"• ffprobe: {'available' if ffprobe_ok else 'NOT FOUND'}\n"
        f"• Work directory: `{WORK_DIR}`\n"
        f"• Disk free: {_get_disk_free()}\n"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")


def _get_disk_free() -> str:
    """Get free disk space."""
    try:
        result = subprocess.run(
            ["df", "-h", str(WORK_DIR)], capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            return f"{parts[3]} available"
    except Exception:
        pass
    return "unknown"


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming video files — download and store for editing."""
    message = update.message
    video = message.video or message.document

    if not video:
        return

    await message.reply_text("📥 Downloading video...")

    file = await context.bot.get_file(video.file_id)
    file_ext = ".mp4"
    if video.file_name:
        file_ext = Path(video.file_name).suffix or ".mp4"

    video_path = WORK_DIR / f"{video.file_unique_id}{file_ext}"
    await file.download_to_drive(str(video_path))

    context.user_data["last_video"] = str(video_path)
    file_size_mb = video_path.stat().st_size / (1024 * 1024)

    await message.reply_text(
        f"Video saved ({file_size_mb:.1f} MB).\n\n"
        f"Now reply with an editing command, e.g.:\n"
        f"• `trim 0:10 to 0:30`\n"
        f"• `compress`\n"
        f"• `speed 2x`\n\n"
        f"Type /help to see all commands.",
        parse_mode="Markdown",
    )


async def handle_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process text messages as editing commands."""
    message = update.message
    text = message.text.strip().lower()

    # Check if replying to a video or if we have a stored video
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
            "No video found. Please send a video first, then reply with a command."
        )
        return

    await message.reply_text("⚙️ Processing...")

    try:
        output_path = await process_command(text, video_path)
        if output_path and Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            if output_path.endswith((".mp3", ".wav", ".ogg")):
                await message.reply_audio(audio=open(output_path, "rb"))
            elif output_path.endswith(".gif"):
                await message.reply_animation(animation=open(output_path, "rb"))
            elif output_path.endswith((".jpg", ".png")):
                await message.reply_photo(photo=open(output_path, "rb"))
            elif file_size > 50 * 1024 * 1024:
                await message.reply_text(
                    f"Output file is too large for Telegram ({file_size / (1024*1024):.1f} MB > 50 MB limit).\n"
                    f"Try `compress` first or trim a shorter segment."
                )
            else:
                await message.reply_video(video=open(output_path, "rb"))
            # Clean up output
            os.remove(output_path)
        else:
            await message.reply_text("Something went wrong — no output file was generated.")
    except TimeoutError:
        await message.reply_text("Processing timed out. Try a shorter video or simpler operation.")
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        await message.reply_text(f"Error: {str(e)}")


async def process_command(command: str, video_path: str) -> str | None:
    """Parse and execute an editing command. Returns output file path."""
    input_path = video_path
    stem = Path(video_path).stem
    ext = Path(video_path).suffix

    if command.startswith("trim"):
        # trim 0:10 to 0:30
        parts = command.replace("trim", "").strip().split("to")
        if len(parts) != 2:
            raise ValueError("Usage: trim <start> to <end> (e.g. trim 0:10 to 0:30)")
        start = parse_time(parts[0])
        end = parse_time(parts[1])
        output = str(WORK_DIR / f"{stem}_trimmed{ext}")
        result = run_ffmpeg(["-i", input_path, "-ss", start, "-to", end, "-c", "copy", output])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command.startswith("compress"):
        quality = "medium"
        if "low" in command:
            quality = "low"
        elif "high" in command:
            quality = "high"
        crf = {"low": "32", "medium": "28", "high": "23"}[quality]
        output = str(WORK_DIR / f"{stem}_compressed{ext}")
        result = run_ffmpeg([
            "-i", input_path, "-vcodec", "libx264", "-crf", crf,
            "-preset", "fast", "-acodec", "aac", "-b:a", "128k", output,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command in ("extract audio", "audio", "extract_audio"):
        output = str(WORK_DIR / f"{stem}.mp3")
        result = run_ffmpeg(["-i", input_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command.startswith("speed"):
        multiplier = command.replace("speed", "").replace("x", "").strip()
        try:
            speed = float(multiplier)
        except ValueError:
            raise ValueError("Usage: speed <multiplier> (e.g. speed 2x)")
        if speed <= 0 or speed > 10:
            raise ValueError("Speed must be between 0.1 and 10")
        video_filter = f"setpts={1/speed}*PTS"
        audio_filter = f"atempo={speed}" if 0.5 <= speed <= 2.0 else f"atempo={min(2.0, speed)}"
        output = str(WORK_DIR / f"{stem}_speed{ext}")
        result = run_ffmpeg([
            "-i", input_path, "-filter:v", video_filter,
            "-filter:a", audio_filter, output,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command.startswith("resize"):
        res = command.replace("resize", "").strip().replace("p", "")
        try:
            height = int(res)
        except ValueError:
            raise ValueError("Usage: resize <resolution> (e.g. resize 720p)")
        output = str(WORK_DIR / f"{stem}_{height}p{ext}")
        result = run_ffmpeg([
            "-i", input_path, "-vf", f"scale=-2:{height}",
            "-c:a", "copy", output,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command.startswith("rotate"):
        degrees = command.replace("rotate", "").strip()
        transpose_map = {"90": "1", "180": "2,transpose=2", "270": "2"}
        if degrees not in transpose_map:
            raise ValueError("Usage: rotate 90, rotate 180, or rotate 270")
        output = str(WORK_DIR / f"{stem}_rotated{ext}")
        result = run_ffmpeg([
            "-i", input_path, "-vf", f"transpose={transpose_map[degrees]}",
            "-c:a", "copy", output,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command.startswith("gif"):
        parts = command.replace("gif", "").strip().split("to")
        if len(parts) != 2:
            raise ValueError("Usage: gif <start> to <end> (e.g. gif 0:02 to 0:07)")
        start = parse_time(parts[0])
        end = parse_time(parts[1])
        output = str(WORK_DIR / f"{stem}.gif")
        result = run_ffmpeg([
            "-i", input_path, "-ss", start, "-to", end,
            "-vf", "fps=15,scale=480:-1:flags=lanczos",
            "-gifflags", "+transdiff", output,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command in ("mute", "remove audio", "no audio"):
        output = str(WORK_DIR / f"{stem}_muted{ext}")
        result = run_ffmpeg(["-i", input_path, "-an", "-c:v", "copy", output])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command == "reverse":
        output = str(WORK_DIR / f"{stem}_reversed{ext}")
        result = run_ffmpeg(["-i", input_path, "-vf", "reverse", "-af", "areverse", output])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    elif command.startswith("thumbnail"):
        time_str = command.replace("thumbnail", "").strip() or "0:00"
        time_pos = parse_time(time_str)
        output = str(WORK_DIR / f"{stem}_thumb.jpg")
        result = run_ffmpeg([
            "-i", input_path, "-ss", time_pos, "-vframes", "1", output,
        ])
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
        return output

    else:
        raise ValueError(
            f"Unknown command: '{command}'\n"
            "Available: trim, compress, extract audio, speed, resize, rotate, gif, mute, reverse, thumbnail\n"
            "Type /help for details."
        )


def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        print("Set it with: export TELEGRAM_BOT_TOKEN='your-bot-token'")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("Warning: ffmpeg not found in PATH. Video processing will fail.")
        print("Install with: pkg install ffmpeg (Termux) or apt install ffmpeg (Linux)")

    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))

    # Video/document handler
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    # Text handler for editing commands
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_command))

    print("Bot started! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
