# Pro Video Editor Telegram Bot

An AI-powered Telegram bot that edits videos like a professional. Just describe what you want in plain English — no need to memorize commands.

## Features

### 🎬 Natural Language Editing
Just tell the bot what you want:
- *"Make this into a TikTok clip"*
- *"Add slow motion and cinematic color"*
- *"Clip the highlights for YouTube Shorts"*
- *"Make it moody with film grain"*

### ✂️ Smart Clipping
- **Auto-clip highlights** — Detects interesting moments using scene detection
- **Platform-ready clips** — Automatically formats for TikTok (9:16, 60s), YouTube Shorts, Reels
- **Manual trim** — Precise cuts with timestamps

### 🎨 Pro Effects
- Zoom in/out (Ken Burns)
- Speed ramp / slow motion
- Fade in/out, crossfade
- Glitch, camera shake, flash
- Film grain, vignette, letterbox
- Blur, cinematic look

### 🎨 Color Grading
Warm, cool, vintage, cinematic, dramatic, moody, neon, pastel, sepia, B&W, high contrast, saturated, and more.

### 🎵 Music & SFX
- Upload your own music and sound effects
- Auto-loop music to match video length
- Mix music under original audio
- Add SFX at specific timestamps

### 📱 Platform Formatting
- **TikTok** — 9:16, 1080x1920, max 60s
- **YouTube Shorts** — 9:16, max 60s
- **Instagram Reels** — 9:16, max 90s
- **YouTube** — 16:9, 1920x1080

### 📝 Text & Captions
- Text overlays with custom positioning
- Auto-caption support (placeholder)

### 🔧 Utilities
- Compress, resize, rotate, reverse, mute, extract audio, enhance

## Setup on Termux (Android)

### 1. Install dependencies

```bash
pkg install -y python ffmpeg
pip install -r requirements.txt
```

### 2. Create a bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow the prompts to name your bot
4. Copy the token BotFather gives you

### 3. Set your token

```bash
export TELEGRAM_BOT_TOKEN="paste-your-token-here"
```

To persist across sessions:

```bash
echo 'export TELEGRAM_BOT_TOKEN="paste-your-token-here"' >> ~/.bashrc
```

### 4. Run the bot

```bash
cd telegram_bot
python bot.py
```

Keep Termux running: `termux-wake-lock`

## Setup on Linux/Desktop

```bash
sudo apt install -y ffmpeg
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token"
python bot.py
```

## Usage

1. Open your bot in Telegram
2. Send `/start` for the welcome guide
3. **Send a video** — the bot stores it for editing
4. **Tell it what to do** — use plain English!

### Examples

| You say | What happens |
|---------|-------------|
| `trim 0:10 to 0:30` | Cuts that segment |
| `make this a TikTok` | Crops 9:16, clips to 60s |
| `add slow motion and cinematic color` | 0.5x speed + cinematic grading |
| `clip the highlights` | Auto-detects best moments |
| `speed 2x with warm filter` | Speeds up + warm color grade |
| `compress` | Reduces file size |
| `add background music` | Mixes in your uploaded music |

### Music & SFX Library

Upload audio files to build your personal library:
- Send audio with caption `music: Song Name` → saved as music
- Send audio with caption `sfx: Whoosh` → saved as SFX
- Use `/music` and `/sfx` to see your library
- Say "add background music" or "add sfx" to use them

### Chaining Edits

Each edit's output becomes the input for the next command. This means you can:
1. Send a video
2. Say "trim 0:10 to 0:30"
3. Then say "add cinematic color and zoom"
4. Then say "format for TikTok"

Each step builds on the previous result!

## Running in Background (Termux)

```bash
termux-wake-lock
nohup python bot.py > bot.log 2>&1 &
```

To stop: `pkill -f "python bot.py"`

## Architecture

```
telegram_bot/
├── bot.py              # Main bot (handlers, orchestration)
├── modules/
│   ├── nlp.py          # Natural language parsing (no API needed)
│   ├── effects.py      # FFmpeg filter chain builder
│   ├── clipper.py      # Scene detection & auto-clipping
│   └── audio.py        # Music/SFX mixing
├── requirements.txt
└── .env.example
```

## Limits

- Telegram file limit: 50 MB upload / 20 MB download via bot API
- For larger files, compress first or use Telegram's Local Bot API
- Very long videos may timeout during processing
- Auto-captions require a speech-to-text API (placeholder for now)
