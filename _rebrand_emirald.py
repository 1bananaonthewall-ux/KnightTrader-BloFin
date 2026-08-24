from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"C:\Users\mknig\hermes-trader\Emirald")

REPLACEMENTS = [
    ("hermes_trader", "emirald"),
    ("Hermes Trader", "Emirald"),
    ("Hermes", "Emirald"),
    ("hermes.log", "emirald.log"),
    (".hermes.", ".emirald."),
    ("launch_hermes_gui.py", "launch_emirald_gui.py"),
    ("stop_hermes.py", "stop_emirald.py"),
    ("HermesGUI", "EmiraldGUI"),
    ("HermesLoop", "EmiraldLoop"),
    ("Hermes is awake", "Emirald is awake"),
    ("Hermes sleeping", "Emirald sleeping"),
    ("Hermes first-run check", "Emirald first-run check"),
    ("Hermes journal", "Emirald journal"),
    ("You are Hermes", "You are Emirald"),
    ("Hermes with no guardrails", "Emirald with no guardrails"),
    ("Hermes's live prompt", "Emirald's live prompt"),
    ("Hermes Agent", "Emirald Agent"),
]

SKIP_EXTS = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".mp4", ".m4a", ".meta.json"}


def rebrand_file(path: Path) -> None:
    if path.suffix.lower() in SKIP_EXTS:
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    new = text
    for old, new_text in REPLACEMENTS:
        new = new.replace(old, new_text)
    if new != text:
        path.write_text(new, encoding="utf-8")


for path in ROOT.rglob("*"):
    if path.is_file():
        rebrand_file(path)

# Rename known script files after content replacements.
rename_map = {
    ROOT / "scripts" / "launch_hermes_gui.py": ROOT / "scripts" / "launch_emirald_gui.py",
    ROOT / "scripts" / "stop_hermes.py": ROOT / "scripts" / "stop_emirald.py",
    ROOT / "src" / "emirald" / "scripts" / "first_run_check.py": ROOT / "src" / "emirald" / "scripts" / "first_run_check.py",
}
for src, dst in rename_map.items():
    if src.exists() and src != dst:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dst)

print("REBRANDED")
