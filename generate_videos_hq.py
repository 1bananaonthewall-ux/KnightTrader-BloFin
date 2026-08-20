import os
import math
from PIL import Image, ImageDraw, ImageFont

VIDEO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_videos")
os.makedirs(VIDEO_ROOT, exist_ok=True)

W, H = 1280, 720
FPS = 30
DURATION_SEC = 18

_font_cache = {}

def font(size):
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype("arial.ttf", size)
        except Exception:
            _font_cache[size] = ImageFont.load_default(size=size)
    return _font_cache[size]

def make_background():
    bg = Image.new("RGB", (W, H), (15, 17, 21))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([0, 0, W, 64], fill=(27, 31, 37))
    draw.text((24, 16), "KnightTrader Walkthru", fill=(230, 233, 238), font=font(26))
    return bg, draw

def browser_frame(title, url, body_lines, highlight=None):
    bg, draw = make_background()
    draw.rectangle([0, 64, W, H], fill=(255, 255, 255))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([24, 78, 520, 106], fill=(255, 255, 255), outline=(180, 185, 192), width=2)
    draw.text((44, 80), url, fill=(60, 64, 70), font=font(18))
    draw.text((24, 116), title, fill=(20, 24, 30), font=font(28))
    y = 170
    for line in body_lines:
        color = (20, 24, 30)
        if highlight and line.startswith(highlight):
            color = (120, 40, 40)
        draw.text((24, y), line, fill=color, font=font(20))
        y += 36
    return bg

def terminal_frame(title, lines, os_name="windows"):
    bg, draw = make_background()
    draw.rectangle([0, 64, W, H], fill=(12, 14, 18))
    draw = ImageDraw.Draw(bg)
    draw.text((24, 116), title, fill=(230, 233, 238), font=font(26))
    y = 172
    for line in lines:
        draw.text((24, y), line, fill=(210, 220, 220), font=font(20))
        y += 36
    return bg

def dashboard_frame(title, items, selected=None):
    bg, draw = make_background()
    draw.rectangle([0, 64, W, H], fill=(20, 24, 30))
    draw = ImageDraw.Draw(bg)
    draw.text((24, 100), title, fill=(240, 225, 140), font=font(28))
    y = 164
    for item in items:
        border = (90, 125, 255) if selected and item.startswith(selected) else (60, 68, 80)
        fill = (28, 32, 40) if selected and item.startswith(selected) else (30, 35, 43)
        draw.rounded_rectangle([24, y, 720, y + 72], radius=14, fill=fill, outline=border, width=2)
        draw.text((44, y + 20), item, fill=(220, 225, 235), font=font(20))
        y += 96
    return bg

def slideshow(images, total_frames=None):
    if total_frames is None:
        total_frames = FPS * DURATION_SEC
    per = max(1, total_frames // max(1, len(images)))
    for i in range(total_frames):
        idx = min(len(images) - 1, i // per)
        yield images[idx]

def write_video(path, frame_gen, tone_hz=520):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_img = path + ".png"
    temp_audio = path + ".wav"
    frames = list(frame_gen())
    if not frames:
        return
    frames[0].save(temp_img, "PNG")
    frames[0].close()

    import wave, struct
    rate = 48000
    n = DURATION_SEC * rate
    with wave.open(temp_audio, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(n):
            t = i / rate
            env = 0.25 * (1 - abs(t - DURATION_SEC / 2) / (DURATION_SEC / 2))
            val = int(32767 * max(env, 0.12) * math.sin(2 * math.pi * tone_hz * t))
            w.writeframes(struct.pack("<h", val))

    cmd = (
        f'ffmpeg -y -framerate {FPS} -i "{temp_img}" -i "{temp_audio}" '
        f'-c:v libx264 -tune stillimage -pix_fmt yuv420p -shortest -c:a aac "{path}"'
    )
    os.system(cmd)
    for extra in [temp_img, temp_audio]:
        if os.path.exists(extra):
            os.remove(extra)

def save_video(name, frame_fn, tone_hz=520):
    path = os.path.join(VIDEO_ROOT, name)
    write_video(path, frame_fn, tone_hz=tone_hz)
    print("created", path, "size", os.path.getsize(path))

def gen_intro_windows():
    def frames():
        a = browser_frame("Welcome", "knighttrader.local", ["This tutorial supports Windows and Mac.", "Use the tabs below to pick your OS."])
        b = browser_frame("What you will do", "knighttrader.local/setup", ["1. Stay awake + online", "2. Create and fund Coinbase", "3. Install Hermes and run a 10-minute cron"])
        return slideshow([a, b])
    save_video("intro-windows.mp4", frames, tone_hz=520)

def gen_intro_mac():
    def frames():
        a = browser_frame("Welcome", "knighttrader.local", ["This tutorial supports Windows and Mac.", "Use the tabs below to pick your OS."])
        b = browser_frame("What you will do", "knighttrader.local/setup", ["1. Stay awake + online", "2. Create and fund Coinbase", "3. Install Hermes and run a 10-minute cron"])
        return slideshow([a, b])
    save_video("intro-mac.mp4", frames, tone_hz=580)

def gen_never_sleep_windows():
    def frames():
        a = browser_frame("Power & sleep", "Windows Settings", ["Search: Power & sleep", "Screen: Never when plugged in", "Sleep: Never when plugged in", "Optional: lid-do-nothing when plugged in"])
        b = terminal_frame("PowerShell", ["powercfg /change standby-timeout-ac 0", "powercfg /change standby-timeout-dc 0", "powercfg /change monitor-timeout-ac 0", "powercfg /change monitor-timeout-dc 0", "powercfg /change hibernate-timeout-ac 0", "powercfg /change hibernate-timeout-dc 0"])
        c = browser_frame("Network", "Settings > Network", ["Confirm Wi-Fi or Ethernet is connected", "Try opening a website to verify"])
        return slideshow([a, b, c])
    save_video("never-sleep-windows.mp4", frames, tone_hz=540)

def gen_never_sleep_mac():
    def frames():
        a = browser_frame("System Settings", "System Settings", ["Open Battery or Energy Saver", "Set display sleep to Never on power adapter", "Keep the lid open while Hermes runs if you can"])
        b = terminal_frame("Terminal", ["caffeinate -dimsu", "Mac will stay awake while this command runs."])
        c = browser_frame("Network", "System Settings > Network", ["Confirm Wi-Fi is connected", "Open a website to confirm internet is working"])
        return slideshow([a, b, c])
    save_video("never-sleep-mac.mp4", frames, tone_hz=620)

def gen_coinbase_signup_windows():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Click Sign up or Get started", "Use a real email", "Use a password you will remember"])
        b = browser_frame("Verify", "coinbase.com/verify", ["Verify email", "Verify phone", "Complete identity check if asked"])
        return slideshow([a, b])
    save_video("coinbase-signup-windows.mp4", frames, tone_hz=500)

def gen_coinbase_signup_mac():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Click Sign up or Get started", "Use a real email", "Use a password you will remember"])
        b = browser_frame("Verify", "coinbase.com/verify", ["Verify email", "Verify phone", "Complete identity check if asked"])
        return slideshow([a, b])
    save_video("coinbase-signup-mac.mp4", frames, tone_hz=560)

def gen_fund_coinbase_windows():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Open Buy or Trade", "Pick a first crypto", "Use the payment method Coinbase shows"])
        b = browser_frame("Wallet", "coinbase.com/wallet", ["Review fee preview", "Confirm purchase", "Wait for balance to appear"])
        return slideshow([a, b])
    save_video("fund-coinbase-windows.mp4", frames, tone_hz=480)

def gen_fund_coinbase_mac():
    def frames():
        a = browser_frame("Coinbase", "coinbase.com", ["Open Buy or Trade", "Pick a first crypto", "Use the payment method Coinbase shows"])
        b = browser_frame("Wallet", "coinbase.com/wallet", ["Review fee preview", "Confirm purchase", "Wait for balance to appear"])
        return slideshow([a, b])
    save_video("fund-coinbase-mac.mp4", frames, tone_hz=530)

def gen_nous_key_windows():
    def frames():
        a = browser_frame("Nous Portal", "portal.nousresearch.com", ["Sign in or create an account", "Open the API key area"])
        b = browser_frame("API key", "portal.nousresearch.com/keys", ["Create a new key", "Copy it once", "Save it carefully"])
        return slideshow([a, b])
    save_video("nous-key-windows.mp4", frames, tone_hz=600)

def gen_nous_key_mac():
    def frames():
        a = browser_frame("Nous Portal", "portal.nousresearch.com", ["Sign in or create an account", "Open the API key area"])
        b = browser_frame("API key", "portal.nousresearch.com/keys", ["Create a new key", "Copy it once", "Save it carefully"])
        return slideshow([a, b])
    save_video("nous-key-mac.mp4", frames, tone_hz=650)

def gen_save_key_windows():
    def frames():
        a = terminal_frame("Notepad", ["Open Notepad", "Paste key and values", "Save as Coinbase MK API Keys.txt"])
        b = browser_frame("Downloads", "file:///C:/Users/you/Downloads", ["Save in Downloads for now", "Do not email this file"])
        return slideshow([a, b])
    save_video("save-key-windows.mp4", frames, tone_hz=510)

def gen_save_key_mac():
    def frames():
        a = terminal_frame("TextEdit", ["Open TextEdit", "Format > Make Plain Text", "Paste key and values", "Save to Downloads"])
        b = browser_frame("Downloads", "file:///Users/you/Downloads", ["File should be visible now", "Keep it local and safe"])
        return slideshow([a, b])
    save_video("save-key-mac.mp4", frames, tone_hz=570)

def gen_install_hermes_windows():
    def frames():
        a = terminal_frame("PowerShell", ["Right-click to paste", "winget install HermesProject.Hermes", "Wait for install to finish"])
        b = terminal_frame("PowerShell", ["hermes --version", "hermes doctor", "Installed and ready."])
        return slideshow([a, b])
    save_video("install-hermes-windows.mp4", frames, tone_hz=490)

def gen_install_hermes_mac():
    def frames():
        a = terminal_frame("Terminal", ["brew install hermes", "Allow developer tools if prompted"])
        b = terminal_frame("Terminal", ["hermes --version", "hermes doctor", "Installed and ready."])
        return slideshow([a, b])
    save_video("install-hermes-mac.mp4", frames, tone_hz=550)

def gen_provider_model_windows():
    def frames():
        a = dashboard_frame("Hermes Settings", ["Provider: Nous", "Model: tencent/hy free", "Save settings"], selected="Provider")
        b = dashboard_frame("Settings saved", ["Provider confirmed", "Model confirmed", "Ready for dashboard"])
        return slideshow([a, b])
    save_video("provider-model-windows.mp4", frames, tone_hz=630)

def gen_provider_model_mac():
    def frames():
        a = dashboard_frame("Hermes Settings", ["Provider: Nous", "Model: tencent/hy free", "Save settings"], selected="Provider")
        b = dashboard_frame("Settings saved", ["Provider confirmed", "Model confirmed", "Ready for dashboard"])
        return slideshow([a, b])
    save_video("provider-model-mac.mp4", frames, tone_hz=680)

def gen_dashboard_windows():
    def frames():
        a = terminal_frame("PowerShell", ["hermes dashboard", "Opening browser automatically..."])
        b = dashboard_frame("Hermes Dashboard", ["Chats selected", "Cron section visible", "Local URL: 127.0.0.1:9119"], selected="Chats")
        return slideshow([a, b])
    save_video("dashboard-windows.mp4", frames, tone_hz=500)

def gen_dashboard_mac():
    def frames():
        a = terminal_frame("Terminal", ["hermes dashboard", "Opening browser automatically..."])
        b = dashboard_frame("Hermes Dashboard", ["Chats selected", "Cron section visible", "Local URL: 127.0.0.1:9119"], selected="Chats")
        return slideshow([a, b])
    save_video("dashboard-mac.mp4", frames, tone_hz=560)

def gen_cron_windows():
    def frames():
        a = dashboard_frame("Create Cron Job", ["Name: coinbase-equity-vertical", "Schedule: every 10 minutes", "Provider: Nous", "Model: tencent/hy free"], selected="Name")
        b = dashboard_frame("Cron Prompt", ["Paste the Coinbase prompt", "Save job", "Confirm it is active"])
        return slideshow([a, b])
    save_video("cron-windows.mp4", frames, tone_hz=590)

def gen_cron_mac():
    def frames():
        a = dashboard_frame("Create Cron Job", ["Name: coinbase-equity-vertical", "Schedule: every 10 minutes", "Provider: Nous", "Model: tencent/hy free"], selected="Name")
        b = dashboard_frame("Cron Prompt", ["Paste the Coinbase prompt", "Save job", "Confirm it is active"])
        return slideshow([a, b])
    save_video("cron-mac.mp4", frames, tone_hz=640)

def gen_three_tabs_windows():
    def frames():
        a = browser_frame("Tab 1", "coinbase.com/portfolio", ["Coinbase portfolio overview", "Balances visible"])
        b = browser_frame("Tab 2", "coinbase.com/advanced-trade", ["Advanced Trading", "Positions and orders"])
        c = dashboard_frame("Tab 3", ["Hermes dashboard", "Chats selected", "Cron is alive"], selected="Chats")
        return slideshow([a, b, c])
    save_video("three-tabs-windows.mp4", frames, tone_hz=470)

def gen_three_tabs_mac():
    def frames():
        a = browser_frame("Tab 1", "coinbase.com/portfolio", ["Coinbase portfolio overview", "Balances visible"])
        b = browser_frame("Tab 2", "coinbase.com/advanced-trade", ["Advanced Trading", "Positions and orders"])
        c = dashboard_frame("Tab 3", ["Hermes dashboard", "Chats selected", "Cron is alive"], selected="Chats")
        return slideshow([a, b, c])
    save_video("three-tabs-mac.mp4", frames, tone_hz=520)

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
