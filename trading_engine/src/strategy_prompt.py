from __future__ import annotations

from typing import Any

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
(breakout AND ROC momentum, 10x leverage, SL~3% / TP~25%).
Prefer that playbook when the live tape supports it. Your journal can
override signal choice if live results clearly disagree - but POSITION
SIZING is calculated based on risk and available margin:
  risk_usd = equity * 0.01
  margin   = risk_usd / (leverage * stop_loss_pct)   # e.g. 0.40/(10*0.03) ~= $1.33
  notional = margin * leverage
  sz       = notional / price   (lot-snapped)
Trade high-conviction setups as capital permits. Do not invent oversized sz.
CRITICAL: Output ONLY the raw JSON object. Do NOT include pre-amble, conversational analysis, thinking steps, or markdown fences. Start your response directly with '{' and end with '}'.
{
  "thesis":          "1-3 sentences on market regime, current positions, and execution rationale",
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


def build_user_prompt(
    tick_num: int,
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    top20: list[dict[str, Any]],
    lot_sizes: dict[str, dict[str, str]],
    candles: dict[str, list[dict[str, Any]]],
    trades: list[dict[str, Any]],
    summary_text: str,
) -> str:
    lines: list[str] = [f"=== TICK {tick_num} ===", ""]

    lines.append("## Account")
    lines.append(
        f"Equity={account.get('equity')}, Available={account.get('available')}, "
        f"MarginUsed={account.get('margin_used')}, UnrealizedPnl={account.get('unrealized_pnl')}"
    )
    lines.append("")

    lines.append("## Open positions")
    if positions:
        for p in positions:
            lines.append(
                f"{p.get('instId')} side={p.get('side')} sz={p.get('sz')} entry_px={p.get('entryPx')} "
                f"mark_px={p.get('markPx')} leverage={p.get('leverage')} liq_px={p.get('liqPx')} "
                f"unrealized_pnl={p.get('unrealizedPnl')}"
            )
    else:
        lines.append("None")
    lines.append("")

    lines.append("## Top 20 market")
    lines.append("instId | last | 24h% | 1h% | funding | vol24h | oi_chg24h%")
    for m in top20:
        lines.append(
            f"{m.get('instId')} | {m.get('last')} | {m.get('open24h_pct')}% | {m.get('open1h_pct')}% | "
            f"{m.get('funding')} | {m.get('vol24h')} | {m.get('oi_chg24h_pct')}%"
        )
    lines.append("")

    lines.append("## Instrument lot sizes")
    for inst, meta in lot_sizes.items():
        lines.append(f"{inst}: lotSz={meta.get('lotSz')}, minSz={meta.get('minSz')}")
    lines.append("")

    lines.append("## Recent 1m candles (last 30, oldest -> newest)")
    for inst, rows in candles.items():
        c_str = " ".join(
            f"{r['ts']}:{r['o']},{r['h']},{r['l']},{r['c']},{r['vol']}" for r in rows
        )
        lines.append(f"{inst}: {c_str}")
    lines.append("")

    lines.append("## Your last 30 trades (verbatim)")
    if trades:
        for t in trades:
            lines.append(
                f"#{t.get('id')} t={t.get('tick')} {t.get('instId')} {t.get('side')} {t.get('action')} "
                f"sz={t.get('sz')} px={t.get('px')} lev={t.get('leverage')} pnl={t.get('pnl_usdt')} | {t.get('rationale')}"
            )
    else:
        lines.append("None")
    lines.append("")

    lines.append("## Summary of older trades")
    lines.append(summary_text or "No summary yet.")
    lines.append("")

    lines.append("## Your move")
    lines.append(
        "Respond ONLY with raw JSON matching the schema. No preamble, no markdown fences."
    )
    return "\n".join(lines)
