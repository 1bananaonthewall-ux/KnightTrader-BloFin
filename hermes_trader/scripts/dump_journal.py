"""Pretty-print the SQLite journal: recent trades + cached summary + today PnL."""
from __future__ import annotations

import sys
from pathlib import Path

from ..config import load_all
from ..journal import Journal


def main(argv: list[str]) -> int:
    n = 30
    if len(argv) > 1:
        try:
            n = int(argv[1])
        except ValueError:
            print(f"usage: {argv[0]} [N]", file=sys.stderr)
            return 2

    _, config = load_all("config.yaml")
    journal = Journal(config.journal.db_path)

    print(f"== Hermes journal ==\n")
    print(f"db: {config.journal.db_path}")
    print(f"total trades: {journal.total_trades()}")
    print(f"pnl today (UTC): {journal.pnl_today():+.4f} USDT\n")

    trades = journal.get_verbatim(n)
    if not trades:
        print("(no trades yet)")
    else:
        print(f"-- last {len(trades)} trades --")
        for t in trades:
            pnl = f"{t.pnl_usdt:+.4f}" if t.pnl_usdt is not None else "open"
            print(
                f"#{t.id:>5} tick={t.tick:>5} {t.instId:<14} "
                f"{t.side:<5} {t.action:<18} sz={t.sz:<10} px={str(t.px or '?'):<10} "
                f"lev={str(t.leverage or '?'):<3} pnl={pnl:<10} "
                f"{(t.rationale or '')[:80]}"
            )

    summary = journal.get_summary()
    if summary:
        print(f"\n-- cached summary --\n{summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
