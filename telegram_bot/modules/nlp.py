"""
Natural Language Processing module for video editing commands.
Parses user instructions into structured editing actions without external API calls.
"""

import re
from dataclasses import dataclass, field
from modules.downloader import extract_urls


@dataclass
class EditAction:
    """A parsed editing action."""
    action: str
    params: dict = field(default_factory=dict)


# Time pattern: matches 0:10, 1:30, 00:01:30, 90s, 10sec, 2min, etc.
TIME_PATTERN = r"(\d{1,2}:\d{2}(?::\d{2})?|\d+\s*(?:s|sec|seconds?|m|min|minutes?|h|hours?)?)"

PLATFORM_KEYWORDS = {
    "tiktok": {"aspect": "9:16", "max_duration": 60, "resolution": "1080x1920"},
    "youtube shorts": {"aspect": "9:16", "max_duration": 60, "resolution": "1080x1920"},
    "youtube short": {"aspect": "9:16", "max_duration": 60, "resolution": "1080x1920"},
    "shorts": {"aspect": "9:16", "max_duration": 60, "resolution": "1080x1920"},
    "reels": {"aspect": "9:16", "max_duration": 90, "resolution": "1080x1920"},
    "instagram": {"aspect": "9:16", "max_duration": 90, "resolution": "1080x1920"},
    "youtube": {"aspect": "16:9", "max_duration": None, "resolution": "1920x1080"},
    "twitter": {"aspect": "16:9", "max_duration": 140, "resolution": "1920x1080"},
    "for x": {"aspect": "16:9", "max_duration": 140, "resolution": "1920x1080"},
}

EFFECT_KEYWORDS = {
    "zoom": "zoom_in",
    "zoom in": "zoom_in",
    "zoom out": "zoom_out",
    "ken burns": "ken_burns",
    "fast forward": "speed_up",
    "speed up": "speed_up",
    "speed ramp": "speed_ramp",
    "fade in": "fade_in",
    "fade out": "fade_out",
    "fade": "fade_in_out",

    "glitch": "glitch",
    "shake": "shake",
    "flash": "flash",
    "blur": "blur",
    "vignette": "vignette",
    "film grain": "film_grain",
    "grain": "film_grain",
    "letterbox": "letterbox",
    "black bars": "letterbox",
}

COLOR_KEYWORDS = {
    "warm": "warm",
    "cool": "cool",
    "cold": "cool",
    "vintage": "vintage",
    "retro": "vintage",
    "cinematic": "cinematic",
    "dramatic": "dramatic",
    "bright": "bright",
    "dark": "dark",
    "moody": "moody",
    "saturated": "saturated",
    "desaturated": "desaturated",
    "black and white": "bw",
    "b&w": "bw",
    "bw": "bw",
    "grayscale": "bw",
    "sepia": "sepia",
    "high contrast": "high_contrast",
    "low contrast": "low_contrast",
    "neon": "neon",
    "pastel": "pastel",
}

SPEED_PATTERN = r"(\d+\.?\d*)\s*x"


def parse_time_to_seconds(time_str: str) -> float:
    """Convert time string to seconds."""
    time_str = time_str.strip()

    # Handle unit suffixes
    for unit, mult in [("hours", 3600), ("hour", 3600), ("h", 3600),
                       ("minutes", 60), ("minute", 60), ("min", 60), ("m", 60),
                       ("seconds", 1), ("second", 1), ("sec", 1), ("s", 1)]:
        if time_str.endswith(unit):
            num = time_str[:-len(unit)].strip()
            try:
                return float(num) * mult
            except ValueError:
                break

    # Handle M:SS or H:MM:SS
    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    # Plain number = seconds
    try:
        return float(time_str)
    except ValueError:
        return 0.0


def parse_instruction(text: str) -> list[EditAction]:
    """Parse natural language editing instruction into a list of actions."""
    text_lower = text.lower().strip()
    actions = []

    # Detect platform formatting (match longer keywords first to avoid partial matches)
    sorted_platforms = sorted(PLATFORM_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True)
    for platform, settings in sorted_platforms:
        if re.search(r'\b' + re.escape(platform) + r'\b', text_lower):
            actions.append(EditAction("format_platform", {
                "platform": platform,
                **settings,
            }))
            break

    # Detect clip/trim requests
    if any(w in text_lower for w in ["clip", "cut", "trim", "segment", "highlight"]):
        # Look for time ranges
        time_matches = re.findall(TIME_PATTERN, text_lower)
        if len(time_matches) >= 2:
            start = parse_time_to_seconds(time_matches[0])
            end = parse_time_to_seconds(time_matches[1])
            actions.append(EditAction("trim", {"start": start, "end": end}))
        elif "best" in text_lower or "interesting" in text_lower or "highlight" in text_lower:
            actions.append(EditAction("auto_clip", {
                "style": "highlights",
                "max_clips": 5,
            }))
        else:
            actions.append(EditAction("auto_clip", {
                "style": "general",
                "max_clips": 3,
            }))

    # Detect auto-clip for posting
    if any(w in text_lower for w in ["ready to post", "publish", "viral", "content"]):
        if not any(a.action == "auto_clip" for a in actions):
            actions.append(EditAction("auto_clip", {
                "style": "viral",
                "max_clips": 5,
            }))

    # Detect music/audio requests
    if any(w in text_lower for w in ["music", "background music", "bgm", "song", "beat",
                                      "add music", "put music", "soundtrack",
                                      "audio track", "backing track", "tune"]):
        actions.append(EditAction("add_music", {"source": "user_upload"}))

    if any(w in text_lower for w in ["sfx", "sound effect", "sound effects",
                                      "whoosh", "swoosh", "ding", "pop sound"]):
        actions.append(EditAction("add_sfx", {"source": "user_upload"}))

    # Detect speed changes
    speed_match = re.search(SPEED_PATTERN, text_lower)
    if speed_match:
        speed = float(speed_match.group(1))
        actions.append(EditAction("speed", {"multiplier": speed}))
    elif "slow motion" in text_lower or "slow mo" in text_lower or "slowmo" in text_lower:
        actions.append(EditAction("speed", {"multiplier": 0.5}))
    elif "fast" in text_lower and "forward" in text_lower:
        actions.append(EditAction("speed", {"multiplier": 2.0}))

    # Detect effects
    for keyword, effect in EFFECT_KEYWORDS.items():
        if keyword in text_lower:
            if not any(a.action == "effect" and a.params.get("type") == effect for a in actions):
                actions.append(EditAction("effect", {"type": effect}))

    # Detect color grading
    for keyword, grade in COLOR_KEYWORDS.items():
        if keyword in text_lower:
            actions.append(EditAction("color_grade", {"style": grade}))
            break

    # Detect text overlay
    text_match = re.search(r'(?:add|put|overlay)\s+(?:text|title|caption)\s*[:\-]?\s*["\'](.+?)["\']', text_lower)
    if text_match:
        actions.append(EditAction("text_overlay", {"text": text_match.group(1)}))
    elif any(w in text_lower for w in ["subtitle", "subtitles", "captions", "caption"]):
        actions.append(EditAction("auto_captions", {}))

    # Detect compress/optimize
    if any(w in text_lower for w in ["compress", "smaller", "reduce size", "optimize"]):
        actions.append(EditAction("compress", {}))

    # Detect reverse
    if "reverse" in text_lower:
        actions.append(EditAction("reverse", {}))

    # Detect mute
    if any(w in text_lower for w in ["mute", "remove audio", "no audio", "silent", "no sound"]):
        actions.append(EditAction("mute", {}))

    # Detect resolution changes
    res_match = re.search(r"(\d{3,4})p", text_lower)
    if res_match:
        actions.append(EditAction("resize", {"height": int(res_match.group(1))}))

    # Detect rotation
    rot_match = re.search(r"rotate\s*(\d+)", text_lower)
    if rot_match:
        actions.append(EditAction("rotate", {"degrees": int(rot_match.group(1))}))

    # Detect silence removal
    if any(w in text_lower for w in ["remove silence", "cut silence", "no silence",
                                      "remove dead air", "remove pauses", "cut pauses",
                                      "dead air", "awkward pause", "clean up audio",
                                      "remove the silence", "cut the silence",
                                      "remove gaps", "cut gaps"]):
        actions.append(EditAction("remove_silence", {}))

    # Detect transition requests
    if any(w in text_lower for w in ["transition", "transitions", "crossfade"]):
        style = "smooth"
        for s in ["dynamic", "cinematic", "energetic", "minimal", "creative"]:
            if s in text_lower:
                style = s
                break
        if not any(a.action == "add_transitions" for a in actions):
            actions.append(EditAction("add_transitions", {"style": style}))

    # Detect intro/outro
    if any(w in text_lower for w in ["intro", "title card", "opening"]):
        actions.append(EditAction("add_intro", {}))
    if any(w in text_lower for w in ["outro", "end screen", "end card"]):
        actions.append(EditAction("add_end_screen", {}))

    # Detect lower third
    lower_match = re.search(r'lower third[:\s]*["\']?(.+?)["\']?$', text_lower)
    if lower_match:
        actions.append(EditAction("lower_third", {"name": lower_match.group(1)}))

    # Detect subscribe/CTA overlay
    if any(w in text_lower for w in ["subscribe", "cta", "call to action"]):
        actions.append(EditAction("subscribe_overlay", {}))

    # Detect stock footage/B-roll
    if any(w in text_lower for w in ["b-roll", "broll", "b roll", "stock footage",
                                      "stock video", "cutaway"]):
        query_match = re.search(r'(?:b-?roll|stock (?:footage|video)|cutaway)\s+(?:of\s+)?["\']?(.+?)["\']?$', text_lower)
        query = query_match.group(1) if query_match else "generic"
        actions.append(EditAction("add_broll", {"query": query}))

    # Detect URL-based video downloading
    urls = extract_urls(text)
    if urls:
        actions.append(EditAction("download_and_merge", {
            "urls": urls,
            "raw_text": text,
            "add_transitions": True,
            "fix_glitches": True,
        }))
        # Check for music preferences in the same message
        if any(w in text_lower for w in ["my music", "upload music", "i have music",
                                          "my own music", "i'll upload"]):
            actions.append(EditAction("ask_music", {"preference": "user_upload"}))
        elif any(w in text_lower for w in ["add music", "background music", "music",
                                            "with music", "put music"]):
            actions.append(EditAction("smart_music", {}))
        return actions  # URLs are the primary action, skip other parsing

    # Detect smart music requests (auto-find suitable music)
    if any(w in text_lower for w in ["find music", "suggest music", "auto music",
                                      "pick music", "choose music",
                                      "suitable music", "matching music",
                                      "best music", "right music"]):
        actions.append(EditAction("smart_music", {}))

    # Detect full auto-edit ("edit this", "full edit", "edit like a pro")
    if any(w in text_lower for w in ["full edit", "edit this", "edit it",
                                      "edit like a pro", "auto edit", "auto-edit",
                                      "professional edit", "do everything"]):
        if not any(a.action == "auto_edit" for a in actions):
            actions.append(EditAction("auto_edit", {"raw_text": text}))

    # If no specific actions detected, try to infer from context
    if not actions:
        # Broad catch-all: anything that sounds like an editing request
        edit_indicators = [
            "edit", "make it", "make this", "can you", "could you",
            "i want", "i need", "please", "do", "fix", "change",
            "better", "enhance", "improve", "help", "clean",
            "professional", "nice", "good", "awesome", "fire",
            "polish", "touch up", "finalize", "finish",
            "prepare", "get it ready", "make it look",
            "production", "post", "upload ready",
        ]
        if any(w in text_lower for w in edit_indicators):
            actions.append(EditAction("auto_edit", {"raw_text": text}))
        else:
            # Even for truly unknown input, default to auto_edit rather than error
            # The user sent a video + text — they clearly want something done
            actions.append(EditAction("auto_edit", {"raw_text": text}))

    return actions


def describe_actions(actions: list[EditAction]) -> str:
    """Generate a human-readable description of planned actions."""
    descriptions = []
    for action in actions:
        if action.action == "format_platform":
            descriptions.append(f"Format for {action.params['platform']} ({action.params['aspect']})")
        elif action.action == "trim":
            descriptions.append(f"Trim from {action.params['start']}s to {action.params['end']}s")
        elif action.action == "auto_clip":
            descriptions.append(f"Auto-clip ({action.params['style']} style, up to {action.params['max_clips']} clips)")
        elif action.action == "add_music":
            descriptions.append("Add background music (send music file)")
        elif action.action == "add_sfx":
            descriptions.append("Add sound effects (send audio files)")
        elif action.action == "speed":
            descriptions.append(f"Speed: {action.params['multiplier']}x")
        elif action.action == "effect":
            descriptions.append(f"Effect: {action.params['type']}")
        elif action.action == "color_grade":
            descriptions.append(f"Color grade: {action.params['style']}")
        elif action.action == "text_overlay":
            descriptions.append(f"Text overlay: \"{action.params['text']}\"")
        elif action.action == "auto_captions":
            descriptions.append("Auto-generate captions/subtitles")
        elif action.action == "compress":
            descriptions.append("Compress/optimize file size")
        elif action.action == "reverse":
            descriptions.append("Reverse video")
        elif action.action == "mute":
            descriptions.append("Mute audio")
        elif action.action == "resize":
            descriptions.append(f"Resize to {action.params['height']}p")
        elif action.action == "rotate":
            descriptions.append(f"Rotate {action.params['degrees']}°")
        elif action.action == "enhance":
            descriptions.append("Auto-enhance (stabilize, color correct, denoise)")
        elif action.action == "remove_silence":
            descriptions.append("Remove silence/dead air")
        elif action.action == "add_transitions":
            descriptions.append(f"Add {action.params.get('style', 'smooth')} transitions")
        elif action.action == "add_intro":
            descriptions.append("Add animated intro")
        elif action.action == "add_end_screen":
            descriptions.append("Add end screen")
        elif action.action == "lower_third":
            descriptions.append(f"Add lower third: {action.params.get('name', '')}")
        elif action.action == "subscribe_overlay":
            descriptions.append("Add subscribe/CTA overlay")
        elif action.action == "add_broll":
            descriptions.append(f"Insert B-roll: {action.params.get('query', '')}")
        elif action.action == "auto_edit":
            descriptions.append("Full auto-edit (silence removal → color → music → graphics)")
        elif action.action == "download_and_merge":
            url_count = len(action.params.get("urls", []))
            descriptions.append(f"Download {url_count} clip(s) from URL(s)")
            if action.params.get("fix_glitches"):
                descriptions.append("Scan for AI glitches and fix them")
            if action.params.get("add_transitions"):
                descriptions.append("Merge clips with transitions")
        elif action.action == "smart_music":
            descriptions.append("Auto-select background music that suits the video")
        elif action.action == "ask_music":
            descriptions.append("Waiting for your music upload")
    return "\n".join(f"• {d}" for d in descriptions)
