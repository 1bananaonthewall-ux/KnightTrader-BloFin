"""Load the offline backtest winner into Hermes's live prompt / journal memory.

Hermes is still an LLM agent — this does not force signal execution. It makes
the optimized playbook visible every tick and seeds the journal summary so
persistent learning starts from that prior rather than a blank slate.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BEST_PATH = Path("data/backtest_best.json")
PLAYBOOK_MARKER = "### OPTIMIZED PLAYBOOK (offline backtest)"


def load_backtest_best(path: str | Path | None = None) -> dict[str, Any] | None:
    p = Path(path) if path else DEFAULT_BEST_PATH
    if not p.is_file():
        logger.warning("backtest best not found at %s", p)
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to load backtest best %s: %s", p, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def format_playbook(best: dict[str, Any] | None) -> str:
    if not best:
        return ""
    params = best.get("params") or {}
    mix = best.get("mix") or "(single)"
    strategy = best.get("strategy") or "?"
    ret = best.get("total_return_pct")
    dd = best.get("max_drawdown_pct")
    trades = best.get("trades")
    lines = [
        PLAYBOOK_MARKER,
        f"Strategy: {strategy}",
        f"Mix: {mix}",
        f"Backtest result: return={ret}% maxDD={dd}% trades={trades} (portfolio $40 start, ~1 month 1H bars, full Blofin USDT universe).",
        "Trade this concentrated style unless your live journal clearly shows it failing:",
        "- Prefer breakout confirmed by ROC momentum (AND): only enter when BOTH agree.",
        f"- Breakout window={params.get('window', 20)}; ROC period={params.get('period__roc_momentum', 5)}, "
        f"threshold={params.get('threshold__roc_momentum', 0.3)}%.",
        f"- Risk: stop_loss~{float(params.get('stop_loss_pct', 0.03)) * 100:.0f}% / "
        f"take_profit~{float(params.get('take_profit_pct', 0.25)) * 100:.0f}% from entry.",
        f"- Leverage~{int(float(params.get('leverage', 10)))}x; keep at most "
        f"{int(float(params.get('max_positions', 3)))} open positions (high conviction, not spray).",
        "- POSITION SIZING (mandatory, stop-based — NOT all-in cash):",
        "  risk_usd = equity * 1%   (per open; max ~3% heat across 3 slots)",
        "  margin   = risk_usd / (leverage * stop_loss_pct)",
        "  notional = margin * leverage;  sz = notional / price (lot-snapped)",
        "  Example $40 / 10x / 3% SL -> ~$1.33 margin (~$13 notional) per open, ~$36 cash free.",
        "- Cap total margin under ~35% of equity. Never dump the whole book into 3 lots.",
        "- Still obey hard JSON schema / lot sizes. Do nothing when signals conflict or edge is unclear.",
    ]
    return "\n".join(lines)


def merge_summary_with_playbook(existing: str, playbook: str) -> str:
    """Keep the playbook block at the top of the journal summary cache."""
    playbook = (playbook or "").strip()
    existing = (existing or "").strip()
    if not playbook:
        return existing
    if PLAYBOOK_MARKER in existing:
        # Replace old playbook block, keep the rest of the learned summary.
        parts = existing.split(PLAYBOOK_MARKER, 1)
        rest = parts[1]
        # Drop through end of previous playbook (until blank line + non-playbook content).
        rest_lines = rest.splitlines()
        kept: list[str] = []
        skipping = True
        for line in rest_lines:
            if skipping:
                if line.strip() == "":
                    skipping = False
                continue
            kept.append(line)
        rest_body = "\n".join(kept).strip()
        return playbook if not rest_body else f"{playbook}\n\n{rest_body}"
    if not existing:
        return playbook
    return f"{playbook}\n\n{existing}"


def seed_journal_playbook(journal, best_path: str | Path | None = None) -> bool:
    """Write/refresh playbook into journal summary so persistent memory includes it."""
    best = load_backtest_best(best_path)
    playbook = format_playbook(best)
    if not playbook:
        return False
    merged = merge_summary_with_playbook(journal.get_summary(), playbook)
    journal.set_summary(merged)
    logger.info("seeded journal summary with optimized playbook from %s", best_path or DEFAULT_BEST_PATH)
    return True
