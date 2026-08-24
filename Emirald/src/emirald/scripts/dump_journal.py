"""Quick journal reader for Emirald.

Usage:
    python -m emirald.scripts.dump_journal
    python -m emirald.scripts.dump_journal --limit 20
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from ..config import load_all
from ..journal import Journal


def _db_path(config) -> Path:
    return Path(config.journal.db_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump Emirald journal")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    _, config = load_all("config.yaml")
    journal = Journal(_db_path(config))
    rows = journal.recent(args.limit)
    if not rows:
        print("(no trades yet)")
        return 0

    print(f"== Emirald journal (last {len(rows)}) ==\n")
    for row in rows:
        print(
            f"{row.ts}  {row.instId}  {row.side}  {row.action}  sz={row.sz}  "
            f"px={row.px or '-'}  lev={row.leverage or '-'}  pnl={row.pnl_usdt or 0}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
