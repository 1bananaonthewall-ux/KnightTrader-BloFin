from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .blofin_client import BlofinClient
from .config import settings
from .journal import AxiomJournal, Trade
from .loop import AxiomLoop
from .market_data import AxiomMarketData

app = FastAPI(title="Axiom Logic")
templates = Jinja2Templates(directory=str(settings.__file__).replace("config.py", "templates"))

loop = AxiomLoop(mode=settings.mode)
journal = AxiomJournal()
ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "data" / "axiom.pid"
LOG_FILE = ROOT / "data" / "axiom.log"


def _python_exe() -> str:
    return sys.executable or "python"


def _launch_background(action: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [_python_exe(), "-m", "axiom_logic.scripts.control", action]
    kwargs: dict[str, Any] = {"cwd": str(ROOT), "env": env, "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        return {"status": "queued", "action": action}
    except Exception as exc:
        return {"status": "error", "action": action, "detail": str(exc)}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> Any:
    snap = loop.current_snapshot
    snapshot = {
        "equity": 0.0,
        "available_balance": 0.0,
        "margin_used": 0.0,
        "unrealized_pnl": 0.0,
        "positions": [],
        "orders": [],
    }
    if snap:
        snapshot["equity"] = float(snap.balances[0].eq) if snap.balances else 0.0
        snapshot["available_balance"] = float(snap.balances[0].avail_eq) if snap.balances else 0.0
        snapshot["margin_used"] = 0.0
        snapshot["unrealized_pnl"] = 0.0
        snapshot["positions"] = [
            {
                "instId": getattr(p, "instId", ""),
                "side": getattr(p, "side", ""),
                "sz": getattr(p, "sz", ""),
                "entry_px": getattr(p, "entry_px", ""),
                "mark_px": getattr(p, "mark_px", ""),
                "leverage": getattr(p, "leverage", ""),
                "liq_px": getattr(p, "liq_px", ""),
                "unrealized_pnl": getattr(p, "unrealized_pnl", ""),
            }
            for p in snap.positions
        ]
        snapshot["orders"] = []
    else:
        snapshot = loop.broker.snapshot()
    trades = journal.recent_trades(50)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "snapshot": snapshot,
            "trades": trades,
            "thesis": loop.last_decision_raw or "",
            "mode": settings.mode,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "mode": settings.mode, "tick": loop.tick_num}


@app.get("/api/snapshot")
async def snapshot() -> dict[str, Any]:
    if loop.current_snapshot:
        snap = loop.current_snapshot
        equity = float(snap.balances[0].eq) if snap.balances else loop.broker.equity
        return {
            "equity": equity,
            "available_balance": float(snap.balances[0].avail_eq) if snap.balances else loop.broker.available_balance,
            "margin_used": 0.0,
            "unrealized_pnl": 0.0,
            "refreshed_at": snap.refreshed_at.isoformat(),
            "positions": [
                {
                    "instId": getattr(p, "instId", ""),
                    "side": getattr(p, "side", ""),
                    "sz": getattr(p, "sz", ""),
                    "entry_px": getattr(p, "entry_px", ""),
                    "mark_px": getattr(p, "mark_px", ""),
                    "leverage": getattr(p, "leverage", ""),
                    "liq_px": getattr(p, "liq_px", ""),
                    "unrealized_pnl": getattr(p, "unrealized_pnl", ""),
                }
                for p in snap.positions
            ],
        }
    return loop.broker.snapshot()


@app.get("/api/trades")
async def trades(limit: int = 50) -> dict[str, Any]:
    rows = journal.recent_trades(limit)
    return {"trades": [r.model_dump(mode="json") if hasattr(r, "model_dump") else r.__dict__ for r in rows]}


@app.get("/api/decision")
async def decision() -> dict[str, Any]:
    return {"raw": loop.last_decision_raw or "", "tick": loop.tick_num}


@app.get("/api/control/{action}")
async def control(action: str) -> JSONResponse:
    if action not in {"start", "stop"}:
        return JSONResponse({"status": "error", "detail": "invalid action"}, status_code=400)
    result = _launch_background(action)
    return JSONResponse(result)
