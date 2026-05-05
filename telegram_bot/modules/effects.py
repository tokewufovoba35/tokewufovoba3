"""
Video effects module — builds ffmpeg filter chains for pro-level effects.
"""

from dataclasses import dataclass


@dataclass
class FilterChain:
    """Represents a set of ffmpeg video/audio filters."""
    video_filters: list[str]
    audio_filters: list[str]
    extra_inputs: list[str]  # additional input files
    extra_args: list[str]    # additional ffmpeg arguments

    def __init__(self):
        self.video_filters = []
        self.audio_filters = []
        self.extra_inputs = []
        self.extra_args = []


def build_zoom_in(duration: float = 5.0) -> str:
    """Gradual zoom in effect (Ken Burns style)."""
    return f"scale=2*iw:2*ih,zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(duration*25)}:s=1920x1080"


def build_zoom_out(duration: float = 5.0) -> str:
    """Gradual zoom out effect."""
    return f"scale=2*iw:2*ih,zoompan=z='if(eq(on,1),1.5,max(zoom-0.0015,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(duration*25)}:s=1920x1080"


def build_fade_in(duration: float = 1.0, fps: int = 25) -> str:
    """Fade in from black."""
    return f"fade=t=in:st=0:d={duration}"


def build_fade_out(duration: float, video_duration: float, fps: int = 25) -> str:
    """Fade out to black at the end."""
    start = max(0, video_duration - duration)
    return f"fade=t=out:st={start}:d={duration}"


def build_speed_ramp(multiplier: float = 2.0) -> tuple[str, str]:
    """Speed change with smooth ramping."""
    video_filter = f"setpts={1/multiplier}*PTS"
    audio_filter = f"atempo={min(2.0, max(0.5, multiplier))}"
    return video_filter, audio_filter


def build_color_grade(style: str) -> str:
    """Build color grading filter."""
    grades = {
        "warm": "colortemperature=temperature=7000,eq=saturation=1.2",
        "cool": "colortemperature=temperature=4000,eq=saturation=1.1",
        "vintage": "curves=vintage,eq=saturation=0.8:contrast=1.1",
        "cinematic": "eq=contrast=1.2:brightness=-0.05:saturation=0.9,unsharp=5:5:0.5",
        "dramatic": "eq=contrast=1.4:brightness=-0.1:saturation=1.1",
        "bright": "eq=brightness=0.1:contrast=1.1:saturation=1.2",
        "dark": "eq=brightness=-0.15:contrast=1.2:saturation=0.9",
        "moody": "eq=brightness=-0.1:contrast=1.3:saturation=0.7",
        "saturated": "eq=saturation=1.5",
        "desaturated": "eq=saturation=0.5",
        "bw": "hue=s=0",
        "sepia": "hue=s=0,colorbalance=rs=0.3:gs=0.1:bs=-0.2",
        "high_contrast": "eq=contrast=1.5",
        "low_contrast": "eq=contrast=0.7",
        "neon": "eq=saturation=2.0:contrast=1.3:brightness=0.05",
        "pastel": "eq=saturation=0.6:brightness=0.1:contrast=0.9",
    }
    return grades.get(style, "eq=contrast=1.0")


def build_vignette() -> str:
    """Add vignette effect."""
    return "vignette=PI/4"


def build_film_grain() -> str:
    """Add film grain noise."""
    return "noise=alls=20:allf=t+u"


def build_letterbox(aspect: str = "21:9") -> str:
    """Add cinematic letterbox (black bars)."""
    if aspect == "21:9":
        return "crop=iw:iw/2.35,pad=iw:iw/1.78:(ow-iw)/2:(oh-ih)/2"
    return "pad=iw:iw*9/16:(ow-iw)/2:(oh-ih)/2:black"


def build_shake(intensity: float = 5.0) -> str:
    """Camera shake effect."""
    return f"crop=iw-{int(intensity*2)}:ih-{int(intensity*2)}:x='if(eq(mod(n,2),0),{int(intensity)},0)':y='if(eq(mod(n,3),0),{int(intensity)},0)',scale=iw+{int(intensity*2)}:ih+{int(intensity*2)}"


def build_blur(strength: int = 10) -> str:
    """Gaussian blur."""
    return f"boxblur={strength}:{strength}"


def build_glitch() -> str:
    """Glitch/datamosh-style effect."""
    return "rgbashift=rh=-5:bh=5,noise=alls=40:allf=t,hue=H=2*PI*t:s=2"


def build_text_overlay(text: str, position: str = "bottom", fontsize: int = 48) -> str:
    """Add text overlay."""
    positions = {
        "top": f"drawtext=text='{text}':fontsize={fontsize}:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=50",
        "center": f"drawtext=text='{text}':fontsize={fontsize}:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2",
        "bottom": f"drawtext=text='{text}':fontsize={fontsize}:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-text_h-50",
    }
    return positions.get(position, positions["bottom"])


def build_platform_format(platform_settings: dict) -> list[str]:
    """Build filters for platform-specific formatting."""
    filters = []
    aspect = platform_settings.get("aspect", "16:9")
    resolution = platform_settings.get("resolution", "1920x1080")
    w, h = resolution.split("x")

    if aspect == "9:16":
        # Vertical video: crop center and scale
        filters.append(f"scale={w}:{h}:force_original_aspect_ratio=increase")
        filters.append(f"crop={w}:{h}")
    else:
        # Horizontal: scale to fit
        filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        filters.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")

    return filters


def build_enhance() -> list[str]:
    """Auto-enhance: stabilize, denoise, color correct."""
    return [
        "hqdn3d=4:4:3:3",     # denoise
        "eq=contrast=1.1:brightness=0.02:saturation=1.1",  # color correct
        "unsharp=5:5:0.5",    # sharpen
    ]
