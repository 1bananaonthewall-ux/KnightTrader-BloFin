"""Pre-flight check. Run this before `python -m hermes_trader`.

Verifies:
1. .env loads and all four keys are present.
2. Blofin API key works (account balance returns successfully).
3. Nous Portal key works (one cheap LLM call).
4. We can list the USDT perp universe from Blofin.
5. Prints a sample of the largest-volume tickers with their lot sizes.

If anything fails, prints a clear error and exits non-zero. **Do not start
the loop until this exits 0.**
"""
from __future__ import annotations

import sys

from ..blofin_client import BlofinAPIError, BlofinClient
from ..config import load_all
from ..market_data import fetch_universe
from ..nous_client import LLMUnavailable, NousClient


def main() -> int:
    print("== Hermes first-run check ==\n")

    try:
        secrets, config = load_all("config.yaml")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] config load: {e}")
        print("       Did you copy .env.example to .env and fill in BLOFIN_API_KEY, "
              "BLOFIN_API_SECRET, NOUS_PORTAL_KEY?")
        return 2

    print("[OK]   config loaded")
    print(f"       model={config.llm.model}")
    print(f"       base_url={config.llm.base_url}")
    print(f"       loop interval={config.loop.interval_seconds}s (+/- {config.loop.jitter_seconds}s)")
    print(f"       td_mode={config.mode}\n")

    # Blofin
    client = BlofinClient(
        api_key=secrets.blofin_api_key,
        api_secret=secrets.blofin_api_secret,
        passphrase=getattr(secrets, "blofin_passphrase", "") or "",
    )
    try:
        balance = client.get_balance()
        print(f"[OK]   Blofin auth works")
        total_eq = balance.get("totalEq", "?")
        details = balance.get("details", [])
        usdt = next((d for d in details if d.get("ccy") == "USDT"), {})
        print(f"       totalEq={total_eq}  USDT available={usdt.get('availEq', '?')}\n")
    except BlofinAPIError as e:
        print(f"[FAIL] Blofin auth/balance: {e}")
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] Blofin call crashed: {e}")
        return 3

    # Universe
    try:
        universe = fetch_universe(client)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] could not list USDT perps: {e}")
        return 4
    if not universe:
        print("[FAIL] universe is empty. Blofin returned no USDT swaps.")
        return 4
    print(f"[OK]   {len(universe)} USDT perps resolved")
    sample = list(universe.items())[:10]
    print("       first 10:")
    for iid, inst in sample:
        print(f"         {iid:<18} lotSz={inst.lotSz} minSz={inst.minSz} state={inst.state}")
    print()

    # Nous Portal
    llm = NousClient(
        api_key=secrets.nous_portal_key,
        model=config.llm.model,
        base_url=config.llm.base_url,
        timeout_seconds=20,
        reasoning_effort="low",
    )
    try:
        resp = llm.cheap_call("Reply with one word: ready")
    except LLMUnavailable as e:
        print(f"[FAIL] Nous Portal: {e}")
        return 5
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] Nous Portal crashed: {e}")
        return 5
    print(f"[OK]   Nous Portal works: {resp.strip()[:80]!r}\n")

    print("All checks passed. You can now run:  python -m hermes_trader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
