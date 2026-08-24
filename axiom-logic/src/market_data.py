from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .blofin_client import BlofinClient, Candle, Instrument, Ticker
from .config import settings


class MarketSnapshot:
    def __init__(self) -> None:
        self.tickers: list[Ticker] = []
        self.top20_tickers: list[Ticker] = []
        self.top20_candles: dict[str, list[Candle]] = {}
        self.instruments: dict[str, Instrument] = {}
        self.positions: list[Any] = []
        self.balances: list[Any] = []
        self.universe: list[str] = []
        self.refreshed_at = datetime.now(timezone.utc)

    @property
    def timestamp_iso(self) -> str:
        return self.refreshed_at.isoformat()


class AxiomMarketData:
    def __init__(self, client: BlofinClient) -> None:
        self.client = client
        self._snapshot = MarketSnapshot()
        self.refresh_universe = True

    def snapshot(self, top_n: int = 20) -> MarketSnapshot:
        snap = MarketSnapshot()
        tickers = self.client.get_tickers()
        tickers.sort(key=lambda x: float(x.quoteVolume or 0), reverse=True)
        snap.tickers = tickers
        snap.top20_tickers = tickers[:top_n]
        snap.universe = self.client.universe()
        snap.instruments = self._instrument_map()
        snap.positions = self.client.get_positions()
        snap.balances = self.client.get_balances("USDT")
        for t in snap.top20_tickers:
            try:
                snap.top20_candles[t.instId] = self.client.get_candles(t.instId, "1m", 30)
            except Exception:
                snap.top20_candles[t.instId] = []
        self._snapshot = snap
        return snap

    def _instrument_map(self) -> dict[str, Instrument]:
        try:
            instruments = self.client.get_instruments()
            return {i.instId: i for i in instruments if getattr(i, "instId", "")}
        except Exception:
            return {}

    def formatted_top20_table(self) -> str:
        snap = self._snapshot
        lines = ["| instId | last | 24h% | 1h% | funding | vol24h | oi_chg24h% |"]
        lines.append("|---|---|---|---|---|---|---|")
        for t in snap.top20_tickers:
            try:
                last = float(t.last or 0)
                o24 = float(t.open24h or 0)
                open24 = float(t.open24h or 0)
                h24 = float(t.high24h or 0)
                l24 = float(t.low24h or 0)
                chg24 = ((last - o24) / o24 * 100) if o24 else 0.0
                chg1h = 0.0
                candles = snap.top20_candles.get(t.instId, [])
                if len(candles) >= 2:
                    c1 = candles[-2]
                    c0 = candles[-1]
                    o1 = float(c1.o or 0)
                    c = float(c0.c or 0)
                    chg1h = ((c - o1) / o1 * 100) if o1 else 0.0
                lines.append(
                    f"| {t.instId} | {last:.4g} | {chg24:+.2f}% | {chg1h:+.2f}% | {t.quoteVolume} | {t.quoteVolume} | {(float(t.openInterest or 0)):.2f} |"
                )
            except Exception:
                continue
        return "\n".join(lines) if len(lines) > 2 else "No top20 market data."

    def formatted_open_positions(self) -> str:
        positions = self._snapshot.positions
        if not positions:
            return "No open positions."
        lines = ["| instId | side | sz | entry_px | mark_px | leverage | liq_px | unrealized_pnl |"]
        lines.append("|---|---|---|---|---|---|---|---|")
        for p in positions:
            try:
                lines.append(
                    f"| {getattr(p, 'instId', '')} | {getattr(p, 'side', '')} | {getattr(p, 'sz', '')} | {getattr(p, 'entry_px', '')} | {getattr(p, 'mark_px', '')} | {getattr(p, 'leverage', '')} | {getattr(p, 'liq_px', '')} | {getattr(p, 'unrealized_pnl', '')} |"
                )
            except Exception:
                continue
        return "\n".join(lines)

    def formatted_account(self) -> str:
        lines = []
        for b in self._snapshot.balances:
            lines.append(f"{getattr(b, 'ccy', 'USDT')}: equity={getattr(b, 'eq', '')} avail={getattr(b, 'avail_eq', '')} frozen={getattr(b, 'frozen', '')}")
        return "\n".join(lines) if lines else "No balance data."
