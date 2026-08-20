from render_assets import (
    draw_panel, draw_mini_browser, draw_text_window,
    draw_start_or_apple, load_font, OUT, VIDEO_DIR, SHOT_DIR,
    build_shot, build_clip, multi_frame_still,
    WINDOWS, MAC
)

def scene_welcome(draw, cfg, W, H, frame=0):
    cx = W / 2
    # app icon
    draw_start_or_apple(draw, cx, 60, 90, cfg)
    f = load_font(26)
    draw.text((cx - 180, 170), "KnightTrader Walkthru", fill=cfg["accent"], font=f)
    f2 = load_font(18)
    draw.text((cx - 220, 206), "Hermes on Coinbase — beginner setup", fill=(200, 206, 214), font=f2)

    # browser mock on the right
    draw_mini_browser(draw, cx + 290, 140, 620, 360, cfg)
    # text window mock on the left
    draw_text_window(
        draw, cx - 280, 200, 520, 320, cfg,
        ["$ hermes dashboard",
         "",
         "Dashboard starting at http://127.0.0.1:9119",
         "",
         "Provider: Nous",
         "Model: tencent/hy free",
         "",
         "Cron: every 10 minutes"],
        cfg["terminal_label"]
    )
    # subtitle
    f3 = load_font(16)
    draw.text((cx - 230, 600), "Windows and Mac, step by step, with video walkthroughs.", fill=(180, 186, 194), font=f3)

def scene_never_sleep(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_start_or_apple(draw, cx, 50, 80, cfg)
    draw_mini_browser(draw, cx + 260, 90, 700, 340, cfg)
    # settings window
    settings_x = cx - 260
    settings_w = 480
    settings_h = 380
    draw_panel(draw, settings_x, 130, settings_w, settings_h, fill=(26, 30, 35), border=(64, 70, 78))
    f = load_font(16)
    draw.text((settings_x + 16, 150), "System settings - Power", fill=cfg["accent"], font=f)
    items = [
        ("Screen and sleep", True),
        ("Turn off my screen after", True),
        ("  Never", True),
        ("Put my device to sleep after", True),
        ("  Never", True),
        ("When I close the lid", True),
        ("  Do nothing (while plugged in)", True),
    ]
    y = 186
    for label, on in items:
        col = cfg["accent"] if on else (160, 166, 174)
        draw.text((settings_x + 20, y), label, fill=col, font=load_font(14))
        y += 26
    # wifi window
    wifi_x = cx - 220
    draw_panel(draw, wifi_x, 540, 420, 120, fill=(26, 30, 35), border=(64, 70, 78))
    draw.text((wifi_x + 14, 560), "Network", fill=cfg["accent"], font=load_font(14))
    draw.text((wifi_x + 14, 584), "Status: Connected", fill=(140, 220, 160), font=load_font(13))
    draw.text((wifi_x + 14, 606), "Internet access: yes", fill=(140, 220, 160), font=load_font(13))

def scene_coinbase_signup(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_mini_browser(draw, cx, 100, 760, 440, cfg)
    f = load_font(15)
    draw.text((cx - 260, 580), "coinbase.com - Sign up", fill=cfg["accent"], font=f)
    draw.text((cx - 260, 604), "Email -> verify -> ID check -> payment method -> buy", fill=(180, 186, 194), font=load_font(13))

def scene_fund(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_mini_browser(draw, cx, 120, 780, 420, cfg)
    f = load_font(15)
    draw.text((cx - 280, 580), "Buy crypto on Coinbase", fill=cfg["accent"], font=f)
    draw.text((cx - 280, 604), "Choose asset -> payment method -> fee preview -> confirm", fill=(180, 186, 194), font=load_font(13))

def scene_nous(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_mini_browser(draw, cx, 120, 780, 400, cfg)
    panel_x = cx - 300
    draw_panel(draw, panel_x, 200, 560, 220, fill=(24, 28, 32), border=(64, 70, 78))
    draw.text((panel_x + 16, 220), "Nous Portal - API key", fill=cfg["accent"], font=load_font(15))
    key = "nous_sk_ ...................................."
    draw.text((panel_x + 16, 250), "API key: " + key, fill=(220, 224, 230), font=load_font(13))
    draw.text((panel_x + 16, 280), "[ Copy ]   Save this carefully.", fill=(180, 200, 255), font=load_font(13))
    draw.text((panel_x + 16, 310), "Sign in once if Hermes asks later.", fill=(180, 186, 194), font=load_font(13))

def scene_save_key(draw, cfg, W, H, frame=0):
    cx = W / 2
    # text editor
    if cfg["icon"] == "start":
        editor_x = cx - 300
    else:
        editor_x = cx - 280
    draw_text_window(
        draw, cx, 150, 560, 360, cfg,
        ["Passphrase: YOUR_PASSPHRASE",
         "API Key: YOUR_API_KEY",
         "API Secret: YOUR_API_SECRET",
         "",
         "Saved as: My Coinbase API Keys.txt",
         "Location: Downloads"],
        cfg["terminal_label"]
    )
    draw.text((cx - 200, 560), "Plain text file, not rich text.", fill=cfg["accent"], font=load_font(14))

def scene_install(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_start_or_apple(draw, cx, 60, 80, cfg)
    cmd = ("iex (irm https://hermes-agent.nousresearch.com/install.ps1)"
           if cfg["icon"] == "start"
           else "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash")
    draw_text_window(
        draw, cx, 170, 660, 340, cfg,
        ["$ " + cmd,
         "",
         "Installing Hermes...",
         "This can take a few minutes.",
         "",
         "When it finishes:",
         "hermes --version",
         "hermes doctor"],
        cfg["terminal_label"]
    )
    f = load_font(14)
    draw.text((cx - 280, 560), "Copy the install command and paste it into the text window.", fill=(180, 186, 194), font=f)

def scene_provider_model(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_mini_browser(draw, cx, 120, 780, 400, cfg)
    panel_x = cx - 300
    draw_panel(draw, panel_x, 180, 560, 240, fill=(24, 28, 32), border=(64, 70, 78))
    draw.text((panel_x + 16, 200), "Hermes dashboard - model settings", fill=cfg["accent"], font=load_font(15))
    rows = [("Provider", "Nous"), ("Model", "tencent/hy free")]
    y = 240
    for k, v in rows:
        draw.text((panel_x + 20, y), k, fill=(180, 186, 194), font=load_font(13))
        draw.text((panel_x + 150, y), v, fill=cfg["accent"], font=load_font(13))
        y += 30
    draw.text((panel_x + 16, 300), "Save. Then move to cron.", fill=(180, 186, 194), font=load_font(13))

def scene_dashboard(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_mini_browser(draw, cx, 110, 780, 440, cfg)
    panel_x = cx - 300
    draw_panel(draw, panel_x, 200, 560, 240, fill=(24, 28, 32), border=(64, 70, 78))
    draw.text((panel_x + 16, 220), "Hermes dashboard - http://127.0.0.1:9119", fill=cfg["accent"], font=load_font(14))
    f = load_font(13)
    items = ["Dashboard", "Chats", "Cron", "Settings"]
    for i, it in enumerate(items):
        active = it == "Cron"
        col = cfg["accent"] if active else (180, 186, 194)
        draw.text((panel_x + 20, 250 + i * 28), it, fill=col, font=f)
    draw.text((panel_x + 16, 360), "Keep this command window open.", fill=(220, 224, 230), font=load_font(13))

def scene_cron(draw, cfg, W, H, frame=0):
    cx = W / 2
    draw_mini_browser(draw, cx, 120, 780, 420, cfg)
    panel_x = cx - 320
    draw_panel(draw, panel_x, 220, 600, 300, fill=(24, 28, 32), border=(64, 70, 78))
    draw.text((panel_x + 16, 240), "Cron - new scheduled job", fill=cfg["accent"], font=load_font(15))
    rows = [
        ("Schedule", "every 10 minutes"),
        ("Name", "coinbase-equity-vertical"),
        ("Provider", "Nous"),
        ("Model", "tencent/hy free"),
        ("Delivery", "local"),
    ]
    y = 280
    for k, v in rows:
        draw.text((panel_x + 20, y), k, fill=(180, 186, 194), font=load_font(13))
        draw.text((panel_x + 150, y), v, fill=cfg["accent"], font=load_font(13))
        y += 28
    draw.text((panel_x + 16, 420), "Paste the Coinbase Cron Prompt, save, run once.", fill=(180, 200, 255), font=load_font(13))

def scene_three_tabs(draw, cfg, W, H, frame=0):
    cx = W / 2
    # three browser tabs
    positions = [(-320, 90), (0, 90), (320, 90)]
    labels = ["Coinbase portfolio", "Coinbase Advanced Trading", "Hermes dashboard - chats"]
    for (x, y), label in zip(positions, labels):
        draw_mini_browser(draw, cx + x, y, 320, 360, cfg)
        draw.text((cx + x - 120, y + 400), label, fill=cfg["accent"], font=load_font(13))

# Windows shorts
build_shot("windows", "welcome", scene_welcome)
build_shot("windows", "never-sleep", scene_never_sleep)
build_shot("windows", "coinbase-signup", scene_coinbase_signup)
build_shot("windows", "fund", scene_fund)
build_shot("windows", "nous", scene_nous)
build_shot("windows", "save-key", scene_save_key)
build_shot("windows", "install", scene_install)
build_shot("windows", "provider-model", scene_provider_model)
build_shot("windows", "dashboard", scene_dashboard)
build_shot("windows", "cron", scene_cron)
build_shot("windows", "three-tabs", scene_three_tabs)

# Mac shorts
build_shot("mac", "welcome", scene_welcome)
build_shot("mac", "never-sleep", scene_never_sleep)
build_shot("mac", "coinbase-signup", scene_coinbase_signup)
build_shot("mac", "fund", scene_fund)
build_shot("mac", "nous", scene_nous)
build_shot("mac", "save-key", scene_save_key)
build_shot("mac", "install", scene_install)
build_shot("mac", "provider-model", scene_provider_model)
build_shot("mac", "dashboard", scene_dashboard)
build_shot("mac", "cron", scene_cron)
build_shot("mac", "three-tabs", scene_three_tabs)

# Clips: intro + major walkthroughs
build_clip("windows", "intro",
    "A calm welcome: this is KnightTrader Walkthru, the Hermes on Coinbase beginner setup. Pick Windows or Mac and the whole page changes to your computer.",
    scene_welcome)
build_clip("mac", "intro",
    "A calm welcome: this is KnightTrader Walkthru, the Hermes on Coinbase beginner setup. Pick Windows or Mac and the whole page changes to your computer.",
    scene_welcome)

build_clip("windows", "never-sleep",
    "Set the computer to never sleep and confirm internet is connected. On Windows, that means Power and sleep set to Never, lid closed behavior set to Do nothing while plugged in, and a quick site load to prove internet is there.",
    scene_never_sleep)
build_clip("mac", "never-sleep",
    "Set the Mac to never sleep. That means display off set to Never, prevent automatic sleeping on power adapter turned on, lid open while learning, plugged in, and a quick site load to prove internet is there.",
    scene_never_sleep)

build_clip("windows", "install",
    "Install Hermes on Windows. Open PowerShell, copy the install command, paste it, wait for it to finish, then run hermes --version and hermes doctor in a new PowerShell window.",
    scene_install)
build_clip("mac", "install",
    "Install Hermes on Mac. Open Terminal, copy the install command, paste it, let it finish, open a new Terminal window, then run hermes --version and hermes doctor.",
    scene_install)

build_clip("windows", "dashboard",
    "Bring up the Hermes dashboard on Windows. Run hermes dashboard in the same PowerShell window, or open http://127.0.0.1:9119 yourself. Keep that window open.",
    scene_dashboard)
build_clip("mac", "dashboard",
    "Bring up the Hermes dashboard on Mac. Run hermes dashboard in Terminal, or open http://127.0.0.1:9119 yourself. Keep that Terminal window open.",
    scene_dashboard)

build_clip("windows", "cron",
    "Set up the 10-minute cron job on Windows. Create a new scheduled job in the dashboard, set schedule to every 10 minutes, name it coinbase-equity-vertical, provider Nous, model tencent/hy free, then paste the Coinbase Cron Prompt and run it once.",
    scene_cron)
build_clip("mac", "cron",
    "Set up the 10-minute cron job on Mac. Create a new scheduled job in the dashboard, set schedule to every 10 minutes, name it coinbase-equity-vertical, provider Nous, model tencent/hy free, then paste the Coinbase Cron Prompt and run it once.",
    scene_cron)

build_clip("windows", "three-tabs",
    "When you finish, leave three tabs open: Coinbase portfolio overview, Coinbase Advanced Trading, and the Hermes dashboard with chats selected.",
    scene_three_tabs)
build_clip("mac", "three-tabs",
    "When you finish, leave three tabs open: Coinbase portfolio overview, Coinbase Advanced Trading, and the Hermes dashboard with chats selected.",
    scene_three_tabs)

print("done")
