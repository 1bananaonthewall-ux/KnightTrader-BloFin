# Hermes Trader

A bot that wakes up every minute, asks the Hermes LLM (via Nous Portal) what to
do with your Blofin perpetual futures account, acts on it, and goes back to
sleep. It "learns" by reading its own trade journal in-context.

> **Risk warning (read once, then it's on record):** This bot is intentionally
> built with **no position cap, no daily-loss cap, no drawdown cap, and no
> leverage cap** per the user's explicit decision. The free Nous Portal tier
> has variable latency. The combination — guardless live perpetuals on a 1-min
> loop driven by a free cloud LLM across the full Blofin universe — is the
> configuration most likely to liquidate the account. You accepted this. If
> the account goes to zero overnight, that's the design, not a bug. There is a
> single empty `risk_none.py` module wired into the loop, with a one-line swap
> to a real `risk.py` if you change your mind.

## First run

```powershell
cd C:\Users\mknig\hermes-trader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env: fill in BLOFIN_API_KEY, BLOFIN_API_SECRET, NOUS_PORTAL_KEY
python -m hermes_trader.scripts.first_run_check
```

`first_run_check.py` verifies both API keys work, fetches the full perp
universe from Blofin, and runs one cheap LLM call. **Do not start the loop
until this exits 0 and the universe looks sensible.**

## Running

```powershell
python -m hermes_trader
```

Console shows one line per tick:
```
tick=42  llm_ms=8120  decisions=0  fills=0  pnl_today=+0.00USDT  equity=523.10USDT  reason="ranging, no edge"
```

`Ctrl+C` finishes the current tick and exits cleanly.

To run detached from the terminal, schedule it via Windows Task Scheduler
("Run whether user is logged on or not"), action =
`C:\Users\mknig\hermes-trader\.venv\Scripts\pythonw.exe -m hermes_trader`,
working directory `C:\Users\mknig\hermes-trader`. Triggers = "At system
startup" + on logon.

## Inspecting the journal

```powershell
python -m hermes_trader.scripts.dump_journal
```

Prints the last N trades, the cached summary, and account state.

## Risk off-switch (future-you)

To add guardrails: implement `hermes_trader/risk.py` with a real
`apply(decision, account_state) -> decision` function, then in
`hermes_trader/loop.py` change the import from `risk_none` to `risk` and
the wiring takes over.

## Tests

```powershell
pip install pytest
pytest tests/
```

Signing test uses a known vector. Decision parser test uses canned LLM
outputs. Journal test covers FIFO P&L and the rolling summary.
