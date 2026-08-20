"""Stop Hermes agent, GUI launcher, and dashboard processes for this project."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PID_FILE = Path(".hermes.pid")
DASHBOARD_PORT = 8766
DASH_PID_FILE = Path(".hermes_dashboard.pid")


def _find_project_root(start: Path) -> Path:
    root = start.resolve()
    for parent in [root] + list(root.parents):
        if (parent / "config.yaml").exists() and (parent / "hermes_trader").exists():
            return parent
    return root


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        m = re.search(r"\d+", text)
        return int(m.group()) if m else None
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return False
    return str(pid) in (out or "")


def _terminate_pid(pid: int) -> bool:
    if pid <= 4:  # skip idle/system
        return False
    if not _pid_alive(pid):
        return True
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    for _ in range(40):
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)
    return not _pid_alive(pid)


def _process_commandlines() -> list[tuple[int, str]]:
    ps = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId, CommandLine | "
        "ConvertTo-Csv -NoTypeInformation"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return []
    rows: list[tuple[int, str]] = []
    for i, line in enumerate(out.splitlines()):
        if i == 0 or not line.strip():
            continue
        # "ProcessId","CommandLine"
        m = re.match(r'^"(\d+)","(.*)"$', line)
        if not m:
            # Fallback split for simpler rows
            parts = line.split(",", 1)
            if len(parts) != 2:
                continue
            try:
                rows.append((int(parts[0].strip('"')), parts[1].strip('"')))
            except ValueError:
                continue
            continue
        try:
            rows.append((int(m.group(1)), m.group(2).replace('""', '"')))
        except ValueError:
            continue
    return rows


def _kill_matching(root: Path) -> list[int]:
    root_s = str(root).lower().replace("/", "\\")
    killed: list[int] = []
    needles = (
        "hermes_trader",
        "launch_hermes_gui.py",
        "apps.dashboard.main",
        "start_dashboard.ps1",
    )
    self_pid = os.getpid()
    for pid, cmd in _process_commandlines():
        if pid in (0, self_pid):
            continue
        low = (cmd or "").lower().replace("/", "\\")
        if "stop_hermes.py" in low:
            continue
        if root_s not in low and "hermes-trader" not in low:
            if "apps.dashboard.main" not in low and "launch_hermes_gui.py" not in low:
                continue
        if not any(n in low for n in needles):
            continue
        if _terminate_pid(pid):
            killed.append(pid)
    return killed


def _kill_port_listeners(port: int) -> list[int]:
    killed: list[int] = []
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
             "Select-Object -ExpandProperty OwningProcess -Unique"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return killed
    for line in out.splitlines():
        line = line.strip()
        if not line.isdigit():
            continue
        pid = int(line)
        if pid > 4 and _terminate_pid(pid):
            killed.append(pid)
    return killed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stop Hermes agent + dashboard")
    parser.add_argument("workdir", nargs="?", default=".")
    parser.add_argument("--quiet", action="store_true", help="no message box")
    args = parser.parse_args(argv)

    working = _find_project_root(Path(args.workdir).resolve())
    os.chdir(working)

    killed: list[int] = []
    pid = _read_pid(working / PID_FILE)
    if pid is not None:
        if _terminate_pid(pid):
            killed.append(pid)

    killed.extend(_kill_matching(working))
    killed.extend(_kill_port_listeners(DASHBOARD_PORT))

    dash_pid = _read_pid(working / DASH_PID_FILE)
    if dash_pid is not None:
        if _terminate_pid(dash_pid):
            killed.append(dash_pid)

    for name in [PID_FILE.name, DASH_PID_FILE.name, ".hermes.lock", ".hermes_gui.pid"]:
        p = working / name
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    unique = sorted(set(killed))
    msg = (
        f"Stopped Hermes (killed {len(unique)} process tree(s))."
        if unique
        else "No running Hermes agent/dashboard found. Cleared lock files."
    )
    if not args.quiet:
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Hermes", msg)
            root.destroy()
        except Exception:
            print(msg)
    else:
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
