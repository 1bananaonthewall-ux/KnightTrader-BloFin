"""Build the system + user prompts that get sent to the LLM each tick.

Design constraints:
- Total prompt must stay under ~60K tokens. The free Portal tier has
  variable latency, and a 200K-token prompt is a foot-gun: 8+ second
  LLM calls, frequent timeouts, dropped ticks. If we're approaching the
  cap, we drop oldest candle bars first (candles are the bulkiest item).
- The system prompt is stable across ticks (no state, no timestamps) so
  it can be cached by the provider if it supports it.
- The user prompt carries the live state: account, positions, top-N
  market snapshot, verbatim journal, summary cache.
"""
from __future__ import annotations

from .journal import Journal, serialize_trades_for_prompt
from .market_data import MarketSnapshot
from .playbook import format_playbook, load_backtest_best


SYSTEM_PROMPT = """You are Hermes, a self-learning crypto perpetual futures trader
running on the user's Blofin account via the Nous Portal LLM endpoint. Every
minute you wake up, receive fresh market and account state, look at your own
recent trade history, and decide what to do next.

Universe: every USDT-margined perpetual on Blofin (you will see the full list
and the top 20 by volume in detail in the user prompt).
Mode: isolated margin per position. You may set leverage freely per order,
between 1 and 100. No position-size, no daily-loss, no drawdown guardrails
are wired in. The user has explicitly accepted full responsibility for all
outcomes and asked you to trade without external risk constraints.

Your job is to read your own journal, weigh it against current market state,
and produce a small set of high-conviction actions. Quality over quantity.
If you have no edge, do nothing.

An offline portfolio backtest across the full Blofin USDT universe produced an
optimized playbook that grew ~$40 -> ~$120+ in ~1 month of 1H bars
(breakout AND ROC momentum, max 3 positions, 10x, SL~3% / TP~25%).
Prefer that playbook when the live tape supports it. Your journal can
override signal choice if live results clearly disagree - but POSITION
SIZING is enforced by the bot to match the backtest:

  risk_usd = equity * 0.01
  margin   = risk_usd / (leverage * stop_loss_pct)   # e.g. 0.40/(10*0.03) ~= $1.33
  notional = margin * leverage
  sz       = notional / price   (lot-snapped)

Never dump all cash across 3 slots. Do not invent oversized sz.

Respond with EXACTLY one JSON object. No prose before or after, no markdown
fences. The JSON must match this schema:

{
  "thesis":          "1-3 sentences on what you believe right now",
  "decisions": [
    {
      "instId":    "BTC-USDT",
      "action":    "open" | "add" | "reduce" | "close" | "cancel_and_replace",
      "side":      "buy" | "sell",
      "orderType": "market" | "limit",
      "sz":        "0.010",          // base coin amount, as a string
      "px":        "60000",          // required for limit, omit for market
      "leverage":  5,                // integer 1-100
      "stopLoss":  "59000",          // optional trigger price
      "takeProfit":"65000",          // optional trigger price
      "rationale": "one short sentence referencing your journal"
    }
  ],
  "no_trade_reason": "why you're doing nothing, if decisions is empty"
}

Hard rules:
- Never invent instIds; only use those in the provided ticker list.
- sz must be a string representation of a positive number. On BloFin this is
  CONTRACT size (not coins). Snap to the instrument's lotSize — values will
  be rounded down to the nearest lot increment before being placed.
- Leverage must be an integer between 1 and 100.
- Limit orders MUST include px. Market orders MUST NOT include px.
- stopLoss / takeProfit are optional trigger prices (plain numbers as strings).
- If you do nothing this tick, return decisions:[] and explain in no_trade_reason.
- Never return more than 5 decisions per tick.
- The decision raw output is recorded verbatim in your journal. Your future
  self will read it. Write rationales that future-you will respect.

The journal you see is your only memory between ticks. Use it. Be honest
about what worked and what didn't. The bot has no other state.
"""


def _format_account(snap: MarketSnapshot) -> str:
    a = snap.account
    return (
        f"Equity: {a.equity:.2f} USDT\n"
        f"Available: {a.available:.2f} USDT\n"
        f"Margin in use: {a.margin_used:.2f} USDT\n"
        f"Unrealized PnL: {a.unrealized_pnl:+.2f} USDT"
    )


def _format_positions(snap: MarketSnapshot) -> str:
    if not snap.positions:
        return "No open positions."
    lines = []
    for p in snap.positions:
        liq = f"{p.liq_px:.4f}" if p.liq_px is not None else "n/a"
        lines.append(
            f"- {p.instId} {p.side.upper()} sz={p.sz} entry={p.entry_px:.4f} "
            f"mark={p.mark_px:.4f} lev={p.leverage or '?'}x "
            f"liq={liq} upnl={p.unrealized_pnl:+.2f}"
        )
    return "\n".join(lines)


def _format_open_orders(snap: MarketSnapshot) -> str:
    if not snap.open_orders:
        return "No open orders."
    lines = []
    for o in snap.open_orders[:20]:
        lines.append(
            f"- {o.get('instId','')} {o.get('side','')} {o.get('ordType','')} "
            f"sz={o.get('sz','')} px={o.get('px','?')}"
        )
    return "\n".join(lines)


def _format_top_market(snap: MarketSnapshot) -> str:
    """Top N by 24h volume: last, change%, funding, OI change%."""
    if not snap.tickers:
        return "(no tickers)"
    # Sort by 24h vol, take top N.
    sorted_t = sorted(
        snap.tickers.values(), key=lambda t: t.vol_24h_quote, reverse=True
    )[: snap.top_n]
    lines = ["instId            last        24h%      1h%      funding      vol24h(quote)   oi_chg24h%"]
    for t in sorted_t:
        fund = f"{t.funding_rate:+.5f}" if t.funding_rate is not None else "n/a"
        oi = f"{t.oi_change_24h_pct:+.2f}%" if t.oi_change_24h_pct is not None else "n/a"
        lines.append(
            f"{t.instId:<18}{t.last:>12.4f}{t.change_24h_pct:>+9.2f}"
            f"{t.change_1h_pct:>+9.2f}{fund:>13}{t.vol_24h_quote:>16.0f}{oi:>13}"
        )
    return "\n".join(lines)


def _format_candles(snap: MarketSnapshot) -> str:
    """Most recent 1m candles for the top N. Compressed as ts,open,high,low,close,vol.
    We render them OLDEST first so the LLM reads left-to-right like a chart.
    """
    if not snap.candles:
        return "(no candles)"

    def _bar_fields(b) -> tuple[str, str, str, str, str, str]:
        if isinstance(b, dict):
            ts = b.get("ts", "")
            o = b.get("o", b.get("open", ""))
            h = b.get("h", b.get("high", ""))
            l = b.get("l", b.get("low", ""))
            c = b.get("c", b.get("close", ""))
            v = b.get("vol", b.get("volume", ""))
        else:
            # Blofin raw row: [ts, o, h, l, c, vol, ...]
            seq = list(b) if b is not None else []
            ts = seq[0] if len(seq) > 0 else ""
            o = seq[1] if len(seq) > 1 else ""
            h = seq[2] if len(seq) > 2 else ""
            l = seq[3] if len(seq) > 3 else ""
            c = seq[4] if len(seq) > 4 else ""
            v = seq[5] if len(seq) > 5 else ""
        ts_s = str(ts)
        if isinstance(ts, str) and len(ts_s) > 3:
            ts_s = ts_s[:-3]
        return ts_s, str(o), str(h), str(l), str(c), str(v)

    out = []
    for iid in sorted(snap.candles.keys()):
        bars = snap.candles[iid]
        if not bars:
            continue
        # Bars come back from Blofin in chronological order after our reversal.
        # Keep last 30 to stay prompt-budget-friendly.
        recent = bars[-30:]
        rendered = " ".join(
            f"{ts}:{o},{h},{l},{c},{v}" for ts, o, h, l, c, v in (_bar_fields(b) for b in recent)
        )
        out.append(f"{iid}: {rendered}")
    return "\n".join(out)


def _format_instruments(snap: MarketSnapshot) -> str:
    """Compact lotSz/minSz reference for the top N so the LLM can size orders."""
    sorted_t = sorted(
        snap.tickers.values(), key=lambda t: t.vol_24h_quote, reverse=True
    )[: snap.top_n]
    lines = ["instId            lotSz       minSz      state"]
    for t in sorted_t:
        inst = snap.instruments.get(t.instId)
        if not inst:
            continue
        lines.append(
            f"{t.instId:<18}{inst.lotSz:<12}{inst.minSz:<12}{inst.state}"
        )
    return "\n".join(lines)


def _format_journal(journal: Journal, n: int) -> str:
    trades = journal.get_verbatim(n)
    return serialize_trades_for_prompt(trades)


def build_user_prompt(
    snapshot: MarketSnapshot,
    journal: Journal,
    *,
    verbatim_n: int = 30,
    tick_num: int = 0,
) -> str:
    summary = journal.get_summary()
    playbook = format_playbook(load_backtest_best())
    sections = [
        f"=== TICK {tick_num} ===",
        "",
        "## Account",
        _format_account(snapshot),
        "",
        "## Open positions",
        _format_positions(snapshot),
        "",
        "## Open orders",
        _format_open_orders(snapshot),
        "",
        f"## Top {snapshot.top_n} market (sorted by 24h quote volume)",
        _format_top_market(snapshot),
        "",
        f"## Instrument lot sizes (top {snapshot.top_n})",
        _format_instruments(snapshot),
        "",
        "## Recent 1m candles (oldest -> newest, last 30 bars each)",
        _format_candles(snapshot),
        "",
        f"## Your last {verbatim_n} trades (verbatim)",
        _format_journal(journal, verbatim_n),
    ]
    if playbook:
        sections.extend(["", "## Optimized playbook (load this into your thesis)", playbook])
    if summary:
        sections.extend([
            "",
            "## Summary of older trades (your own digest, refreshed periodically)",
            summary,
        ])
    sections.extend([
        "",
        "## Your move",
        "Decide now. Output EXACTLY one JSON object. No prose, no fences.",
    ])
    return "\n".join(sections)


SYSTEM = SYSTEM_PROMPT
USER = build_user_prompt
