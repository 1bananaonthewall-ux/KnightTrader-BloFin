SYSTEM_PROMPT = """You are Emirald, a self-learning crypto perpetual futures trader.

GOAL
- Preserve and grow account equity over many ticks.
- Avoid unnecessary drawdowns and overtrading.
- Learn from past trades in the journal memory block.

RULES
- Output only one JSON object. No extra prose.
- Use the schema: {"decisions":[{"action":"open"|"close"|"hold","instId":"BTC-USDT","side":"buy"|"sell","sz":"0.001","orderType":"market","leverage":10,"stopLoss":"67000","takeProfit":"75000","rationale":"..."}]}
- If no good edge, return {"decisions":[{"action":"hold","instId":"BTC-USDT","side":"buy","sz":"0","orderType":"market","leverage":1,"rationale":"No high-confidence setup."}]}
- sz is contract size as a string. round to lotSz.
- leverage must be an integer.
- Do not exceed max open positions from context.
- Do not reuse stale rationale text; write a fresh 1-line reason.

CONTEXT BLOCKS
- ACCOUNT: equity, available, margin_used, unrealized, positions
- MARKET: top tickers + 1m candles
- JOURNAL: recent trades and summary memory
"""

SYSTEM = SYSTEM_PROMPT


def build_user_prompt(snapshot, journal, *, verbatim_n: int = 20, tick_num: int | None = None) -> str:
    account = getattr(snapshot, "account", None)
    positions = getattr(snapshot, "positions", None) or []
    tickers = list(getattr(snapshot, "tickers", {}).values())
    candles = list(getattr(snapshot, "candles", {}).values())

    lines = [
        "ACCOUNT",
        f"equity={getattr(account, 'equity', None)} available={getattr(account, 'available', None)} margin_used={getattr(account, 'margin_used', None)} unrealized={getattr(account, 'unrealized_pnl', None)}",
        "POSITIONS",
    ]
    if positions:
        for p in positions[:20]:
            lines.append(
                f"- {getattr(p, 'instId', '?')} {getattr(p, 'side', '?')} sz={getattr(p, 'sz', '?')} entry={getattr(p, 'entry_px', '?')} mark={getattr(p, 'mark_px', '?')} lev={getattr(p, 'leverage', '?')} margin={getattr(p, 'margin', '?')} upnl={getattr(p, 'unrealized_pnl', '?')}"
            )
    else:
        lines.append("- none")

    lines.append("UNIVERSE")
    shown = 0
    for item in tickers:
        lines.append(f"- {getattr(item, 'instId', '?')}")
        shown += 1
    lines.append(f"- ... {max(0, len(tickers) - shown)} more")

    lines.append("CANDLES")
    for c in candles[: verbatim_n * 3]:
        lines.append(
            f"- {c.get('instId')} ts={c.get('ts')} o={c.get('open')} h={c.get('high')} l={c.get('low')} c={c.get('close')} vol={c.get('volume')}"
            if isinstance(c, dict) else f"- {c}"
        )

    trades = []
    try:
        trades = journal.get_verbatim(verbatim_n)
    except Exception:
        trades = []

    lines.append("RECENT_TRADES")
    if trades:
        for t in trades[: verbatim_n]:
            lines.append(
                f"#{getattr(t, 'id', '?')} t={getattr(t, 'tick', '?')} {getattr(t, 'instId', '?')} {getattr(t, 'side', '?')} {getattr(t, 'action', '?')} sz={getattr(t, 'sz', '?')} px={getattr(t, 'px', '?')} pnl={getattr(t, 'pnl_usdt', '?')} rationale={getattr(t, 'rationale', '')}"
            )
    else:
        lines.append("- none")

    summary = ""
    try:
        summary = journal.get_summary() or ""
    except Exception:
        summary = ""
    lines.append("JOURNAL_MEMORY")
    lines.append(summary or "(none)")

    lines.append("DECISION_FORMAT")
    lines.append('{"decisions":[{"action":"open"|"close"|"hold","instId":"BTC-USDT","side":"buy"|"sell","sz":"0.001","orderType":"market","leverage":10,"stopLoss":"67000","takeProfit":"75000","rationale":"..."}]}')
    return "\n".join(lines)
