import os
import math
import datetime
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "tutorial-assets")
VIDEO_DIR = os.path.join(OUT, "video")
SHOT_DIR = os.path.join(OUT, "shots")
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(SHOT_DIR, exist_ok=True)

FPS = 24
DURATION = 9  # seconds per short walkthrough clip

WINDOWS = {
    "title": "Windows",
    "accent": (123, 210, 255),
    "panel": (20, 23, 28),
    "ui": "PowerShell",
    "icon": "start",
    "browser": "Edge",
    "text_window": "Windows PowerShell",
    "key_binding": "Ctrl + C / Ctrl + V",
    "terminal_label": "Windows PowerShell",
}

MAC = {
    "title": "Mac",
    "accent": (255, 210, 102),
    "panel": (24, 22, 26),
    "ui": "Terminal",
    "icon": "apple",
    "browser": "Safari",
    "text_window": "Terminal",
    "key_binding": "Cmd + C / Cmd + V",
    "terminal_label": "Terminal",
}

def load_font(size, bold=False):
    candidates = []
    for root, _, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
        for name in files:
            if name.lower().endswith(".ttf") or name.lower().endswith(".otf"):
                candidates.append(os.path.join(root, name))
    if not candidates:
        candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    picked = None
    for path in candidates:
        if os.path.exists(path):
            picked = path
            break
    if not picked:
        picked = candidates[0] if candidates else None
    try:
        return ImageFont.truetype(picked, size) if picked else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()

def draw_panel(draw, x, y, w, h, fill=(20, 23, 28), border=(40, 46, 54)):
    draw.rectangle([x, y, x + w, y + h], fill=fill, outline=border, width=2)

def draw_mini_browser(draw, cx, top, width, height, os_cfg):
    x0 = cx - width / 2
    y0 = top
    accent = os_cfg["accent"]
    draw.rectangle([x0, y0, x0 + width, y0 + height], fill=(18, 21, 26), outline=(54, 60, 68), width=3)
    # title bar
    draw.rectangle([x0, y0, x0 + width, y0 + 26], fill=(28, 32, 38))
    draw.rectangle([x0, y0, x0 + width, y0 + 26], outline=(70, 76, 84), width=1)
    # dots
    for i, c in enumerate([(255, 95, 86), (255, 189, 48), (86, 200, 103)]):
        draw.ellipse([x0 + 10 + i * 18, y0 + 8, x0 + 18 + i * 18, y0 + 16], fill=c)
    label = os_cfg["browser"] + "  https://www.coinbase.com"
    f = load_font(16)
    draw.text((x0 + 60, y0 + 6), label, fill=(220, 224, 230), font=f)
    # address bar
    draw.rectangle([x0 + 8, y0 + 34, x0 + width - 8, y0 + 52], fill=(38, 43, 49))
    draw.text((x0 + 14, y0 + 37), "https://www.coinbase.com", fill=(160, 200, 255), font=load_font(14))
    # body
    body_top = y0 + 64
    draw.rectangle([x0 + 8, body_top, x0 + width - 8, y0 + height - 20], fill=(24, 28, 32))
    # fake content
    f2 = load_font(14)
    lines = ["Sign in to your Coinbase account",
             "",
             "Email address",
             "Password",
             "",
             "  [ Sign in ]     [ Get started ]"]
    for i, line in enumerate(lines):
        draw.text((x0 + 18, body_top + 10 + i * 20), line, fill=(200, 206, 214), font=f2)
    # status
    draw.rectangle([x0 + width - 150, y0 + height - 22, x0 + width - 8, y0 + height - 8], fill=(40, 46, 52))
    draw.text((x0 + width - 144, y0 + height - 18), "Connected", fill=(140, 220, 160), font=load_font(12))

def draw_text_window(draw, cx, top, width, height, os_cfg, lines, label):
    x0 = cx - width / 2
    y0 = top
    accent = os_cfg["accent"]
    draw.rectangle([x0, y0, x0 + width, y0 + height], fill=(14, 17, 21), outline=(54, 60, 68), width=3)
    draw.rectangle([x0, y0, x0 + width, y0 + 22], fill=(26, 30, 35))
    draw.text((x0 + 10, y0 + 4), label, fill=accent, font=load_font(13))
    inner = y0 + 26
    for i, line in enumerate(lines):
        color = (220, 224, 230) if i % 2 == 0 else (170, 180, 190)
        draw.text((x0 + 12, inner + i * 18), line, fill=color, font=load_font(13))
    # caret
    last = lines[-1] if lines else ""
    draw.rectangle([x0 + 12 + len(last) * 8, inner + len(lines) * 18 + 2,
                    x0 + 12 + len(last) * 8 + 8, inner + len(lines) * 18 + 12], fill=accent)

def draw_start_or_apple(draw, cx, top, size, os_cfg):
    if os_cfg["icon"] == "start":
        x0 = cx - size / 2
        y0 = top
        draw.rectangle([x0, y0, x0 + size, y0 + size], fill=(28, 32, 38), outline=(70, 76, 84), width=3)
        # windows logo-ish
        bar_w = size * 0.16
        gap = size * 0.08
        offsets = [0.12, 0.36, 0.6, 0.84]
        for i, off in enumerate(offsets):
            alpha = 0.9 if i == 0 else 0.8 if i == 1 else 0.85
            col = tuple(int(v * alpha) for v in (220, 224, 230))
            draw.rectangle([x0 + size * off, y0 + size * 0.22,
                            x0 + size * off + bar_w, y0 + size * 0.28], fill=col)
            draw.rectangle([x0 + size * off, y0 + size * 0.38,
                            x0 + size * off + bar_w, y0 + size * 0.44], fill=col)
    else:
        x0 = cx - size / 2
        y0 = top
        draw.ellipse([x0, y0, x0 + size, y0 + size], fill=(25, 28, 32), outline=(80, 86, 92), width=3)
        half = size / 2
        r = size * 0.16
        draw.ellipse([x0 + half - r, y0 + half - r * 1.1, x0 + half + r, y0 + half + r * 1.1], fill=(255, 210, 102))

def shot_filename(os_name, slug):
    return os.path.join(SHOT_DIR, f"shot-{os_name}-{slug}.png")

def render_shot(os_name, slug, draw_fn):
    cfg = WINDOWS if os_name == "windows" else MAC
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (14, 17, 21))
    draw = ImageDraw.Draw(img)
    draw_fn(draw, cfg, W, H)
    path = shot_filename(os_name, slug)
    img.save(path)
    return path

def render_video_still(os_name, slug, draw_fn, frame_index=0):
    cfg = WINDOWS if os_name == "windows" else MAC
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), (14, 17, 21))
    draw = ImageDraw.Draw(img)
    draw_fn(draw, cfg, W, H, frame=frame_index)
    path = os.path.join(VIDEO_DIR, f"{os_name}-{slug}-frame.jpg")
    img.save(path)
    return path

def ffmpeg_still_to_clip(still_path, out_path, duration=DURATION, fps=FPS):
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", still_path,
        "-vf", f"fps={fps},format=yuv420p",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",
        out_path,
    ]
    import subprocess
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def make_narration_track(path, text, silent=True):
    # Placeholder narration track: a silent audio file + a caption sidecar.
    # If you later plug in real TTS, rewrite this to render speech.
    import subprocess
    import json
    dur = 3.0
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={dur}",
        "-c:a", "aac",
        "-b:a", "128k",
        path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sidecar = path + ".meta.json"
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump({"caption": text, "duration": dur}, f, ensure_ascii=False, indent=2)

def clip_meta(out_path, caption, os_name, slug):
    meta_path = out_path + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        import json
        json.dump({
            "os": os_name,
            "slug": slug,
            "caption": caption,
            "frame": out_path.replace(".mp4", "-frame.jpg"),
        }, f, ensure_ascii=False, indent=2)

def build_shot(os_name, slug, draw_fn):
    render_shot(os_name, slug, draw_fn)

def build_clip(os_name, slug, caption, draw_fn):
    still = render_video_still(os_name, slug, draw_fn)
    out = os.path.join(VIDEO_DIR, f"{os_name}-{slug}.mp4")
    ffmpeg_still_to_clip(still, out)
    audio = out.replace(".mp4", "-narration.m4a")
    make_narration_track(audio, caption)
    clip_meta(out, caption, os_name, slug)

def multi_frame_still(os_name, slug, frame_draw_fn, count=3):
    for i in range(count):
        render_video_still(os_name, slug, frame_draw_fn, frame_index=i)

print("assets ready:", OUT)
