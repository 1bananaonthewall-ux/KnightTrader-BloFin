"""Hermes Trader dashboard — live Blofin account (demo/paper supported).

Poll target: 500ms via GET /api/overview.
Port: 8766 (not shared with LLM KnightTrader on 8765).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Hermes Trader Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = BASE_DIR / "data" / "demo_journal.sqlite"
LIVE_DB = BASE_DIR / "data" / "journal.sqlite"
PAPER_STATE = BASE_DIR / "data" / "paper_state.json"
LIVE_STATE = BASE_DIR / "data" / "live_state.json"
DEFAULT_LOG = BASE_DIR / "data" / "hermes.log"
PID_FILE = BASE_DIR / ".hermes.pid"
CONFIG_YAML = BASE_DIR / "config.yaml"
LOG_TAIL_LINES = 400
templates = Jinja2Templates(directory=str(BASE_DIR / "apps" / "dashboard" / "templates"))

# Live mark cache for 500ms UI MTM (refreshed ~every 1.5s, not every poll).
_MARK_CACHE: dict[str, float] = {}
_MARK_CACHE_TS = 0.0
_MARK_CACHE_TTL = 1.5


def _refresh_mark_cache(needed: list[str] | None = None) -> dict[str, float]:
    """Pull Blofin SWAP last prices (cached) so equity slides every poll."""
    global _MARK_CACHE, _MARK_CACHE_TS
    now = time.time()
    need = {str(x) for x in (needed or []) if x}
    stale = (now - _MARK_CACHE_TS) >= _MARK_CACHE_TTL
    missing = bool(need) and any(i not in _MARK_CACHE for i in need)
    if not stale and not missing and _MARK_CACHE:
        return _MARK_CACHE
    try:
        # Prefer project client (curl_cffi chrome impersonation for Blofin WAF).
        sys.path.insert(0, str(BASE_DIR))
        from hermes_trader.blofin_client import BlofinClient  # noqa: WPS433

        client = BlofinClient(api_key="", api_secret="", passphrase="")
        book = client.get_tickers_batch(None) or {}
        fresh: dict[str, float] = {}
        for iid, row in book.items():
            try:
                last = float((row or {}).get("last") or (row or {}).get("lastPr") or 0)
            except Exception:
                last = 0.0
            if last > 0:
                fresh[str(iid)] = last
        if fresh:
            _MARK_CACHE = fresh
            _MARK_CACHE_TS = now
    except Exception:
        # Keep last good cache on transient failures.
        pass
    return _MARK_CACHE


def _paper_with_live_mtm(paper: dict[str, Any]) -> dict[str, Any]:
    """Recompute unrealized/equity from cached marks for smooth 500ms slides."""
    if not paper:
        return paper
    positions = list(paper.get("positions") or [])
    if not positions:
        return paper
    marks = _refresh_mark_cache([p.get("instId") for p in positions if isinstance(p, dict)])
    if not marks:
        return paper
    cash = float(paper.get("available") or paper.get("cash") or 0.0)
    margin_used = 0.0
    unrealized = 0.0
    out_pos: list[dict[str, Any]] = []
    for p in positions:
        if not isinstance(p, dict):
            continue
        iid = str(p.get("instId") or "")
        entry = float(p.get("entry_px") or 0)
        sz = float(p.get("sz") or 0)
        side = str(p.get("side") or "long").lower()
        margin = float(p.get("margin") or 0)
        mark = float(marks.get(iid) or p.get("mark_px") or entry or 0)
        if side in {"long", "net"}:
            upnl = (mark - entry) * sz
        else:
            upnl = (entry - mark) * sz
        margin_used += margin
        unrealized += upnl
        q = dict(p)
        q["mark_px"] = mark
        q["unrealized_pnl"] = upnl
        out_pos.append(q)
    equity = cash + margin_used + unrealized
    updated = dict(paper)
    updated["positions"] = out_pos
    updated["available"] = cash
    updated["margin_used"] = margin_used
    updated["unrealized_pnl"] = unrealized
    updated["equity"] = equity
    updated["updated_at"] = time.time()
    updated["open_positions"] = len(out_pos)
    return updated


_LIVE_CACHE: dict[str, Any] = {}
_LIVE_CACHE_TS = 0.0
_LIVE_CACHE_TTL = 2.0


def _load_live_state() -> dict[str, Any]:
    if not LIVE_STATE.is_file():
        return {}
    try:
        data = json.loads(LIVE_STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _live_account_overlay() -> dict[str, Any]:
    """Pull live Blofin equity/positions for dashboard (cached ~2s)."""
    global _LIVE_CACHE, _LIVE_CACHE_TS
    now = time.time()
    if _LIVE_CACHE and (now - _LIVE_CACHE_TS) < _LIVE_CACHE_TTL:
        return _LIVE_CACHE
    live_meta = _load_live_state()
    try:
        sys.path.insert(0, str(BASE_DIR))
        from hermes_trader.blofin_client import BlofinClient
        from hermes_trader.config import load_all
        from hermes_trader.market_data import fetch_account, fetch_positions

        secrets, _cfg = load_all(str(CONFIG_YAML))
        client = BlofinClient(
            secrets.blofin_api_key,
            secrets.blofin_api_secret,
            secrets.blofin_passphrase,
        )
        acct = fetch_account(client)
        positions = fetch_positions(client)
        pos_rows = [
            {
                "instId": p.instId,
                "side": p.side,
                "sz": p.sz,
                "entry_px": p.entry_px,
                "mark_px": p.mark_px,
                "leverage": p.leverage,
                "margin": p.margin,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions
        ]
        _LIVE_CACHE = {
            "mode": "live",
            "starting_equity": None,
            "equity": acct.equity,
            "available": acct.available,
            "margin_used": acct.margin_used,
            "unrealized_pnl": acct.unrealized_pnl,
            "realized_pnl": live_meta.get("realized_pnl"),
            "universe_count": int(live_meta.get("universe_count") or 0),
            "last_tick": int(live_meta.get("last_tick") or 0),
            "updated_at": now,
            "positions": pos_rows,
            "open_positions": len(pos_rows),
        }
        _LIVE_CACHE_TS = now
    except Exception as exc:
        # Fall back to last agent-written live_state so UI still shows numbers offline.
        fallback = {
            "mode": "live",
            "starting_equity": None,
            "equity": live_meta.get("equity"),
            "available": live_meta.get("available"),
            "margin_used": live_meta.get("margin_used"),
            "unrealized_pnl": live_meta.get("unrealized_pnl"),
            "realized_pnl": live_meta.get("realized_pnl"),
            "universe_count": int(live_meta.get("universe_count") or 0),
            "last_tick": int(live_meta.get("last_tick") or 0),
            "updated_at": live_meta.get("updated_at") or now,
            "positions": (_LIVE_CACHE or {}).get("positions") or [],
            "open_positions": int(live_meta.get("open_positions") or 0),
            "error": str(exc),
        }
        _LIVE_CACHE = fallback
        _LIVE_CACHE_TS = now
    return _LIVE_CACHE


def _trading_mode() -> str:
    try:
        import yaml

        data = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8")) or {}
        return str(data.get("trading_mode", "live")).lower()
    except Exception:
        return "live"


def _db_path() -> Path:
    mode = _trading_mode()
    if mode == "demo":
        return DEFAULT_DB if DEFAULT_DB.exists() else LIVE_DB
    return LIVE_DB


def _paper_path() -> Path:
    try:
        import yaml

        data = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8")) or {}
        rel = ((data.get("paper") or {}).get("state_path")) or "./data/paper_state.json"
        p = Path(rel)
        return p if p.is_absolute() else (BASE_DIR / p)
    except Exception:
        return PAPER_STATE


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        # Empty schema so dashboard never 500s before first trade.
        conn = sqlite3.connect(db_path, isolation_level=None)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                tick INTEGER NOT NULL,
                instId TEXT NOT NULL,
                side TEXT NOT NULL,
                action TEXT NOT NULL,
                sz TEXT NOT NULL,
                px TEXT,
                leverage INTEGER,
                rationale TEXT,
                pnl_usdt REAL,
                decision_raw TEXT
            );
            CREATE TABLE IF NOT EXISTS open_lots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instId TEXT NOT NULL,
                side TEXT NOT NULL,
                sz REAL NOT NULL,
                entry_px REAL NOT NULL,
                ts INTEGER NOT NULL,
                trade_id INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS summary_cache (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                generated_at INTEGER NOT NULL,
                summary TEXT NOT NULL
            );
            """
        )
        conn.close()
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _read_pid(pid_path: Path) -> int | None:
    if not pid_path.exists():
        return None
    try:
        text = pid_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[0]
        return int(text)
    except Exception:
        return None


def _is_process_alive(pid: int) -> bool:
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


def _load_paper() -> dict[str, Any] | None:
    path = _paper_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _log_tail(log_path: Path) -> str:
    if not log_path.exists():
        return ""
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-LOG_TAIL_LINES:])


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/status")
async def api_status():
    pid = _read_pid(PID_FILE)
    alive = pid is not None and _is_process_alive(pid)
    return {
        "running": alive,
        "pid": pid,
        "mode": _trading_mode(),
        "db": str(_db_path()),
        "log": str(DEFAULT_LOG),
        "log_tail": _log_tail(DEFAULT_LOG),
    }


@app.get("/api/account")
async def api_account():
    mode = _trading_mode()
    if mode == "live":
        return JSONResponse(_live_account_overlay())
    paper = _paper_with_live_mtm(_load_paper() or {})
    if paper:
        return JSONResponse(paper)
    return JSONResponse(
        {
            "mode": mode,
            "equity": None,
            "available": None,
            "margin_used": None,
            "unrealized_pnl": None,
            "realized_pnl": None,
            "starting_equity": 40.0,
            "positions": [],
            "universe_count": 0,
        }
    )


@app.get("/api/journal")
async def api_journal(limit: int = 100):
    conn = _connect(_db_path())
    rows = conn.execute(
        "SELECT id, ts, tick, instId, side, action, sz, px, leverage, pnl_usdt, rationale FROM trades ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    items = [dict(row) for row in rows]
    conn.close()
    return JSONResponse(items)


@app.get("/api/positions")
async def api_positions():
    mode = _trading_mode()
    if mode == "live":
        live = _live_account_overlay()
        return JSONResponse(live.get("positions") or [])
    paper = _load_paper()
    if paper and paper.get("positions") is not None:
        return JSONResponse(paper.get("positions") or [])
    conn = _connect(_db_path())
    rows = conn.execute(
        "SELECT instId, side, sz, entry_px, ts FROM open_lots ORDER BY ts ASC"
    ).fetchall()
    items = [dict(row) for row in rows]
    conn.close()
    return JSONResponse(items)


@app.get("/api/stats")
async def api_stats():
    mode = _trading_mode()
    conn = _connect(_db_path())
    today_ms = int((time.time() - (time.time() % 86400)) * 1000)
    total_trades = conn.execute(
        "SELECT COUNT(*) AS c FROM trades WHERE instId != '(no_trade)'"
    ).fetchone()["c"]
    today_pnl = conn.execute(
        "SELECT COALESCE(SUM(pnl_usdt), 0) AS total FROM trades WHERE ts >= ? AND pnl_usdt IS NOT NULL",
        (today_ms,),
    ).fetchone()["total"]
    open_lots = conn.execute("SELECT COUNT(*) AS c FROM open_lots").fetchone()["c"]
    conn.close()
    acct = _live_account_overlay() if mode == "live" else (_load_paper() or {})
    return JSONResponse({
        "total_trades": total_trades,
        "today_pnl": today_pnl,
        "open_lots": acct.get("open_positions", open_lots),
        "equity": acct.get("equity"),
        "unrealized_pnl": acct.get("unrealized_pnl"),
        "realized_pnl": acct.get("realized_pnl"),
        "universe_count": acct.get("universe_count"),
        "mode": mode,
    })


@app.get("/api/overview")
async def api_overview():
    """Single payload for 500ms UI refresh."""
    pid = _read_pid(PID_FILE)
    alive = pid is not None and _is_process_alive(pid)
    mode = _trading_mode()
    if mode == "live":
        paper = _live_account_overlay()
    else:
        paper = _paper_with_live_mtm(_load_paper() or {})
    conn = _connect(_db_path())
    today_ms = int((time.time() - (time.time() % 86400)) * 1000)
    total_trades = conn.execute(
        "SELECT COUNT(*) AS c FROM trades WHERE instId != '(no_trade)'"
    ).fetchone()["c"]
    today_pnl = float(
        conn.execute(
            "SELECT COALESCE(SUM(pnl_usdt), 0) AS total FROM trades WHERE ts >= ? AND pnl_usdt IS NOT NULL",
            (today_ms,),
        ).fetchone()["total"]
        or 0
    )
    trades = [
        dict(r)
        for r in conn.execute(
            "SELECT id, ts, tick, instId, side, action, sz, px, leverage, pnl_usdt, rationale "
            "FROM trades ORDER BY id DESC LIMIT 30"
        ).fetchall()
    ]
    conn.close()
    positions = paper.get("positions") or []
    starting = float(paper.get("starting_equity") or (paper.get("equity") if mode == "live" else 40.0) or 40.0)
    equity = paper.get("equity")
    session_pnl = (float(equity) - starting) if equity is not None and mode != "live" else (
        float(paper.get("unrealized_pnl") or 0) if mode == "live" else None
    )
    return JSONResponse(
        {
            "ts": time.time(),
            "running": alive,
            "pid": pid,
            "mode": mode,
            "account": {
                "starting_equity": starting if mode != "live" else equity,
                "equity": equity,
                "available": paper.get("available"),
                "margin_used": paper.get("margin_used"),
                "unrealized_pnl": paper.get("unrealized_pnl"),
                "realized_pnl": paper.get("realized_pnl"),
                "session_pnl": session_pnl,
                "universe_count": paper.get("universe_count") or 0,
                "last_tick": paper.get("last_tick") or 0,
                "updated_at": paper.get("updated_at"),
            },
            "stats": {
                "total_trades": total_trades,
                "today_pnl": today_pnl,
                "open_lots": len(positions) if positions else int(paper.get("open_positions") or 0),
            },
            "positions": positions,
            "trades": trades,
            "log_tail": _log_tail(DEFAULT_LOG),
        }
    )


@app.post("/api/start_trading")
async def api_start_trading():
    try:
        pid = _read_pid(PID_FILE)
        if pid is not None and _is_process_alive(pid):
            return JSONResponse({"status": "already_running", "pid": pid})
        py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path(sys.executable)
        creation = 0
        if sys.platform == "win32":
            creation = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        data = BASE_DIR / "data"
        data.mkdir(parents=True, exist_ok=True)
        stdout_path = data / "agent_stdout.log"
        stderr_path = data / "agent_stderr.log"
        stdout_f = open(stdout_path, "a", encoding="utf-8")  # noqa: SIM115
        stderr_f = open(stderr_path, "a", encoding="utf-8")  # noqa: SIM115
        cmd = [
            str(py),
            "-u",
            "-m",
            "hermes_trader",
        ]
        env = {
            **os.environ,
            "HERMES_HOME": str(BASE_DIR),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        popen_kwargs: dict[str, object] = {
            "cwd": str(BASE_DIR),
            "env": env,
            "stdout": stdout_f,
            "stderr": stderr_f,
        }
        if sys.platform == "win32":
            popen_kwargs["close_fds"] = True  # type: ignore[arg-type]
            popen_kwargs["creationflags"] = creation  # type: ignore[arg-type]
        proc = subprocess.Popen(cmd, **popen_kwargs)  # type: ignore[arg-type]
        with open(BASE_DIR / PID_FILE, "w", encoding="utf-8") as fh:
            fh.write(f"{proc.pid}\n")
        return JSONResponse({"status": "started", "mode": _trading_mode(), "pid": proc.pid})
    except Exception as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


@app.post("/api/launch")
async def api_launch():
    try:
        pid = _read_pid(PID_FILE)
        if pid is not None and _is_process_alive(pid):
            return JSONResponse({"status": "already_running", "pid": pid})
        py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path(sys.executable)
        creation = 0
        if sys.platform == "win32":
            creation = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
        subprocess.Popen(
            [
                str(py),
                str(BASE_DIR / "scripts" / "launch_hermes_gui.py"),
                "--no-auto-start",
                "--working-dir",
                str(BASE_DIR),
            ],
            cwd=str(BASE_DIR),
            env={**os.environ, "HERMES_HOME": str(BASE_DIR)},
            creationflags=creation,
        )
        return JSONResponse({"status": "launched", "mode": _trading_mode()})
    except Exception as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


@app.post("/api/stop")
async def api_stop():
    try:
        py = BASE_DIR / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = Path(sys.executable)
        subprocess.run(
            [str(py), str(BASE_DIR / "scripts" / "stop_hermes.py"), str(BASE_DIR), "--quiet"],
            check=False,
            capture_output=True,
        )
        lock = BASE_DIR / ".hermes_dashboard.lock"
        if lock.exists():
            try:
                lock.unlink()
            except Exception:
                pass
        return JSONResponse({"status": "stopped"})
    except Exception as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.dashboard.main:app", host="127.0.0.1", port=8766, reload=False)
