"""
Motion graphics module — animated text, lower thirds, intros, outros, overlays.
All generated with ffmpeg filters (no external tools needed).
"""

import subprocess
from pathlib import Path


def add_animated_intro(video_path: str, output_path: str,
                       title: str = "", subtitle: str = "",
                       duration: float = 3.0,
                       style: str = "fade") -> str:
    """Add an animated text intro to the beginning of a video.
    
    Styles: fade, slide, zoom, minimal
    """
    # Create intro with black background + animated text
    filters = []

    if style == "fade":
        text_filter = (
            f"drawtext=text='{title}':fontsize=64:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30:"
            f"alpha='if(lt(t,0.5),t/0.5,if(lt(t,{duration-0.5}),1,(({duration}-t)/0.5)))'"
        )
        if subtitle:
            text_filter += (
                f",drawtext=text='{subtitle}':fontsize=32:fontcolor=white@0.8:"
                f"x=(w-text_w)/2:y=(h/2)+30:"
                f"alpha='if(lt(t,0.8),t/0.8,if(lt(t,{duration-0.5}),1,(({duration}-t)/0.5)))'"
            )
    elif style == "slide":
        text_filter = (
            f"drawtext=text='{title}':fontsize=64:fontcolor=white:"
            f"x='if(lt(t,0.5),-text_w+(w+text_w)*t/0.5,(w-text_w)/2)':"
            f"y=(h-text_h)/2-30"
        )
        if subtitle:
            text_filter += (
                f",drawtext=text='{subtitle}':fontsize=32:fontcolor=white@0.8:"
                f"x='if(lt(t,0.8),-text_w+(w+text_w)*t/0.8,(w-text_w)/2)':"
                f"y=(h/2)+30"
            )
    elif style == "zoom":
        text_filter = (
            f"drawtext=text='{title}':"
            f"fontsize='if(lt(t,0.5),64*t/0.5+10,64)':"
            f"fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-30:"
            f"alpha='if(lt(t,0.3),t/0.3,if(lt(t,{duration-0.5}),1,(({duration}-t)/0.5)))'"
        )
        if subtitle:
            text_filter += (
                f",drawtext=text='{subtitle}':fontsize=32:fontcolor=white@0.8:"
                f"x=(w-text_w)/2:y=(h/2)+30:"
                f"alpha='if(lt(t,0.5),0,if(lt(t,1),(t-0.5)/0.5,if(lt(t,{duration-0.5}),1,(({duration}-t)/0.5))))'"
            )
    else:  # minimal
        text_filter = (
            f"drawtext=text='{title}':fontsize=48:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"alpha='if(lt(t,0.3),t/0.3,if(lt(t,{duration-0.3}),1,(({duration}-t)/0.3)))'"
        )

    # Get video resolution
    import shutil
    resolution = "1920x1080"
    if shutil.which("ffprobe"):
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", video_path],
            capture_output=True, text=True,
        )
        if probe.stdout.strip():
            resolution = probe.stdout.strip().split("\n")[0]
    else:
        # Fallback: parse from ffmpeg
        probe = subprocess.run(
            ["ffmpeg", "-i", video_path],
            capture_output=True, text=True,
        )
        import re
        res_match = re.search(r"(\d{2,5})x(\d{2,5})", probe.stderr)
        if res_match:
            resolution = f"{res_match.group(1)}x{res_match.group(2)}"
    w, h = resolution.split("x")[:2]

    # Generate intro clip
    intro_path = str(Path(output_path).parent / "_intro.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={duration}:r=25",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-vf", text_filter,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        "-shortest",
        intro_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Intro generation failed: {result.stderr[-300:]}")

    # Concatenate intro + original video
    concat_file = Path(output_path).parent / "_intro_concat.txt"
    with open(concat_file, "w") as f:
        f.write(f"file '{intro_path}'\n")
        f.write(f"file '{video_path}'\n")

    # Need to re-encode for matching formats
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat_file),
         "-c:v", "libx264", "-preset", "fast",
         "-c:a", "aac",
         output_path],
        capture_output=True, text=True, timeout=180,
    )

    # Clean up
    Path(intro_path).unlink(missing_ok=True)
    concat_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Intro concat failed: {result.stderr[-300:]}")

    return output_path


def add_lower_third(video_path: str, output_path: str,
                    name: str, title: str = "",
                    start_time: float = 2.0,
                    duration: float = 4.0) -> str:
    """Add an animated lower third (name + title bar).
    
    Appears at start_time and fades out after duration.
    """
    end_time = start_time + duration
    fade_in = 0.3
    fade_out = 0.3

    # Background bar + text
    filter_chain = (
        # Semi-transparent bar
        f"drawbox=x=50:y=h-120:w=500:h=80:color=black@0.7:t=fill:"
        f"enable='between(t,{start_time},{end_time})',"
        # Name text
        f"drawtext=text='{name}':fontsize=36:fontcolor=white:"
        f"x=70:y=h-110:"
        f"alpha='if(lt(t,{start_time}),0,if(lt(t,{start_time+fade_in}),(t-{start_time})/{fade_in},"
        f"if(lt(t,{end_time-fade_out}),1,({end_time}-t)/{fade_out})))',"
        # Title/role text
        f"drawtext=text='{title}':fontsize=24:fontcolor=white@0.8:"
        f"x=70:y=h-75:"
        f"alpha='if(lt(t,{start_time+0.2}),0,if(lt(t,{start_time+fade_in+0.2}),(t-{start_time+0.2})/{fade_in},"
        f"if(lt(t,{end_time-fade_out}),1,({end_time}-t)/{fade_out})))'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", filter_chain,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Lower third failed: {result.stderr[-300:]}")

    return output_path


def add_subscribe_overlay(video_path: str, output_path: str,
                          text: str = "SUBSCRIBE",
                          position: str = "bottom_right",
                          start_time: float = 5.0,
                          duration: float = 5.0) -> str:
    """Add animated subscribe/CTA overlay."""
    end_time = start_time + duration

    positions = {
        "bottom_right": ("w-250", "h-80"),
        "bottom_left": ("30", "h-80"),
        "top_right": ("w-250", "30"),
    }
    x, y = positions.get(position, positions["bottom_right"])

    filter_chain = (
        # Rounded rect background
        f"drawbox=x={x}:y={y}:w=220:h=50:color=red@0.9:t=fill:"
        f"enable='between(t,{start_time},{end_time})',"
        # Text
        f"drawtext=text='{text}':fontsize=24:fontcolor=white:"
        f"x={x}+20:y={y}+13:"
        f"alpha='if(lt(t,{start_time}),0,if(lt(t,{start_time+0.3}),(t-{start_time})/0.3,"
        f"if(lt(t,{end_time-0.3}),1,({end_time}-t)/0.3)))'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", filter_chain,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Subscribe overlay failed: {result.stderr[-300:]}")

    return output_path


def add_end_screen(video_path: str, output_path: str,
                   text: str = "Thanks for watching!",
                   subtext: str = "Like & Subscribe",
                   duration: float = 4.0) -> str:
    """Add an end screen with text."""
    from modules.clipper import get_video_duration

    video_duration = get_video_duration(video_path)
    start_time = max(0, video_duration - duration)

    filter_chain = (
        # Darken the last few seconds
        f"colorlevels=rimax=0.6:gimax=0.6:bimax=0.6:enable='gte(t,{start_time})',"
        # Main text
        f"drawtext=text='{text}':fontsize=48:fontcolor=white:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-20:"
        f"alpha='if(lt(t,{start_time}),0,if(lt(t,{start_time+0.5}),(t-{start_time})/0.5,1))',"
        # Subtext
        f"drawtext=text='{subtext}':fontsize=28:fontcolor=white@0.8:"
        f"x=(w-text_w)/2:y=(h/2)+30:"
        f"alpha='if(lt(t,{start_time+0.3}),0,if(lt(t,{start_time+0.8}),(t-{start_time+0.3})/0.5,1))'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", filter_chain,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"End screen failed: {result.stderr[-300:]}")

    return output_path


def add_progress_bar(video_path: str, output_path: str,
                     color: str = "red", height: int = 4) -> str:
    """Add a progress bar at the bottom of the video."""
    from modules.clipper import get_video_duration

    duration = get_video_duration(video_path)

    filter_chain = (
        f"drawbox=x=0:y=ih-{height}:w='iw*t/{duration}':h={height}:"
        f"color={color}:t=fill"
    )

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", filter_chain,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Progress bar failed: {result.stderr[-300:]}")

    return output_path
