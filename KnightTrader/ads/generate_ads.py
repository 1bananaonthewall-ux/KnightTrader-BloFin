"""
Generate 3 high-converting Facebook/Reels video ads for KnightTrader Blofin.

Patterns used (based on research):
- Hook in first 3 seconds
- Problem -> Agitate -> Solve
- Pattern-break / curiosity openers
- UGC-style feel with clear captions
- Strong CTA at the end
"""

import os
import random
import math
from PIL import Image, ImageDraw, ImageFont, ImageChops
import numpy as np
import imageio.v2 as imageio

OUT_DIR = r"C:\Users\mknig\OneDrive\Documents\KT Blo\FB Ad Creative"
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 1080, 1920  # vertical 9:16
FPS = 30

# Brand colors
BG_DARK = (8, 8, 12)
BG_CARD = (20, 20, 28)
ACCENT_GREEN = (0, 230, 140)
ACCENT_RED = (255, 60, 60)
WHITE = (255, 255, 255)
GRAY = (180, 180, 190)
YELLOW = (255, 220, 60)

FONT_PATHS = [
    "C:\\Windows\\Fonts\\arial.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\impact.ttf",
]

def best_font(size, bold=False):
    try:
        path = FONT_PATHS[1 if bold else 0]
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        w, _ = text_size(draw, test, font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered_text(draw, text, y, font, fill=WHITE, max_width=None, line_gap=16):
    if max_width is None:
        max_width = W - 80
    lines = wrap_text(draw, text, font, max_width)
    total_h = sum(text_size(draw, line, font)[1] + line_gap for line in lines) - line_gap
    cy = y - total_h // 2
    for line in lines:
        lw, lh = text_size(draw, line, font)
        draw.text(((W - lw) // 2, cy), line, font=font, fill=fill)
        cy += lh + line_gap
    return cy


def gradient_bg(w, h, color1, color2):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / max(h - 1, 1)
        arr[y, :, 0] = int(color1[0] * (1 - t) + color2[0] * t)
        arr[y, :, 1] = int(color1[1] * (1 - t) + color2[1] * t)
        arr[y, :, 2] = int(color1[2] * (1 - t) + color2[2] * t)
    return Image.fromarray(arr)


def pulse_glow(radius, strength=0.5):
    # subtle glow circle helper
    size = radius * 2
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for r in range(radius, 0, -4):
        alpha = int(30 * (1 - r / radius) * strength)
        draw.ellipse((radius - r, radius - r, radius + r, radius + r), fill=(0, 230, 140, alpha))
    return img


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return int(a + (b - a) * t)


def lerp_color(c1, c2, t):
    return tuple(lerp(c1[i], c2[i], t) for i in range(3))


# ---------------------------------------------------------------------------
# Ad 1: Problem/Agitate/Solve — "You don't need to be a trading genius"
# ---------------------------------------------------------------------------
def render_ad_1(path):
    frames = int(FPS * 18)  # 18s
    out = []

    # timeline
    hook_end = int(FPS * 3)
    problem_end = int(FPS * 7)
    agitate_end = int(FPS * 11)
    solve_end = frames

    for i in range(frames):
        img = Image.new("RGB", (W, H), BG_DARK)
        draw = ImageDraw.Draw(img)
        t = i / frames

        # header status bar
        draw.rectangle((0, 0, W, 90), fill=(12, 12, 18))
        draw.text((60, 28), "KnightTrader Blofin", font=best_font(34, bold=True), fill=WHITE)
        draw.text((W - 220, 32), "AUTO TRADING", font=best_font(26), fill=ACCENT_GREEN)

        if i < hook_end:
            # Hook: big pain text with glitch-like emphasis
            progress = i / max(hook_end - 1, 1)
            scale = 1 + 0.05 * math.sin(progress * math.pi * 6)
            font = best_font(int(88 * scale), bold=True)
            color = ACCENT_RED if int(progress * 6) % 2 == 0 else WHITE
            draw_centered_text(draw, "STOP losing money", H // 2 - 60, font, fill=color, max_width=W - 100, line_gap=24)
            draw_centered_text(draw, "trading manually.", H // 2 + 60, font, fill=color, max_width=W - 100, line_gap=24)

            # pulsing circle
            glow = pulse_glow(160, 0.6)
            img.paste(glow, (W // 2 - 160, H // 2 - 160), glow)

        elif i < problem_end:
            progress = (i - hook_end) / max(problem_end - hook_end - 1, 1)
            y = 200
            draw.text((80, y), "❌ Manual trading fails because:", font=best_font(44, bold=True), fill=WHITE)
            y += 90
            bullets = [
                "You can’t watch charts 24/7",
                "Emotions make you sell too early",
                "Missed entries = missed profits",
                "Crypto moves while you sleep",
            ]
            for b in bullets:
                draw.text((100, y), "• " + b, font=best_font(42), fill=GRAY)
                y += 80

        elif i < agitate_end:
            progress = (i - problem_end) / max(agitate_end - problem_end - 1, 1)
            draw.text((80, 220), "😤 You’re tired of:", font=best_font(52, bold=True), fill=YELLOW)
            lines = [
                "Checking charts every 5 minutes...",
                "Watching pumps you missed...",
                "Wishing you had an edge...",
            ]
            y = 320
            for line in lines:
                draw.text((100, y), line, font=best_font(46), fill=WHITE)
                y += 100
            # shake effect
            if progress < 0.3:
                shift = int(6 * math.sin(progress * 80))
                img = ImageChops.offset(img, shift, 0)

        else:
            progress = min((i - agitate_end) / max(solve_end - agitate_end - 1, 1), 1)
            ep = ease_in_out(progress)

            # Solution card
            cx, cy = W // 2, H // 2 - 100
            cw, ch = 880, 520
            draw.rounded_rectangle((cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2), radius=30, fill=BG_CARD, outline=ACCENT_GREEN, width=4)

            draw.text((cx, cy - 140), "KT BLO", font=best_font(56, bold=True), fill=ACCENT_GREEN, anchor="mm")
            draw.text((cx, cy - 50), "does it for you.", font=best_font(48, bold=True), fill=WHITE, anchor="mm")

            features = ["24/7 autonomous trading", "Auto TP + SL on every trade", "Tracks equity live in app"]
            y = cy + 10
            for f in features:
                draw.text((cx, y), "✓ " + f, font=best_font(38), fill=GRAY, anchor="mm")
                y += 60

            # CTA
            cta_y = cy + ch // 2 + 80
            draw.rounded_rectangle((cx - 260, cta_y, cx + 260, cta_y + 90), radius=20, fill=ACCENT_GREEN)
            draw.text((cx, cta_y + 45), "Start Trading Automatically", font=best_font(40, bold=True), fill=BG_DARK, anchor="mm")

            # watermark
            draw.text((60, H - 120), "knighttraderblofin.com", font=best_font(30), fill=GRAY)

        out.append(np.array(img))

    writer = imageio.get_writer(path, fps=FPS, codec="libx264", quality=8, macro_block_size=8)
    for frame in out:
        writer.append_data(frame)
    writer.close()
    print("Wrote", path)


# ---------------------------------------------------------------------------
# Ad 2: Dashboard POV — "POV: You finally set up auto-trading"
# ---------------------------------------------------------------------------
def render_ad_2(path):
    frames = int(FPS * 15)
    out = []

    for i in range(frames):
        img = Image.new("RGB", (W, H), BG_DARK)
        draw = ImageDraw.Draw(img)
        progress = i / max(frames - 1, 1)

        # fake dashboard frame
        pad = 60
        draw.rounded_rectangle((pad, pad, W - pad, H - pad), radius=20, fill=BG_CARD, outline=(50, 50, 70), width=2)

        # header
        draw.rectangle((pad, pad, W - pad, pad + 90), fill=(16, 16, 26))
        draw.text((pad + 40, pad + 22), "Hermes Dashboard", font=best_font(38, bold=True), fill=WHITE)
        dot_color = ACCENT_GREEN if int(progress * 30) % 2 == 0 else (0, 200, 120)
        draw.ellipse((W - pad - 80, pad + 28, W - pad - 44, pad + 64), fill=dot_color)

        # equity box
        ex, ey, ew, eh = pad + 50, pad + 150, W - 2 * pad - 100, 220
        draw.rounded_rectangle((ex, ey, ex + ew, ey + eh), radius=16, fill=(28, 28, 40))
        draw.text((ex + 30, ey + 24), "Account Equity", font=best_font(34), fill=GRAY)
        equity_val = f"${(1200 + int(progress * 900)):,.2f}"
        draw.text((ex + 30, ey + 70), equity_val, font=best_font(72, bold=True), fill=ACCENT_GREEN)

        # fake chart line
        pts = []
        for x in range(ex + 20, ex + ew - 20, 12):
            y_base = ey + eh - 60
            amp = 40 + 20 * math.sin(x * 0.02 + progress * 4)
            pts.append((x, int(y_base - amp - progress * 120)))
        for j in range(len(pts) - 1):
            draw.line((pts[j], pts[j + 1]), fill=ACCENT_GREEN, width=4)

        # positions
        draw.text((ex + 30, ey + eh + 30), "Open Positions: 3", font=best_font(32), fill=WHITE)

        # POV text overlay top
        draw.text((W // 2, pad + 140), "POV: You finally set up auto-trading", font=best_font(54, bold=True), fill=WHITE, anchor="mm")

        # bottom CTA
        draw.rounded_rectangle((pad + 40, H - pad - 140, W - pad - 40, H - pad - 60), radius=20, fill=ACCENT_GREEN)
        draw.text((W // 2, H - pad - 100), "Download the App — $47/mo", font=best_font(40, bold=True), fill=BG_DARK, anchor="mm")

        out.append(np.array(img))

    writer = imageio.get_writer(path, fps=FPS, codec="libx264", quality=8, macro_block_size=8)
    for frame in out:
        writer.append_data(frame)
    writer.close()
    print("Wrote", path)


# ---------------------------------------------------------------------------
# Ad 3: Curiosity / Secret — "Nobody talks about this Windows trading trick"
# ---------------------------------------------------------------------------
def render_ad_3(path):
    frames = int(FPS * 20)
    out = []

    hook_end = int(FPS * 3)
    body_end = int(FPS * 13)

    for i in range(frames):
        img = Image.new("RGB", (W, H), BG_DARK)
        draw = ImageDraw.Draw(img)

        if i < hook_end:
            progress = i / max(hook_end - 1, 1)
            scale = 1 + 0.04 * math.sin(progress * math.pi * 8)
            font = best_font(int(96 * scale), bold=True)
            draw_centered_text(draw, "Nobody talks about this...", H // 2 - 80, font, fill=YELLOW, max_width=W - 100, line_gap=28)
            draw_centered_text(draw, "Windows trading trick.", H // 2 + 60, font, fill=WHITE, max_width=W - 100, line_gap=28)

        elif i < body_end:
            progress = (i - hook_end) / max(body_end - hook_end - 1, 1)
            y = 260
            draw.text((80, y), "The secret most traders ignore:", font=best_font(48, bold=True), fill=WHITE)
            y += 110
            lines = [
                "1. Let a bot trade for you",
                "2. Never miss a setup again",
                "3. Keep your day job",
                "4. Track everything in one app",
            ]
            for line in lines:
                draw.text((110, y), line, font=best_font(46), fill=ACCENT_GREEN)
                y += 90

            # typewriter effect
            if progress > 0.6:
                alpha = int(255 * min((progress - 0.6) / 0.4, 1))
                draw.rounded_rectangle((80, y + 30, W - 80, y + 140), radius=16, fill=(30, 30, 46))
                draw.text((120, y + 45), "KnightTrader Blofin = the edge.", font=best_font(46, bold=True), fill=WHITE)

        else:
            progress = min((i - body_end) / max(frames - body_end - 1, 1), 1)
            ep = ease_in_out(progress)

            draw_centered_text(draw, "Start auto-trading today.", H // 2 - 80, best_font(72, bold=True), fill=WHITE, max_width=W - 100, line_gap=28)
            draw_centered_text(draw, "$47/month. Cancel anytime.", H // 2 + 60, best_font(44), fill=GRAY, max_width=W - 100, line_gap=20)

            # CTA pulse
            pulse = 1 + 0.02 * math.sin(progress * math.pi * 6)
            cw, ch = 700, 110
            cx, cy = W // 2, H - 280
            draw.rounded_rectangle((cx - int(cw * pulse / 2), cy - int(ch * pulse / 2),
                                    cx + int(cw * pulse / 2), cy + int(ch * pulse / 2)),
                                   radius=24, fill=ACCENT_GREEN)
            draw.text((cx, cy), "Get KnightTrader Blofin", font=best_font(44, bold=True), fill=BG_DARK, anchor="mm")

        # bottom banner
        draw.rectangle((0, H - 50, W, H), fill=(12, 12, 18))
        draw.text((60, H - 36), "knighttraderblofin.com", font=best_font(26), fill=GRAY)

        out.append(np.array(img))

    writer = imageio.get_writer(path, fps=FPS, codec="libx264", quality=8, macro_block_size=8)
    for frame in out:
        writer.append_data(frame)
    writer.close()
    print("Wrote", path)


if __name__ == "__main__":
    print("Rendering ad 1/3...")
    render_ad_1(os.path.join(OUT_DIR, "KT_Blo_Ad1_ProblemSolve.mp4"))
    print("Rendering ad 2/3...")
    render_ad_2(os.path.join(OUT_DIR, "KT_Blo_Ad2_DashboardPOV.mp4"))
    print("Rendering ad 3/3...")
    render_ad_3(os.path.join(OUT_DIR, "KT_Blo_Ad3_SecretTrick.mp4"))
    print("All ads rendered to", OUT_DIR)
