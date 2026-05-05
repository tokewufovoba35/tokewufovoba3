# Termux Setup Guide for video-use (Android)

A complete step-by-step guide to setting up [video-use](https://github.com/browser-use/video-use) on Android using Termux.

---

## Step 1 — Install Termux

Download **Termux** from **F-Droid** (not Play Store — the Play Store version is outdated and broken):

https://f-droid.org/en/packages/com.termux/

## Step 2 — Update Termux packages

Open Termux and run:

```bash
pkg update && pkg upgrade -y
```

Type `y` if it asks you to confirm anything.

## Step 3 — Install required tools

```bash
pkg install -y python git ffmpeg
```

This installs Python 3, Git, and FFmpeg (the video processing engine).

## Step 4 — Install optional tools

```bash
pip install yt-dlp
```

Only needed if you want to download videos from YouTube/other sites.

## Step 5 — Allow Termux to access your phone storage

```bash
termux-setup-storage
```

Tap **Allow** when the permission popup appears. This creates a `~/storage/` folder linked to your phone's files.

## Step 6 — Clone video-use

```bash
mkdir -p ~/Developer
git clone https://github.com/browser-use/video-use ~/Developer/video-use
cd ~/Developer/video-use
```

## Step 7 — Install Python dependencies

```bash
pip install -e .
```

This installs: `requests`, `librosa`, `matplotlib`, `pillow`, `numpy`.

> ⚠️ **Note:** `librosa` and `numpy` may take a while to compile on your phone (10-20 min). If `librosa` fails, try:

```bash
pkg install -y build-essential libopenblas
pip install numpy
pip install librosa
```

## Step 8 — Install Claude Code

```bash
pkg install -y nodejs
npm install -g @anthropic-ai/claude-code
```

## Step 9 — Set up your API keys

### Anthropic API key

For Claude Code — get one at https://console.anthropic.com:

```bash
export ANTHROPIC_API_KEY="paste-your-key-here"
```

### ElevenLabs API key

For transcription — get one at https://elevenlabs.io/app/settings/api-keys:

```bash
printf 'ELEVENLABS_API_KEY=paste-your-key-here\n' > ~/Developer/video-use/.env
chmod 600 ~/Developer/video-use/.env
```

### Persist the Anthropic key across Termux sessions

```bash
echo 'export ANTHROPIC_API_KEY="paste-your-key-here"' >> ~/.bashrc
```

## Step 10 — Register the skill with Claude Code

```bash
mkdir -p ~/.claude/skills
ln -sfn ~/Developer/video-use ~/.claude/skills/video-use
```

## Step 11 — Verify everything works

```bash
python ~/Developer/video-use/helpers/timeline_view.py --help
ffprobe -version | head -1
```

If both commands run without errors, you're good!

## Step 12 — Edit your first video!

1. Copy your video files to an accessible folder:

```bash
mkdir -p ~/videos/my-project
cp ~/storage/shared/DCIM/Camera/my-video.mp4 ~/videos/my-project/
```

2. Go to that folder and start Claude Code:

```bash
cd ~/videos/my-project
claude
```

3. Tell it what you want:

> "edit these into a final publish-ready video"

Your output will appear in `~/videos/my-project/edit/final.mp4`.
