from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.blofin_client import BlofinClient


class MarketData:
    def __init__(self, client: BlofinClient) -> None:
        self.client = client
        self.universe: list[str] = []
        self.top20: list[dict[str, Any]] = []
        self.lot_sizes: dict[str, dict[str, str]] = {}
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.candles: dict[str, list[dict[str, Any]]] = {}

    def refresh_universe(self) -> list[str]:
        try:
            data = self.client.get_tickers()
            items = data.get("data", []) or []
        except Exception:
            items = []
        universe = []
        for item in items:
            inst_id = item.get("instId")
            if inst_id and inst_id.endswith("-USDT-SWAP"):
                universe.append(inst_id)
                self.snapshots[inst_id] = item
        self.universe = sorted(set(universe))
        try:
            ranked = sorted(
                self.universe,
                key=lambda x: float((self.snapshots.get(x) or {}).get("vol24h", "0") or "0"),
                reverse=True,
            )
            self.top20 = ranked[:20]
        except Exception:
            self.top20 = self.universe[:20]
        return self.universe

    def refresh_top20_state(self) -> None:
        candles_out: dict[str, list[dict[str, Any]]] = {}
        for inst in self.top20:
            try:
                raw = self.client.get_candles(inst, limit=30)
                rows = []
                for row in raw.get("data", []) or []:
                    rows.append(
                        {
                            "ts": row[0],
                            "o": row[1],
                            "h": row[2],
                            "l": row[3],
                            "c": row[4],
                            "vol": row[5],
                        }
                    )
                candles_out[inst] = rows
            except Exception:
                candles_out[inst] = []
            snap = self.snapshots.get(inst, {})
            self.lot_sizes[inst] = {
                "lotSz": snap.get("lotSz", "0.001"),
                "minSz": snap.get("minSz", "0.001"),
            }
        self.candles = candles_out
