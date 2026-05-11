# Arena Chat App

A polished chat interface inspired by ChatGPT, built as a single self-contained HTML file with no build step required. Includes a full Android Studio project for native deployment.

## Project Structure

```
├── arena_app.html              # Standalone single-file version (open directly in browser)
├── web/                        # PWA-ready web app (deploy to any static host)
│   ├── index.html
│   ├── manifest.webmanifest
│   ├── sw.js
│   ├── icon-192.png
│   └── icon-512.png
└── android/                    # Android Studio project (Kotlin + WebView)
    ├── build.gradle
    ├── settings.gradle
    ├── gradle.properties
    └── app/
        ├── build.gradle
        └── src/main/
            ├── AndroidManifest.xml
            ├── java/ai/arena/app/MainActivity.kt
            ├── res/values/{strings,styles}.xml
            ├── res/mipmap-xxxhdpi/ic_launcher.png
            └── assets/index.html
```

## Features

- **Dark theme** — Clean palette (#0d0d0d / #171717 / #2f2f2f), Inter font, 14px radius
- **Collapsible sidebar** — New chat, Search, Leaderboard, grouped history (Today / Yesterday / Previous 7 days)
- **Model picker** — "Arena Auto" badge + "Battle Mode" pill
- **Welcome state** — Gradient headline "Experience the frontier" + 4 suggestion cards
- **Chat bubbles** — User messages right-aligned, assistant responses with gradient avatar
- **Composer** — Rounded pill with attach / voice / send, auto-grow textarea, Enter to send
- **Animations** — Fade-in messages, 3-dot typing indicator, streamed character-by-character responses
- **Mobile responsive** — Sidebar slides off, suggestions stack
- **PWA support** — Service worker + web manifest for installable app
- **No dependencies** — Pure HTML/CSS/JS

## Quick Start

### Web (no build)
```bash
# Open directly
open arena_app.html

# Or serve the PWA
cd web && python3 -m http.server 8000
```

### Android
1. Open the `android/` folder in Android Studio (Hedgehog+)
2. Click Run, or build from CLI:
   ```bash
   cd android && ./gradlew assembleDebug
   ```
3. APK at `app/build/outputs/apk/debug/app-debug.apk`

### PWA Install (no build)
Host `web/` on any static server → open in Chrome on Android → Menu → "Add to Home screen"