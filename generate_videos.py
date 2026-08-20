import os
import math
import random
from PIL import Image, ImageDraw, ImageFont

VIDEO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_videos")
os.makedirs(VIDEO_ROOT, exist_ok=True)

W, H = 1280, 720
FPS = 24
DURATION_SEC = 12

def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default(size=size)

def draw_rounded_rect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

def center_text(draw, text, y, fill, font_size=36):
    f = font(font_size)
    bbox = draw.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, y), text, fill=fill, font=f)

def slideshow_frames(images, total_frames=None):
    if total_frames is None:
        total_frames = FPS * DURATION_SEC
    per = max(1, total_frames // max(1, len(images)))
    for i in range(total_frames):
        idx = min(len(images) - 1, i // per)
        yield images[idx]

def write_video(path, frames, sample_rate=48000, freq=440):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    palette = None
    temp_palette = path + ".png"
    temp_audio = path + ".wav"
    first = next(frames)
    first.save(temp_palette, "PNG")
    first.close()

    import wave, struct
    duration = DURATION_SEC
    rate = sample_rate
    n = duration * rate
    with wave.open(temp_audio, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(n):
            val = int(32767 * 0.15 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", val))

    cmd = (
        f'ffmpeg -y -framerate {FPS} -i "{temp_palette}" -i "{temp_audio}" '
        f'-c:v libx264 -tune stillimage -pix_fmt yuv420p -shortest -c:a aac "{path}"'
    )
    os.system(cmd)

    for extra in [temp_palette, temp_audio]:
        if os.path.exists(extra):
            os.remove(extra)

def make_background(dark=True):
    bg = Image.new("RGB", (W, H), (15, 17, 21) if dark else (235, 238, 242))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([0, 0, W, 60], fill=(27, 31, 37) if dark else (210, 214, 219))
    draw.text((24, 14), "KnightTrader Walkthru", fill=(230, 233, 238) if dark else (30, 33, 38), font=font(26))
    return bg, draw

def browser_frame(title, url, body_lines, os_name="windows"):
    bg, draw = make_background()
    draw.rectangle([0, 60, W, H], fill=(255, 255, 255))
    bar = Image.new("RGB", (W, 44), (220, 223, 228))
    bg.paste(bar, (0, 60))
    draw = ImageDraw.Draw(bg)
    draw.rounded_rectangle([24, 72, 340, 100], radius=18, fill=(255, 255, 255), outline=(180, 185, 192), width=2)
    draw.text((44, 74), url, fill=(60, 64, 70), font=font(18))
    draw.text((24, 120), title, fill=(20, 24, 30), font=font(28))
    y = 170
    for line in body_lines:
        draw.text((24, y), line, fill=(50, 55, 65), font=font(20))
        y += 34
    return bg

def terminal_frame(title, lines, os_name="windows"):
    bg, draw = make_background()
    draw.rectangle([0, 60, W, H], fill=(12, 14, 18))
    draw = ImageDraw.Draw(bg)
    draw.text((24, 120), title, fill=(230, 233, 238), font=font(26))
    y = 170
    for line in lines:
        draw.text((24, y), line, fill=(210, 220, 220), font=font(20))
        y += 34
    return bg

def dashboard_frame(title, items, os_name="windows"):
    bg, draw = make_background()
    draw.rectangle([0, 60, W, H], fill=(20, 24, 30))
    draw = ImageDraw.Draw(bg)
    draw.text((24, 100), title, fill=(240, 225, 140), font=font(28))
    y = 160
    for item in items:
        draw.rounded_rectangle([24, y, 640, y + 70], radius=14, fill=(30, 35, 43), outline=(60, 68, 80), width=2)
        draw.text((44, y + 18), item, fill=(220, 225, 235), font=font(20))
        y += 92
    return bg

def save_video(name, frame_fn):
    path = os.path.join(VIDEO_ROOT, name)
    frames = frame_fn()
    write_video(path, frames)
    print("created", path, "size", os.path.getsize(path))

def gen_intro_windows():
    def frames():
        a = browser_frame("Welcome", "knighttrader.local", ["This tutorial supports Windows and Mac.", "Pick your OS and follow that path."])
        b = browser_frame("Setup Overview", "knighttrader.local/setup", ["1. Stay awake + online", "2. Coinbase account", "3. Hermes + cron"])
        return slideshow_frames([a, b])
    save_video("intro-windows.mp4", frames)

def gen_intro_mac():
    def frames():
        a = browser_frame("Welcome", "knighttrader.local", ["This tutorial supports Windows and Mac.", "Pick your OS and follow that path."])
        b = browser_frame("Setup Overview", "knighttrader.local/setup", ["1. Stay awake + online", "2. Coinbase account", "3. Hermes + cron"])
        return slideshow_frames([a, b])
    save_video("intro-mac.mp4", frames)

def gen_never_sleep_windows():
    def frames():
        a = browser_frame("Power & sleep", "Windows Settings", ["Search: Power & sleep", "Screen: Never when plugged in", "Sleep: Never when plugged in"])
        b = terminal_frame("PowerShell", ["powercfg /change standby-timeout-ac 0", "powercfg /change monitor-timeout-ac 0", "Command completed."])
        return slideshow_frames([a, b])
    save_video("never-sleep-windows.mp4", frames)

def gen_never_sleep_mac():
    def frames():
        a = browser_frame("System Settings", "System Settings", ["Open Battery / Energy Saver", "Keep display awake while learning", "Keep lid open when possible"])
        b = terminal_frame("Terminal", ["caffeinate -dimsu", "Mac will stay awake while this runs."])
        return slideshow_frames([a, b])
    save_video("never-sleep-mac.mp4", frames)

def gen_coinbase_signup_windows():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Click Sign up", "Use a real email", "Verify email and phone"])
        b = browser_frame("Coinbase", "coinbase.com/verify", ["Complete identity check if asked", "This is normal"])
        return slideshow_frames([a, b])
    save_video("coinbase-signup-windows.mp4", frames)

def gen_coinbase_signup_mac():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Click Sign up", "Use a real email", "Verify email and phone"])
        b = browser_frame("Coinbase", "coinbase.com/verify", ["Complete identity check if asked", "This is normal"])
        return slideshow_frames([a, b])
    save_video("coinbase-signup-mac.mp4", frames)

def gen_fund_coinbase_windows():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Open Buy / Trade", "Pick a first crypto", "Review fee preview"])
        b = browser_frame("Wallet", "coinbase.com/wallet", ["Purchase submitted", "Balance will appear shortly"])
        return slideshow_frames([a, b])
    save_video("fund-coinbase-windows.mp4", frames)

def gen_fund_coinbase_mac():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Open Buy / Trade", "Pick a first crypto", "Review fee preview"])
        b = browser_frame("Wallet", "coinbase.com/wallet", ["Purchase submitted", "Balance will appear shortly"])
        return slideshow_frames([a, b])
    save_video("fund-coinbase-mac.mp4", frames)

def gen_nous_key_windows():
    def frames():
        a = browser_frame("Nous Portal", "portal.nousresearch.com", ["Sign in or create an account", "Open API Keys"])
        b = browser_frame("API Key", "portal.nousresearch.com/keys", ["Create a new key", "Copy it once and save it"])
        return slideshow_frames([a, b])
    save_video("nous-key-windows.mp4", frames)

def gen_nous_key_mac():
    def frames():
        a = browser_frame("Nous Portal", "portal.nousresearch.com", ["Sign in or create an account", "Open API Keys"])
        b = browser_frame("API Key", "portal.nousresearch.com/keys", ["Create a new key", "Copy it once and save it"])
        return slideshow_frames([a, b])
    save_video("nous-key-mac.mp4", frames)

def gen_save_key_windows():
    def frames():
        a = terminal_frame("Notepad", ["Paste key and values", "Save as: Coinbase MK API Keys.txt"])
        b = browser_frame("Downloads", "file:///Users/you/Downloads", ["Save in Downloads for now", "Do not email this file"])
        return slideshow_frames([a, b])
    save_video("save-key-windows.mp4", frames)

def gen_save_key_mac():
    def frames():
        a = terminal_frame("TextEdit", ["Format > Make Plain Text", "Paste key and values", "Save to Downloads"])
        b = browser_frame("Downloads", "file:///Users/you/Downloads", ["File should be visible now", "Keep it local and safe"])
        return slideshow_frames([a, b])
    save_video("save-key-mac.mp4", frames)

def gen_install_hermes_windows():
    def frames():
        a = terminal_frame("PowerShell", ["winget install HermesProject.Hermes", "Wait for install to finish"])
        b = terminal_frame("PowerShell", ["hermes --version", "hermes doctor", "Installed and ready."])
        return slideshow_frames([a, b])
    save_video("install-hermes-windows.mp4", frames)

def gen_install_hermes_mac():
    def frames():
        a = terminal_frame("Terminal", ["brew install hermes", "Allow developer tools if prompted"])
        b = terminal_frame("Terminal", ["hermes --version", "hermes doctor", "Installed and ready."])
        return slideshow_frames([a, b])
    save_video("install-hermes-mac.mp4", frames)

def gen_provider_model_windows():
    def frames():
        a = dashboard_frame("Hermes Settings", ["Provider: Nous", "Model: tencent/hy free", "Save settings"])
        b = dashboard_frame("Settings saved", ["Provider confirmed", "Model confirmed", "Ready for dashboard"])
        return slideshow_frames([a, b])
    save_video("provider-model-windows.mp4", frames)

def gen_provider_model_mac():
    def frames():
        a = dashboard_frame("Hermes Settings", ["Provider: Nous", "Model: tencent/hy free", "Save settings"])
        b = dashboard_frame("Settings saved", ["Provider confirmed", "Model confirmed", "Ready for dashboard"])
        return slideshow_frames([a, b])
    save_video("provider-model-mac.mp4", frames)

def gen_dashboard_windows():
    def frames():
        a = terminal_frame("PowerShell", ["hermes dashboard", "Opening browser..."])
        b = dashboard_frame("Hermes Dashboard", ["Chats selected", "Cron section visible", "Local URL: 127.0.0.1:9119"])
        return slideshow_frames([a, b])
    save_video("dashboard-windows.mp4", frames)

def gen_dashboard_mac():
    def frames():
        a = terminal_frame("Terminal", ["hermes dashboard", "Opening browser..."])
        b = dashboard_frame("Hermes Dashboard", ["Chats selected", "Cron section visible", "Local URL: 127.0.0.1:9119"])
        return slideshow_frames([a, b])
    save_video("dashboard-mac.mp4", frames)

def gen_cron_windows():
    def frames():
        a = dashboard_frame("Create Cron Job", ["Name: coinbase-equity-vertical", "Schedule: every 10 minutes", "Provider: Nous"])
        b = dashboard_frame("Cron Prompt", ["Paste the Coinbase prompt", "Save job", "Confirm it is active"])
        return slideshow_frames([a, b])
    save_video("cron-windows.mp4", frames)

def gen_cron_mac():
    def frames():
        a = dashboard_frame("Create Cron Job", ["Name: coinbase-equity-vertical", "Schedule: every 10 minutes", "Provider: Nous"])
        b = dashboard_frame("Cron Prompt", ["Paste the Coinbase prompt", "Save job", "Confirm it is active"])
        return slideshow_frames([a, b])
    save_video("cron-mac.mp4", frames)

def gen_three_tabs_windows():
    def frames():
        a = browser_frame("Tab 1", "coinbase.com/portfolio", ["Coinbase portfolio overview", "Balances visible"])
        b = browser_frame("Tab 2", "coinbase.com/advanced-trade", ["Advanced Trading", "Positions and orders"])
        c = dashboard_frame("Tab 3", ["Hermes dashboard", "Chats selected", "Cron is alive"])
        return slideshow_frames([a, b, c])
    save_video("three-tabs-windows.mp4", frames)

def gen_three_tabs_mac():
    def frames():
        a = browser_frame("Tab 1", "coinbase.com/portfolio", ["Coinbase portfolio overview", "Balances visible"])
        b = browser_frame("Tab 2", "coinbase.com/advanced-trade", ["Advanced Trading", "Positions and orders"])
        c = dashboard_frame("Tab 3", ["Hermes dashboard", "Chats selected", "Cron is alive"])
        return slideshow_frames([a, b, c])
    save_video("three-tabs-mac.mp4", frames)

def main():
    gens = [
        ("intro", gen_intro_windows, gen_intro_mac),
        ("never-sleep", gen_never_sleep_windows, gen_never_sleep_mac),
        ("coinbase-signup", gen_coinbase_signup_windows, gen_coinbase_signup_mac),
        ("fund-coinbase", gen_fund_coinbase_windows, gen_fund_coinbase_mac),
        ("nous-key", gen_nous_key_windows, gen_nous_key_mac),
        ("save-key", gen_save_key_windows, gen_save_key_mac),
        ("install-hermes", gen_install_hermes_windows, gen_install_hermes_mac),
        ("provider-model", gen_provider_model_windows, gen_provider_model_mac),
        ("dashboard", gen_dashboard_windows, gen_dashboard_mac),
        ("cron", gen_cron_windows, gen_cron_mac),
        ("three-tabs", gen_three_tabs_windows, gen_three_tabs_mac),
    ]
    for name, wfn, mfn in gens:
        wfn()
        mfn()
    print("DONE")

if __name__ == "__main__":
    main()
