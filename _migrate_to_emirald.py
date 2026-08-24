from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\mknig\hermes-trader")
DEST = ROOT / "Emirald"

PAIRS = [
    (ROOT / "hermes_trader", DEST / "src"),
    (ROOT / "hermes_trader" / "scripts", DEST / "scripts"),
    (ROOT / "apps" / "dashboard", DEST / "apps" / "dashboard"),
    (ROOT / "tests", DEST / "tests"),
]
FILES = [
    ROOT / "scripts" / "launch_hermes_gui.py",
    ROOT / "scripts" / "stop_hermes.py",
    ROOT / "scripts" / "create_desktop_shortcuts.ps1",
    ROOT / "scripts" / "start_dashboard.ps1",
    ROOT / "scripts" / "stop_hermes_gui.ps1",
    ROOT / "scripts" / "start_hermes_dashboard.ps1",
    ROOT / "scripts" / "axiom-launcher.vbs",
    ROOT / "scripts" / "axiom-start.vbs",
    ROOT / "scripts" / "axiom-stop.vbs",
    ROOT / "config.yaml",
    ROOT / ".env.example",
    ROOT / ".env",
    ROOT / "requirements.txt",
    ROOT / "backtest.py",
    ROOT / "README.md",
]

for src, dst in PAIRS:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

for src in FILES:
    if src.exists():
        dst = DEST / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

print("MIGRATED")
