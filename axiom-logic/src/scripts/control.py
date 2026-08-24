from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "data" / "axiom.pid"
LOG_FILE = ROOT / "data" / "axiom.log"


def python_exe() -> str:
    return sys.executable or "python"


def start() -> None:
    if is_running():
        print("Axiom Logic is already running.")
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["AXIOM_MODE"] = "demo"
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [python_exe(), str(ROOT / "src" / "main.py")]
    log = LOG_FILE.open("a", encoding="utf-8")
    p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0)
    PID_FILE.write_text(str(p.pid), encoding="utf-8")
    time.sleep(1.5)
    if p.poll() is not None:
        print(f"Failed to start Axiom Logic. See {LOG_FILE}")
        return
    print(f"Axiom Logic started. PID {p.pid}. Dashboard: http://localhost:8080")


def stop() -> None:
    pid_text = PID_FILE.read_text(encoding="utf-8").strip() if PID_FILE.exists() else ""
    if not pid_text:
        print("No saved PID found. Attempting process scan.")
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = proc.info.get("cmdline") or []
                if any("axiom_logic" in str(x) or "main.py" in str(x) for x in cmd):
                    print(f"Stopping PID {proc.pid} ...")
                    proc.send_signal(signal.SIGTERM if os.name != "nt" else signal.SIGBREAK)
            except (psutil.NoSuchProcess, PermissionError):
                continue
        print("Stop signal sent.")
        return
    pid = int(pid_text)
    try:
        p = psutil.Process(pid)
        if "python" not in (p.name() or "").lower():
            print(f"Saved PID {pid} is not python.")
            return
        p.send_signal(signal.SIGTERM if os.name != "nt" else signal.SIGBREAK)
        print(f"Sent stop signal to PID {pid}.")
    except psutil.NoSuchProcess:
        print("Process not found. Clearing PID file.")
        PID_FILE.unlink(missing_ok=True)
    except PermissionError:
        print("Permission error. Run terminal as admin.")


def is_running() -> bool:
    pid_text = PID_FILE.read_text(encoding="utf-8").strip() if PID_FILE.exists() else ""
    if pid_text:
        try:
            p = psutil.Process(int(pid_text))
            return p.is_running() and "python" in (p.name() or "").lower()
        except Exception:
            PID_FILE.unlink(missing_ok=True)
    return False


def status() -> None:
    if is_running():
        print("Axiom Logic: RUNNING")
    else:
        print("Axiom Logic: STOPPED")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m axiom_logic.scripts.control start|stop|status")
        sys.exit(1)
    action = sys.argv[1].lower()
    {"start": start, "stop": stop, "status": status}[action]()
