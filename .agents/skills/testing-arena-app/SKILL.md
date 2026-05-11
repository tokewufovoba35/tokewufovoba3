---
name: testing-arena-app
description: Test the Arena chat app frontend end-to-end. Use when verifying UI, chat, sidebar, or PWA changes.
---

# Testing the Arena Chat App

## Overview
The Arena chat app is a static HTML/CSS/JS frontend with no backend. It uses canned demo responses.

## Deployment
The `web/` directory can be deployed as a static frontend:
```bash
# Deploy to devinapps.com
deploy frontend web/

# Or serve locally
cd web && python3 -m http.server 8000
```

The standalone `arena_app.html` can also be opened directly in a browser but won't have PWA features (service worker, manifest).

## Key Test Areas

### 1. Welcome State
- Navigate to the app URL
- Verify: "A" gradient logo, "Experience the frontier" headline, 4 suggestion cards, sidebar with chat history, composer with "Message Arena..." placeholder
- Send button should be grey/disabled when input is empty

### 2. Send Button Enable/Disable
- Type text in composer → send button turns white (enabled)
- Clear text → send button returns to grey (disabled)
- This is driven by `toggleSend()` in the JS which checks `input.value.trim().length`

### 3. Chat Send/Receive
- Type a message and press Enter (or click send button)
- Welcome state should disappear
- User message appears right-aligned in dark bubble with "U" avatar
- Bot shows typing dots for ~700ms, then streams a canned response character-by-character
- Input clears and send button returns to disabled
- Shift+Enter should insert a newline (not send)

### 4. Suggestion Cards
- Click any of the 4 suggestion cards on the welcome screen
- Each card has a preset message (check the `quick()` onclick handlers in index.html)
- The preset text should appear as a user message, followed by a bot response

### 5. Sidebar Toggle
- Click the panel icon in the sidebar header to collapse
- Sidebar slides left, main content goes full-width
- Click the hamburger menu icon in the top bar to expand
- All sidebar content should reappear (Arena branding, buttons, chat list, user row)

## Android Project
The `android/` directory is a Kotlin WebView wrapper. Testing requires Android Studio with AGP 8.5+. Build with `./gradlew assembleDebug` from the `android/` directory.

## Notes
- No authentication or API keys needed — all responses are canned/demo
- The app is mobile responsive — sidebar uses absolute positioning on narrow viewports
- PWA features (service worker, manifest) only work when served over HTTPS or localhost
- The `newChat()` function does `location.reload()` to reset state
