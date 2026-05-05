# Telegram Video Editor Bot

A Telegram bot that lets you edit videos directly from your Telegram app using ffmpeg.

## Features

- **Trim** — Cut a segment from your video
- **Compress** — Reduce file size (low/medium/high quality)
- **Extract audio** — Get the audio track as MP3
- **Speed** — Change playback speed (0.1x to 10x)
- **Resize** — Scale to 480p, 720p, or 1080p
- **Rotate** — Rotate 90°, 180°, or 270°
- **GIF** — Convert a segment to animated GIF
- **Mute** — Remove audio track
- **Reverse** — Reverse the video
- **Thumbnail** — Extract a frame as an image

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

To make it persist across sessions:

```bash
echo 'export TELEGRAM_BOT_TOKEN="paste-your-token-here"' >> ~/.bashrc
```

### 4. Run the bot

```bash
python bot.py
```

The bot will start polling for messages. Keep Termux running (use `termux-wake-lock` to prevent Android from killing it).

## Setup on Linux/Desktop

```bash
# Install ffmpeg
sudo apt install -y ffmpeg

# Install Python dependencies
pip install -r requirements.txt

# Set token and run
export TELEGRAM_BOT_TOKEN="your-token"
python bot.py
```

## Usage

1. Open your bot in Telegram (search for the username you gave it)
2. Send `/start` to see the welcome message
3. Send a video file to the bot
4. Reply to the video with a command:
   - `trim 0:10 to 0:30`
   - `compress`
   - `speed 2x`
   - `resize 720p`
5. The bot will process and send back the result

## Running in Background (Termux)

To keep the bot running when you close Termux:

```bash
termux-wake-lock
nohup python bot.py > bot.log 2>&1 &
```

To stop it:

```bash
pkill -f "python bot.py"
```

## Limits

- Telegram file size limit: 50 MB (upload) / 20 MB (download via bot API)
- For larger files, use the Local Bot API server or compress first
- Very long videos may timeout during processing
