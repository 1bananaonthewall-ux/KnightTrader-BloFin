"""Tiny live test trade for Emirald.

Places a minimal BTC-USDT market open, verifies position and journal entry,
then closes the position and verifies realized PnL/journal.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from emirald.blofin_client import BlofinAPIError, BlofinClient
from emirald.config import load_all
from emirald.decision import CycleDecision, Decision
from emirald.executor import execute_decisions
from emirald.journal import Journal


def main() -> int:
    os.chdir(ROOT)
    secrets, config = load_all("config.yaml")
    client = BlofinClient(
        api_key=secrets.blofin_api_key,
        api_secret=secrets.blofin_api_secret,
        passphrase=secrets.blofin_passphrase,
        broker_id=getattr(secrets, "blofin_broker_id", "") or "",
        position_mode=getattr(config, "position_mode", "net") or "net",
    )
    journal = Journal(config.journal.db_path)

    inst_id = "BTC-USDT"
    td_mode = config.mode
    leverage = 10
    sz = "0.1"

    ticker = client.get_ticker(inst_id)
    last = float((ticker or {}).get("last") or (ticker or {}).get("lastPr") or 0)
    if last <= 0:
        print(f"[FAIL] unable to get price for {inst_id}")
        return 2

    print(f"[INFO] placing tiny test open {sz} {inst_id} @ market last={last}")

    open_decision = Decision(
        instId=inst_id,
        action="open",
        side="buy",
        orderType="market",
        sz=sz,
        leverage=leverage,
        rationale="emirald live test open",
    )
    try:
        open_outcomes = execute_decisions(
            [open_decision],
            tick=1,
            client=client,
            journal=journal,
            td_mode=td_mode,
            decision_raw="emirald-live-test",
            demo=False,
        )
    except BlofinAPIError as e:
        print(f"[FAIL] open order rejected: {e}")
        return 3
    print(f"[OK] open outcomes: {open_outcomes}")

    time.sleep(2)

    positions = client.get_positions()
    pos = next((p for p in positions if p.get("instId") == inst_id), None)
    if not pos:
        print("[FAIL] position not found after open")
        return 4
    print(f"[OK] position: {pos}")

    close_decision = Decision(
        instId=inst_id,
        action="close",
        side="sell",
        orderType="market",
        sz=sz,
        leverage=leverage,
        rationale="emirald live test close",
    )
    try:
        close_outcomes = execute_decisions(
            [close_decision],
            tick=2,
            client=client,
            journal=journal,
            td_mode=td_mode,
            decision_raw="emirald-live-test",
            demo=False,
        )
    except BlofinAPIError as e:
        print(f"[FAIL] close order rejected: {e}")
        return 5
    print(f"[OK] close outcomes: {close_outcomes}")

    time.sleep(2)
    rows = journal.get_verbatim(20)
    test_rows = [r for r in rows if inst_id in str(r.instId)]
    if not test_rows:
        print("[FAIL] no journal rows for test trade")
        return 6
    print("[OK] journal rows:")
    for row in test_rows[-4:]:
        print(
            f"  {row.ts} {row.instId} {row.side} {row.action} sz={row.sz} px={row.px or '-'} "
            f"lev={row.leverage or '-'} pnl={row.pnl_usdt or 0} rationale={row.rationale or ''}"
        )
    print("[OK] tiny live test trade completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
