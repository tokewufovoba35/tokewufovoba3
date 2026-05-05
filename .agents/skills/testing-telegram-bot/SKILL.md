---
name: testing-telegram-bot
description: Test the Telegram video editor bot end-to-end. Use when verifying bot startup, ffmpeg video processing commands, or Telegram API connectivity.
---

# Testing the Telegram Video Editor Bot

## Prerequisites

- `python-telegram-bot` installed (`pip install python-telegram-bot`)
- `ffmpeg` available in PATH
- A valid Telegram bot token (from @BotFather)

## Devin Secrets Needed

- `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather (format: `123456789:ABC...`)

## Test Methodology

### 1. Verify Bot API Connection

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" | python3 -m json.tool
```

Expect: `"ok": true` with the bot's username in the response.

### 2. Verify Bot Startup & Polling

```bash
TELEGRAM_BOT_TOKEN="$TOKEN" timeout 10 python3 telegram_bot/bot.py
```

Expect:
- "Bot started!" printed
- HTTP 200 for `getMe`, `deleteWebhook`, `getUpdates`
- "Application started" log message
- No errors or tracebacks

### 3. Test Video Processing Commands

Create a synthetic test video:

```bash
ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=25 -f lavfi -i sine=frequency=440:duration=5 -c:v libx264 -c:a aac -shortest test_video.mp4
```

Then test processing functions directly via Python:

```python
import asyncio, sys
sys.path.insert(0, 'telegram_bot')
from bot import process_command, WORK_DIR
WORK_DIR.mkdir(parents=True, exist_ok=True)
# Copy test_video.mp4 to WORK_DIR first
asyncio.run(process_command('trim 0:01 to 0:03', str(WORK_DIR / 'test_video.mp4')))
```

Commands to test and their assertions:
- `trim 0:01 to 0:03` → output duration ~2s
- `compress` → output size < original size
- `speed 2x` → output duration ~half of original
- `mute` → ffprobe shows only video stream, no audio
- `extract audio` → produces non-zero .mp3 file
- `thumbnail 0:02` → produces non-zero .jpg file
- `resize 480p` → ffprobe shows height=480

### 4. Test Error Handling

Verify these raise `ValueError` with helpful messages:
- Invalid command: `blahblah` → "Unknown command"
- Bad trim: `trim 0:10` (missing "to") → "Usage: trim"
- Bad speed: `speed abc` → "Usage: speed"
- Bad rotate: `rotate 45` → "Usage: rotate"

## Limitations

- Full Telegram message flow (sending video in chat → receiving edited result) requires logging into a Telegram account. If you don't have Telegram web access, test the processing functions directly and verify bot API connectivity separately.
- Telegram Bot API has a 20MB download limit and 50MB upload limit. Test with small files.
- The `reverse` command might be slow on large videos as it requires re-encoding the entire file.

## Tips

- Use `ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1` to check video duration
- Use `ffprobe -v quiet -show_entries stream=codec_type` to check which streams exist
- Use `ffprobe -v quiet -show_entries stream=height` to verify resolution
- The bot stores videos in `~/videos/telegram_bot/` by default (configurable via `VIDEO_WORK_DIR` env var)
