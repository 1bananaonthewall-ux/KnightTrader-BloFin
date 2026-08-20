"""Market data assembly for a single tick.

Each cycle we fetch:
1. Account balance (private)
2. Open positions (private)
3. Tickers for every USDT perp on Blofin (public, batched)
4. 1m candles for the top N by 24h quote volume (public)

Why top N and not everything:
- Full universe of 1m candles across 200+ tickers would be 200+ REST calls
  and tens of thousands of numbers. That's wasted latency, wasted prompt
  tokens, and worse signal (the LLM can't reason about that much at once).
- 20 is the sweet spot: enough cross-market context for the LLM to spot
  regime, small enough to stay under 60K prompt tokens.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from .blofin_client import BlofinClient

logger = logging.getLogger(__name__)


@dataclass
class TickerSnapshot:
    instId: str
    last: float
    change_24h_pct: float
    change_1h_pct: float
    vol_24h_quote: float
    vol_24h_base: float
    funding_rate: float | None
    oi: float | None
    oi_change_24h_pct: float | None


@dataclass
class Instrument:
    instId: str
    tickSz: float
    lotSz: float
    minSz: float
    contract_value: float | None = None  # not always returned by Blofin
    state: str = "live"


@dataclass
class AccountSnapshot:
    equity: float
    available: float
    margin_used: float
    unrealized_pnl: float
    details: list[dict] = field(default_factory=list)


@dataclass
class PositionSnapshot:
    instId: str
    side: str           # "long" | "short"
    sz: float
    entry_px: float
    mark_px: float
    liq_px: float | None
    margin: float
    leverage: int | None
    unrealized_pnl: float
    age_ms: int
    cl_ord_id: str | None = None


@dataclass
class MarketSnapshot:
    account: AccountSnapshot
    positions: list[PositionSnapshot]
    open_orders: list[dict]
    instruments: dict[str, Instrument]    # instId -> instrument
    tickers: dict[str, TickerSnapshot]   # instId -> ticker
    candles: dict[str, list[dict]]       # instId -> last 60 1m bars
    top_n: int = 20


def fetch_universe(client: BlofinClient) -> dict[str, Instrument]:
    """Call once at startup. Returns instId -> Instrument with lot size info."""
    raw = client.list_usdt_perps()
    out: dict[str, Instrument] = {}
    for x in raw:
        try:
            tick = float(x.get("tickSz", x.get("tickSize", "0")) or 0)
            lot = float(x.get("lotSz", x.get("lotSize", "0")) or 0)
            mn = float(x.get("minSz", x.get("minSize", x.get("minQty", "0"))) or 0)
            cv = float(x.get("contractValue", x.get("ctVal", "0")) or 0) or None
        except (TypeError, ValueError):
            continue
        if lot <= 0:
            continue
        out[x["instId"]] = Instrument(
            instId=x["instId"],
            tickSz=tick,
            lotSz=lot,
            minSz=mn,
            contract_value=cv,
            state=x.get("state", "live"),
        )
    return out


def fetch_account(client: BlofinClient) -> AccountSnapshot:
    raw = client.get_balance()
    details = raw.get("details", []) or []
    equity = float(
        raw.get("totalEquity")
        or raw.get("totalEq")
        or 0
        or 0
    )
    usdt = next(
        (
            d
            for d in details
            if (d.get("currency") or d.get("ccy") or "").upper() == "USDT"
        ),
        {},
    )
    if equity <= 0 and usdt:
        equity = float(usdt.get("equity") or usdt.get("eq") or usdt.get("equityUsd") or 0)
    available = float(
        usdt.get("available")
        or usdt.get("availableEquity")
        or usdt.get("availEq")
        or 0
    )
    margin_used = float(usdt.get("frozen") or usdt.get("orderFrozen") or 0)
    unrealized = float(
        usdt.get("isolatedUnrealizedPnl") or usdt.get("upl") or usdt.get("unrealizedPnl") or 0
    )
    return AccountSnapshot(
        equity=equity,
        available=available,
        margin_used=margin_used,
        unrealized_pnl=unrealized,
        details=details,
    )


def fetch_positions(client: BlofinClient) -> list[PositionSnapshot]:
    out: list[PositionSnapshot] = []
    for p in client.get_positions() or []:
        try:
            sz = float(p.get("positions") or p.get("pos") or 0)
        except (TypeError, ValueError):
            continue
        if abs(sz) == 0:
            continue
        side_raw = (p.get("positionSide") or p.get("posSide") or "").lower()
        if side_raw == "short":
            side = "short"
        elif side_raw == "long":
            side = "long"
        else:
            side = "long" if sz > 0 else "short"
        try:
            out.append(
                PositionSnapshot(
                    instId=p.get("instId", ""),
                    side=side,
                    sz=abs(sz),
                    entry_px=float(p.get("averagePrice") or p.get("avgPx") or 0),
                    mark_px=float(p.get("markPrice") or p.get("markPx") or 0),
                    liq_px=(
                        float(p["liquidationPrice"])
                        if p.get("liquidationPrice")
                        else (float(p["liqPx"]) if p.get("liqPx") else None)
                    ),
                    margin=float(p.get("margin") or 0),
                    leverage=(
                        int(float(p["leverage"]))
                        if p.get("leverage")
                        else (int(p["lever"]) if p.get("lever") else None)
                    ),
                    unrealized_pnl=float(p.get("unrealizedPnl") or p.get("upl") or 0),
                    age_ms=int(p.get("createTime") or p.get("cTime") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return out


def fetch_tickers(client: BlofinClient, inst_ids: list[str]) -> dict[str, TickerSnapshot]:
    raw = client.get_tickers_batch(inst_ids)
    out: dict[str, TickerSnapshot] = {}
    for iid, t in raw.items():
        try:
            last = float(t.get("last", 0) or 0)
            open_24h = float(t.get("open24h", 0) or 0)
            ch24 = ((last - open_24h) / open_24h * 100.0) if open_24h else 0.0
            out[iid] = TickerSnapshot(
                instId=iid,
                last=last,
                change_24h_pct=ch24,
                change_1h_pct=0.0,  # Blofin free tier may not return 1h; computed elsewhere
                vol_24h_quote=float(t.get("volCcy24h", 0) or 0),
                vol_24h_base=float(t.get("vol24h", 0) or 0),
                funding_rate=_safe_float(t.get("fundingRate")),
                oi=_safe_float(t.get("openInterest")),
                oi_change_24h_pct=_safe_float(t.get("oiChange24h")),
            )
        except (TypeError, ValueError):
            continue
    return out


def _safe_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_candles_parallel(
    client: BlofinClient,
    inst_ids: list[str],
    *,
    bar: str = "1m",
    limit: int = 60,
    workers: int = 8,
) -> dict[str, list[dict]]:
    """Fetch 1m candles for many instruments in parallel."""
    out: dict[str, list[dict]] = {}

    def _one(iid: str) -> tuple[str, list[dict]]:
        try:
            return iid, client.get_candles(iid, bar=bar, limit=limit)
        except Exception as e:  # noqa: BLE001
            logger.warning("candle fetch failed for %s: %s", iid, e)
            return iid, []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for iid, bars in ex.map(_one, inst_ids):
            out[iid] = bars
    return out


def select_top_n(
    tickers: dict[str, TickerSnapshot],
    instruments: dict[str, Instrument],
    n: int = 20,
) -> list[str]:
    """Pick top N by 24h quote volume, only listing instruments in our
    `instruments` map (i.e. USDT perps in live state).
    """
    candidates = [
        t for iid, t in tickers.items()
        if iid in instruments and instruments[iid].state == "live"
    ]
    candidates.sort(key=lambda t: t.vol_24h_quote, reverse=True)
    return [t.instId for t in candidates[:n]]


def build_snapshot(
    client: BlofinClient,
    instruments: dict[str, Instrument],
    *,
    top_n: int = 20,
    account: AccountSnapshot | None = None,
    positions: list[PositionSnapshot] | None = None,
    open_orders: list[dict] | None = None,
) -> MarketSnapshot:
    """The all-in-one per-tick snapshot. This is what gets fed to the LLM.

    In demo/paper mode, pass `account` / `positions` from PaperBroker so we
    never read live private balance/positions endpoints for trading state.
    """
    if account is None:
        account = fetch_account(client)
    if positions is None:
        positions = fetch_positions(client)
    if open_orders is None:
        open_orders = client.get_open_orders() or []

    inst_ids = [iid for iid, inst in instruments.items() if inst.state == "live"]
    tickers = fetch_tickers(client, inst_ids)
    top_ids = select_top_n(tickers, instruments, n=top_n)
    candles = fetch_candles_parallel(client, top_ids, bar="1m", limit=60)

    return MarketSnapshot(
        account=account,
        positions=positions,
        open_orders=open_orders,
        instruments=instruments,
        tickers=tickers,
        candles=candles,
        top_n=top_n,
    )
