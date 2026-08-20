"""Launch Hermes Trader: visible control window + agent console + dashboard.

Desktop shortcut should run this with python.exe (not pythonw) so the
Tk control room stays visible. The agent runs in its own console window.
Dashboard serves http://127.0.0.1:8766/ (not KnightTrader's 8765).
"""
from __future__ import annotations

import argparse
import ctypes
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import font, messagebox, ttk

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
    except Exception:
        pass

PID_FILE = Path(".hermes.pid")
DASH_PID_FILE = Path(".hermes_dashboard.pid")
DASHBOARD_PORT = 8766
DASHBOARD_URL = f"http://127.0.0.1:{DASHBOARD_PORT}/"
LOG_TAIL_LINES = 400
LOG_REFRESH_MS = 1000
STATS_REFRESH_MS = 1000


def _find_project_root(start: Path) -> Path:
    root = start.resolve()
    for parent in [root] + list(root.parents):
        if (parent / "config.yaml").exists() and (parent / "hermes_trader").exists():
            return parent
    return root


def _pid_alive(pid: int) -> bool:
    if pid <= 4:
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        return str(pid) in (out or "")
    except Exception:
        return False


def _terminate_pid(pid: int, *, timeout: float = 10.0) -> bool:
    if pid <= 4:
        return False
    if not _pid_alive(pid):
        return True
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    start = time.time()
    while time.time() - start < timeout:
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)
    return not _pid_alive(pid)


def _read_pid(pid_path: Path) -> int | None:
    if not pid_path.exists():
        return None
    try:
        text = pid_path.read_text(encoding="utf-8", errors="ignore").strip()
        m = re.search(r"\d+", text)
        return int(m.group()) if m else None
    except Exception:
        return None


def _write_pid(pid_path: Path, pid: int) -> None:
    pid_path.write_text(f"{pid}\n", encoding="utf-8")


def _clear_pid(pid_path: Path) -> None:
    try:
        if pid_path.exists():
            pid_path.unlink()
    except Exception:
        pass


def _python_exe(root: Path) -> Path:
    exe = root / ".venv" / "Scripts" / "python.exe"
    return exe if exe.exists() else Path(sys.executable)


def _find_hermes_agent_pids(root: Path) -> list[int]:
    root_s = str(root).lower().replace("/", "\\")
    found: list[int] = []
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine } | "
                "Select-Object ProcessId, CommandLine | ConvertTo-Csv -NoTypeInformation",
            ],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return found
    for i, line in enumerate(out.splitlines()):
        if i == 0 or not line.strip():
            continue
        m = re.match(r'^"(\d+)","(.*)"$', line)
        if not m:
            continue
        pid = int(m.group(1))
        cmd = m.group(2).replace('""', '"').lower().replace("/", "\\")
        if pid == os.getpid():
            continue
        if "hermes-trader" not in cmd and root_s not in cmd:
            continue
        if "-m hermes_trader" in cmd or "hermes_trader.__main__" in cmd:
            found.append(pid)
    return found


def _stop_existing_agent(root: Path, *, prompt: bool = True) -> None:
    pid_path = root / PID_FILE
    pids = []
    stored = _read_pid(pid_path)
    if stored and _pid_alive(stored):
        pids.append(stored)
    pids.extend(_find_hermes_agent_pids(root))
    pids = sorted(set(pids))
    if not pids:
        _clear_pid(pid_path)
        return
    if prompt:
        joined = ", ".join(str(p) for p in pids)
        if not messagebox.askyesno("Hermes", f"Hermes agent already running (PID {joined}). Stop it and relaunch?"):
            sys.exit(0)
    for pid in pids:
        _terminate_pid(pid)
    _clear_pid(pid_path)


def _dashboard_up() -> bool:
    try:
        with urllib.request.urlopen(DASHBOARD_URL, timeout=2) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        return "Hermes Trader" in body and "KnightTrader" not in body
    except Exception:
        return False


def _start_dashboard(root: Path) -> subprocess.Popen | None:
    if _dashboard_up():
        return None
    # Free wrong listeners on Hermes port only.
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-NetTCPConnection -LocalPort {DASHBOARD_PORT} -State Listen -ErrorAction SilentlyContinue | "
                "Select-Object -ExpandProperty OwningProcess -Unique",
            ],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        for line in out.splitlines():
            line = line.strip()
            if line.isdigit() and int(line) > 4:
                _terminate_pid(int(line))
    except Exception:
        pass

    exe = _python_exe(root)
    creation = 0
    if sys.platform == "win32":
        creation = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    proc = subprocess.Popen(
        [
            str(exe),
            "-m",
            "uvicorn",
            "apps.dashboard.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(DASHBOARD_PORT),
        ],
        cwd=str(root),
        env={**os.environ, "HERMES_HOME": str(root)},
        creationflags=creation,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _write_pid(root / DASH_PID_FILE, proc.pid)
    deadline = time.time() + 25
    while time.time() < deadline:
        if _dashboard_up():
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.4)
    return proc


def _open_dashboard_browser() -> None:
    try:
        os.startfile(DASHBOARD_URL)  # type: ignore[attr-defined]
    except Exception:
        subprocess.Popen(["cmd", "/c", "start", "", DASHBOARD_URL], shell=False)


def _start_bot(root: Path) -> subprocess.Popen:
    """Start agent as a detached background process (survives closing the GUI)."""
    exe = _python_exe(root)
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    stdout_path = data / "agent_stdout.log"
    stderr_path = data / "agent_stderr.log"
    stdout_f = open(stdout_path, "a", encoding="utf-8")  # noqa: SIM115
    stderr_f = open(stderr_path, "a", encoding="utf-8")  # noqa: SIM115
    cmd = [str(exe), "-u", "-m", "hermes_trader"]
    env = {**os.environ, "HERMES_HOME": str(root), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    popen_kwargs: dict[str, object] = {
        "cwd": str(root),
        "env": env,
        "stdout": stdout_f,
        "stderr": stderr_f,
    }
    if sys.platform == "win32":
        # Detached + no console: closing the control room / console must not kill agent.
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
            | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        )
        popen_kwargs["close_fds"] = True
    proc = subprocess.Popen(cmd, **popen_kwargs)  # type: ignore[arg-type]
    _write_pid(root / PID_FILE, proc.pid)
    return proc


def _existing_agent_pid(root: Path) -> int | None:
    stored = _read_pid(root / PID_FILE)
    if stored and _pid_alive(stored):
        return stored
    found = _find_hermes_agent_pids(root)
    return found[0] if found else None


def _gui_lock_path(root: Path) -> Path:
    return root / ".hermes_gui.pid"


def _claim_gui_singleton(root: Path) -> bool:
    """Return True if this process owns the GUI. If another live GUI exists, False."""
    lock = _gui_lock_path(root)
    existing = _read_pid(lock)
    if existing and existing != os.getpid() and _pid_alive(existing):
        return False
    _write_pid(lock, os.getpid())
    return True


def _focus_existing_gui(root: Path) -> bool:
    """Best-effort: bring existing Hermes Trader window to the foreground."""
    pid = _read_pid(_gui_lock_path(root))
    if not pid or not _pid_alive(pid):
        return False
    try:
        # Enumerate top-level windows for that PID and restore/show.
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)  # type: ignore[attr-defined]
        def _enum(hwnd, _lparam):  # noqa: ANN001
            proc_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        if not found:
            return True  # process alive; focus failed but still single-instance
        hwnd = found[0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return True


def _tail_log(path: Path, n: int) -> str:
    if not path.exists():
        return "(no log yet)"
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-n:]) if n > 0 else ""


def _parse_account_state(log_snippet: str) -> dict:
    lines = log_snippet.splitlines()
    equity_match = next((line for line in reversed(lines) if "equity=" in line), "")
    tick_match = next((line for line in reversed(lines) if "tick=" in line and "mode=" in line), "")
    if not tick_match:
        tick_match = next((line for line in reversed(lines) if "tick=" in line), "")
    return {
        "live_text_line": tick_match or equity_match,
        "history_available": bool(lines),
        "ready": "Hermes is awake" in log_snippet or "tick=" in log_snippet,
    }


class HermesGUI(tk.Tk):
    def __init__(self, root: Path, *, auto_start: bool = True):
        super().__init__()
        self.root = root
        self.log_path = root / "data" / "hermes.log"
        self.bot_process: subprocess.Popen | None = None
        self.dash_process: subprocess.Popen | None = None
        self._agent_pid: int | None = None
        self._allow_restart = True
        self.after_id: str | None = None
        self.title("Hermes Trader")
        self.geometry("1100x720")
        self.minsize(900, 560)
        self.configure(padx=12, pady=12)
        self._setup_ui()
        self._schedule_refresh()
        # Bring control room to front.
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        if auto_start:
            self.after(200, lambda: self._launch_all(prompt_stop=False))

    def _mode_label(self) -> str:
        try:
            import yaml

            data = yaml.safe_load((self.root / "config.yaml").read_text(encoding="utf-8")) or {}
            mode = str(data.get("trading_mode", "live")).lower()
        except Exception:
            mode = "live"
        if mode == "live":
            return "Mode: LIVE (Blofin real account)"
        return "Mode: demo ($40 paper)"

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        title = ttk.Label(self, text="Hermes Trader Control Room", font=font.Font(size=18, weight="bold"))
        title.grid(row=0, column=0, sticky="we", pady=(0, 8))

        state_frame = ttk.LabelFrame(self, text="Session")
        state_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        state_frame.columnconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="starting…")
        self.dash_var = tk.StringVar(value=f"Dashboard: {DASHBOARD_URL}")
        self.live_var = tk.StringVar(value="Agent: waiting for first tick…")
        self.mode_var = tk.StringVar(value=self._mode_label())

        rows = [
            ("Status", self.status_var),
            ("Dashboard", self.dash_var),
            ("Agent", self.live_var),
            ("Mode", self.mode_var),
        ]
        for i, (label, var) in enumerate(rows):
            ttk.Label(state_frame, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            ttk.Label(state_frame, textvariable=var).grid(row=i, column=1, sticky="w", padx=8, pady=4)

        btns = ttk.Frame(state_frame)
        btns.grid(row=0, column=2, rowspan=4, padx=12, pady=8, sticky="ns")
        ttk.Button(btns, text="Launch all", command=lambda: self._launch_all(prompt_stop=True)).pack(fill="x", pady=4)
        ttk.Button(btns, text="Open dashboard", command=_open_dashboard_browser).pack(fill="x", pady=4)
        ttk.Button(btns, text="Stop agent", command=self._stop).pack(fill="x", pady=4)

        notebook = ttk.Notebook(self)
        notebook.grid(row=2, column=0, sticky="nsew")
        log_tab = ttk.Frame(notebook)
        notebook.add(log_tab, text="Live bot logs")
        self.log_text = tk.Text(log_tab, wrap="word")
        self.log_text.pack(fill="both", expand=True)

        help_tab = ttk.Frame(notebook)
        notebook.add(help_tab, text="Help")
        help_text = tk.Text(help_tab, wrap="word", height=12)
        help_text.pack(fill="both", expand=True)
        help_text.insert(
            "1.0",
            "Launch all starts:\n"
            f"1) Dashboard at {DASHBOARD_URL} (500ms refresh, live Blofin numbers)\n"
            "2) Detached agent process (python -m hermes_trader) in LIVE mode\n"
            "3) This control room\n\n"
            "Use Stop Hermes desktop shortcut to kill agent + dashboard.\n"
            "Do not use port 8765 — that is LLM KnightTrader.\n",
        )
        help_text.configure(state="disabled")

    def _launch_all(self, *, prompt_stop: bool = True):
        self._allow_restart = True
        self.status_var.set("launching dashboard…")
        self.update_idletasks()
        try:
            self.dash_process = _start_dashboard(self.root)
            if _dashboard_up():
                self.dash_var.set(f"Dashboard: UP  {DASHBOARD_URL}")
                _open_dashboard_browser()
            else:
                self.dash_var.set("Dashboard: FAILED to start on 8766")
                messagebox.showerror("Hermes", "Dashboard failed to start on http://127.0.0.1:8766/")
        except Exception as exc:
            self.dash_var.set(f"Dashboard error: {exc}")
            messagebox.showerror("Hermes", f"Dashboard launch failed: {exc}")

        # Prefer keeping a healthy agent alive — do not kill/relaunch on every open.
        existing = _existing_agent_pid(self.root)
        if existing:
            _write_pid(self.root / PID_FILE, existing)
            self.bot_process = None  # detached; tracked via PID file
            self._agent_pid = existing
            self.status_var.set("running")
            self.live_var.set(f"Agent: already running (PID {existing})")
            self.after(1500, self._poll_bot)
            return

        if self.bot_process and self.bot_process.poll() is None:
            self.status_var.set("running")
            self.live_var.set(f"Agent: already running (PID {self.bot_process.pid})")
            self.after(1500, self._poll_bot)
            return

        self.status_var.set("launching agent…")
        self.update_idletasks()
        try:
            if prompt_stop:
                # Manual "Launch all": only stop if user confirms when something stale exists.
                stale = _find_hermes_agent_pids(self.root)
                if stale:
                    joined = ", ".join(str(p) for p in stale)
                    if not messagebox.askyesno(
                        "Hermes",
                        f"Found leftover agent PID(s) {joined}. Kill and relaunch?",
                    ):
                        self.status_var.set("stopped")
                        return
                    for pid in stale:
                        _terminate_pid(pid)
            self.bot_process = _start_bot(self.root)
            self._agent_pid = self.bot_process.pid
            self.status_var.set("running")
            self.live_var.set(f"Agent: PID {self.bot_process.pid}")
            self.after(1500, self._poll_bot)
        except Exception as exc:
            self.status_var.set("error")
            messagebox.showerror("Hermes", f"Agent launch failed: {exc}")

    def _stop(self):
        self._allow_restart = False
        stopped = False
        if self.bot_process and self.bot_process.poll() is None:
            _terminate_pid(self.bot_process.pid)
            stopped = True
        for pid in _find_hermes_agent_pids(self.root):
            _terminate_pid(pid)
            stopped = True
        stored = _read_pid(self.root / PID_FILE)
        if stored:
            _terminate_pid(stored)
            stopped = True
        _clear_pid(self.root / PID_FILE)
        self.bot_process = None
        self._agent_pid = None
        self.status_var.set("stopped")
        self.live_var.set("Agent: stopped")
        if not stopped:
            messagebox.showinfo("Hermes", "No active Hermes agent process.")

    def _poll_bot(self):
        pid = getattr(self, "_agent_pid", None)
        if self.bot_process is not None:
            if self.bot_process.poll() is not None:
                # Process object exited — check if a replacement PID file is alive.
                pid = _existing_agent_pid(self.root)
                if not pid:
                    self.status_var.set("stopped")
                    self.live_var.set("Agent: stopped — auto-restarting…" if self._allow_restart else "Agent: stopped")
                    _clear_pid(self.root / PID_FILE)
                    if self._allow_restart:
                        self.after(2000, self._auto_restart_agent)
                    return
                self._agent_pid = pid
                self.bot_process = None
            else:
                pid = self.bot_process.pid
                self._agent_pid = pid
        elif pid:
            if not _pid_alive(pid):
                # Maybe PID file was updated.
                pid = _existing_agent_pid(self.root)
                if not pid:
                    self.status_var.set("stopped")
                    self.live_var.set("Agent: stopped — auto-restarting…" if self._allow_restart else "Agent: stopped")
                    _clear_pid(self.root / PID_FILE)
                    if self._allow_restart:
                        self.after(2000, self._auto_restart_agent)
                    return
                self._agent_pid = pid
        else:
            pid = _existing_agent_pid(self.root)
            if not pid:
                self.status_var.set("stopped")
                self.live_var.set("Agent: stopped — auto-restarting…" if self._allow_restart else "Agent: stopped")
                if self._allow_restart:
                    self.after(2000, self._auto_restart_agent)
                return
            self._agent_pid = pid

        _write_pid(self.root / PID_FILE, self._agent_pid)
        self.status_var.set("running")
        self.after(2000, self._poll_bot)

    def _auto_restart_agent(self):
        if not self._allow_restart:
            return
        if _existing_agent_pid(self.root):
            self.after(1500, self._poll_bot)
            return
        try:
            self.bot_process = _start_bot(self.root)
            self._agent_pid = self.bot_process.pid
            self.status_var.set("running")
            self.live_var.set(f"Agent: restarted PID {self._agent_pid}")
            self.after(1500, self._poll_bot)
        except Exception as exc:
            self.status_var.set("error")
            self.live_var.set(f"Agent restart failed: {exc}")
            if self._allow_restart:
                self.after(10000, self._auto_restart_agent)

    def _schedule_refresh(self):
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
        self.after_id = self.after(LOG_REFRESH_MS, self._refresh_safe)

    def _refresh_safe(self):
        try:
            self._refresh()
        except Exception:
            pass
        self.after_id = self.after(STATS_REFRESH_MS, self._refresh_safe)

    def _refresh(self):
        self.mode_var.set(self._mode_label())
        log_snippet = _tail_log(self.log_path, LOG_TAIL_LINES)
        account = _parse_account_state(log_snippet)
        if account.get("live_text_line"):
            self.live_var.set(f"Agent: {account['live_text_line']}")
        if self.log_text.winfo_exists():
            self.log_text.delete("1.0", "end")
            self.log_text.insert("1.0", log_snippet)
            self.log_text.see("end")
        if _dashboard_up():
            self.dash_var.set(f"Dashboard: UP  {DASHBOARD_URL}")
        else:
            self.dash_var.set(f"Dashboard: down  {DASHBOARD_URL}")

    def _on_close(self):
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
        # Closing the control room does NOT kill the agent/dashboard —
        # use Stop Hermes for that. Matches "launcher window" UX.
        self.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes Trader launcher")
    parser.add_argument("--working-dir", default=".", help="Hermes project root")
    parser.add_argument("--no-auto-start", action="store_true", help="open UI without launching")
    args = parser.parse_args(argv)
    working = _find_project_root(Path(args.working_dir).resolve())
    os.chdir(working)

    if not _claim_gui_singleton(working):
        _focus_existing_gui(working)
        # Still ensure dashboard/agent are up without stacking GUIs.
        if not args.no_auto_start:
            try:
                if not _dashboard_up():
                    _start_dashboard(working)
                if not _existing_agent_pid(working):
                    _start_bot(working)
                if _dashboard_up():
                    _open_dashboard_browser()
            except Exception:
                pass
        return 0

    app = HermesGUI(working, auto_start=not args.no_auto_start)
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
    try:
        lock = _gui_lock_path(working)
        if _read_pid(lock) == os.getpid():
            _clear_pid(lock)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
