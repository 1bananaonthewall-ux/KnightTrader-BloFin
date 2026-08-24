from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\mknig\hermes-trader\Emirald")
SRC = ROOT / "src"
PKG = SRC / "emirald"
PKG_SCRIPTS = PKG / "scripts"

PKG.mkdir(parents=True, exist_ok=True)
PKG_SCRIPTS.mkdir(parents=True, exist_ok=True)

for p in list(SRC.iterdir()):
    if p.is_file() and p.suffix == ".py":
        target = PKG / p.name
        if target.exists():
            target.unlink()
        shutil.move(str(p), str(target))
    elif p.is_dir() and p.name == "scripts":
        for q in list(p.iterdir()):
            target = PKG_SCRIPTS / q.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(q), str(target))
        p.rmdir()

print("RESTRUCTURED")
