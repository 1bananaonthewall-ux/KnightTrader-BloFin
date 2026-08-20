"""Blofin universe backtest + mixed-strategy optimization.

Usage (public live data, no API credentials required):
    python backtest.py --public
    python backtest.py --public --limit-instruments 50

Usage (live Blofin data):
    python backtest.py --mode full
    python backtest.py --mode quick --limit-instruments 50

Usage (synthetic data, no keys required):
    python backtest.py --synthetic --synthetic-instruments 240
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

import numpy as np
from dotenv import load_dotenv

from hermes_trader.blofin_client import BlofinClient
from hermes_trader.market_data import fetch_universe

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BAR = "5m"
DEFAULT_LIMIT = 1200
BENCHMARK = "backtest_results.csv"
BEST_FILE = "backtest_best.json"

# --- Data ---


@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    vol: float


@dataclass(frozen=True)
class BacktestResult:
    inst_id: str
    strategy: str
    mix: str
    params: dict
    total_return_pct: float
    sharpe_like: float
    max_drawdown_pct: float
    trades: int


def _rows_to_candles(rows: Sequence[Sequence[str]]) -> list[Candle]:
    out: list[Candle] = []
    for r in rows:
        try:
            out.append(
                Candle(
                    ts=int(r[0]),
                    o=float(r[1]),
                    h=float(r[2]),
                    l=float(r[3]),
                    c=float(r[4]),
                    vol=float(r[5]),
                )
            )
        except (IndexError, ValueError):
            continue
    out = sorted(out, key=lambda c: c.ts)
    seen: set[int] = set()
    deduped: list[Candle] = []
    for c in out:
        if c.ts in seen:
            continue
        seen.add(c.ts)
        deduped.append(c)
    return deduped


def _array(candles: Sequence[Candle]) -> np.ndarray:
    if not candles:
        return np.array([], dtype=float)
    return np.array([c.c for c in candles], dtype=float)


def load_universe(client: BlofinClient) -> list[str]:
    instruments = fetch_universe(client)
    return [iid for iid, inst in instruments.items() if inst.state.lower() == "live"]


def synthetic_universe(n: int = 120) -> list[str]:
    assets = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "AVAX", "MATIC",
        "LINK", "UNI", "ATOM", "LTC", "ETC", "FIL", "APT", "ARB", "OP", "SUI",
        "SEI", "TIA", "NEAR", "AAVE", "MKR", "RUNE", "FTM", "SAND", "MANA", "GALA",
        "ICP", "IMX", "GRT", "SNX", "CRV", "COMP", "1INCH", "ENJ", "CHZ", "BAT",
        "ZRX", "KAVA", "ALGO", "VET", "THETA", "FTM", "EOS", "XTZ", "DASH", "ZEC",
        "KSM", "BLUR", "GMX", "RNDR", "PEPE", "WIF", "BONK", "FLOKI", "TRX", "TON",
        "HBAR", "SHIB", "NEAR", "SUI", "APT", "SEI", "TIA", "STX", "MNT", "GMX",
        "ENR", "PIXEL", "PORTAL", "STRK", "MASK", "HIGH", "ASTR", "DYDX", "LDO", "SSV",
        "LQTY", "BIGTIME", "PEPE2", "OG", "MEME", "AIDOGE", "TSUGT", "SHIB2", "FLOKIPEPE", "BONK2",
        "XEC", "BABYDOGE", "ELON", "FEG", "SAFEMOON", "AKITA", "KISHU", "HOKK", "PIG", "SQUID",
        "MOON", "SAFE", "YFI", "CRV", "LRC", "KNC", "REN", "BNT", "STORJ", "CVC",
        "TRIBE", "BADGER", "KP3R", "MIR", "ALCX", "HEGIC", "OPYN", "NFTS", "ASK", "UNN",
        "DEXT", "ASTRO", "APW", "JOE", "SPELL", "MIM", "TIME", "ICE", "SPA", "GODS",
        "BTRFLY", "ALEPH", "UDT", "DYP", "ROOK", "INDEX", "PICKLE", "YAM", "BASED", "SUSHI",
        "LCX", "RARI", "UNLOCK", "INV", "DPI", "FLI", "MVC", "IBETH", "GYEN", "RENBTC",
        "WBTC", "HBTC", "TBTC", "SBTC", "OBTC", "PBTC", "UBTC", "BBTC", "KBTC", "MBTC",
        "CBTC", "DBTC", "EBTC", "FBTC", "GBTC", "IBTC", "JBTC", "NBTC", "PBTC", "QBTC",
        "RBTC", "SBTC", "TBTC", "UBTC", "VBTC", "WBTC", "XBTC", "YBTC", "ZBTC", "ABTC",
    ]
    names = []
    for i in range(n):
        base = assets[i % len(assets)]
        suffix = f"{(i // len(assets)) + 1}" if i >= len(assets) else ""
        names.append(f"{base}{suffix}-USDT")
    return names


# --- Indicators ---


def _sma(close: np.ndarray, window: int) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    if len(close) >= window:
        csum = np.cumsum(np.insert(close, 0, 0.0))
        out[window - 1 :] = (csum[window:] - csum[:-window]) / window
    return out


def _ema(close: np.ndarray, span: int) -> np.ndarray:
    out = np.empty_like(close, dtype=float)
    out[:] = np.nan
    if len(close) == 0:
        return out
    k = 2.0 / (span + 1)
    out[0] = close[0]
    for i in range(1, len(close)):
        if np.isnan(out[i - 1]):
            out[i] = close[i]
        else:
            out[i] = close[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    pad = np.zeros(period, dtype=float)
    avg_gain = np.concatenate([pad, np.convolve(gain, np.ones(period) / period, mode="full")[: len(close) - 1]])
    avg_loss = np.concatenate([pad, np.convolve(loss, np.ones(period) / period, mode="full")[: len(close) - 1]])
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_loss == 0, 0.0, avg_gain / avg_loss)
        rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def _roc(close: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    if len(close) <= period:
        return out
    out[period:] = (close[period:] - close[:-period]) / close[:-period] * 100.0
    return out


def _rolling_high(close: np.ndarray, window: int) -> np.ndarray:
    if close.size == 0:
        return np.array([], dtype=float)
    out = np.full_like(close, np.nan, dtype=float)
    stride = close.strides[0]
    shape = (close.shape[0] - window + 1, window)
    strides = (stride, stride)
    arr = np.lib.stride_tricks.as_strided(close, shape=shape, strides=strides)
    out[window - 1 :] = arr.max(axis=1)
    return out


def _rolling_low(close: np.ndarray, window: int) -> np.ndarray:
    if close.size == 0:
        return np.array([], dtype=float)
    out = np.full_like(close, np.nan, dtype=float)
    stride = close.strides[0]
    shape = (close.shape[0] - window + 1, window)
    strides = (stride, stride)
    arr = np.lib.stride_tricks.as_strided(close, shape=shape, strides=strides)
    out[window - 1 :] = arr.min(axis=1)
    return out


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    tr1 = high - low
    tr2 = np.abs(high - np.insert(close, 0, close[0])[:-1])
    tr3 = np.abs(low - np.insert(close, 0, close[0])[:-1])
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    out = np.full_like(close, np.nan, dtype=float)
    if close.size >= period:
        csum = np.cumsum(np.insert(tr, 0, 0.0))
        out[period - 1 :] = (csum[period:] - csum[:-period]) / period
    return out


# --- Strategies ---


def _strategy_sma_cross(close: np.ndarray, p: dict) -> np.ndarray:
    fast = _sma(close, int(p.get("fast", 20)))
    slow = _sma(close, int(p.get("slow", 50)))
    signal = np.zeros(len(close), dtype=int)
    in_pos = False
    for i in range(2, len(close)):
        f_prev, f_curr = fast[i - 1], fast[i]
        s_prev, s_curr = slow[i - 1], slow[i]
        if np.isnan(f_curr) or np.isnan(s_curr) or np.isnan(f_prev) or np.isnan(s_prev):
            continue
        if not in_pos and f_prev <= s_prev and f_curr > s_curr:
            signal[i] = 1
            in_pos = True
        elif in_pos and f_prev >= s_prev and f_curr < s_curr:
            signal[i] = -1
            in_pos = False
    return signal


def _strategy_rsi_reversion(close: np.ndarray, p: dict) -> np.ndarray:
    rsi = _rsi(close, int(p.get("period", 14)))
    low = float(p.get("low", 30))
    high = float(p.get("high", 70))
    signal = np.zeros(len(close), dtype=int)
    in_pos = False
    for i in range(2, len(close)):
        prev, curr = rsi[i - 1], rsi[i]
        if np.isnan(prev) or np.isnan(curr):
            continue
        if not in_pos and prev >= low and curr < low:
            signal[i] = 1
            in_pos = True
        elif in_pos and prev <= high and curr > high:
            signal[i] = -1
            in_pos = False
    return signal


def _strategy_roc_momentum(close: np.ndarray, p: dict) -> np.ndarray:
    roc = _roc(close, int(p.get("period", 10)))
    threshold = float(p.get("threshold", 1.0))
    signal = np.zeros(len(close), dtype=int)
    in_pos = False
    for i in range(2, len(close)):
        if np.isnan(roc[i]):
            continue
        if not in_pos and roc[i] > threshold:
            signal[i] = 1
            in_pos = True
        elif in_pos and roc[i] < -threshold:
            signal[i] = -1
            in_pos = False
    return signal


def _strategy_breakout(close: np.ndarray, p: dict) -> np.ndarray:
    window = int(p.get("window", 20))
    rh = _rolling_high(close, window)
    rl = _rolling_low(close, window)
    signal = np.zeros(len(close), dtype=int)
    in_pos = False
    for i in range(2, len(close)):
        if np.isnan(rh[i]) or np.isnan(rl[i]):
            continue
        if not in_pos and close[i] >= rh[i]:
            signal[i] = 1
            in_pos = True
        elif in_pos and close[i] <= rl[i]:
            signal[i] = -1
            in_pos = False
    return signal


STRATEGIES: Dict[str, Callable[[np.ndarray, dict], np.ndarray]] = {
    "sma_cross": _strategy_sma_cross,
    "rsi_reversion": _strategy_rsi_reversion,
    "roc_momentum": _strategy_roc_momentum,
    "breakout": _strategy_breakout,
}


# --- Mixes ---


def _mix_signals(signals: List[np.ndarray], mode: str) -> np.ndarray:
    if not signals:
        return np.array([], dtype=int)
    combined = np.zeros(len(signals[0]), dtype=int)
    if mode == "OR":
        any_one = np.any(np.stack(signals) == 1, axis=0)
        any_neg = np.any(np.stack(signals) == -1, axis=0)
        combined = np.where(any_one, 1, np.where(any_neg, -1, 0))
    elif mode == "AND":
        all_one = np.all(np.stack(signals) == 1, axis=0)
        all_neg = np.all(np.stack(signals) == -1, axis=0)
        combined = np.where(all_one, 1, np.where(all_neg, -1, 0))
    elif mode == "VOTE_2_OF_3":
        if len(signals) < 3:
            return signals[0]
        arr = np.stack(signals)
        ones = np.sum(arr == 1, axis=0)
        negs = np.sum(arr == -1, axis=0)
        combined = np.where(ones >= 2, 1, np.where(negs >= 2, -1, 0))
    else:
        combined = signals[0]
    return combined


# --- Backtest Engine ---


def _backtest_from_signal(
    close: np.ndarray,
    signal: np.ndarray,
    *,
    initial_capital: float = 1000.0,
    position_pct: float = 1.0,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
) -> Tuple[float, float, float, int]:
    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    returns: List[float] = []
    trades = 0
    in_position = False
    entry = 0.0
    qty = 0.0
    for i in range(1, len(close)):
        price = float(close[i])
        if not in_position and int(signal[i]) == 1:
            entry = price
            qty = equity * position_pct / entry if entry > 0 else 0.0
            in_position = True
        elif in_position:
            move = (price - entry) / entry if entry > 0 else 0.0
            if int(signal[i]) == -1 or move <= -stop_loss_pct or move >= take_profit_pct:
                pnl = (price - entry) * qty
                prev = equity
                equity += pnl
                ret = (equity - prev) / prev if prev else 0.0
                returns.append(ret)
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
                in_position = False
                trades += 1
    total_return = (equity / initial_capital - 1.0) * 100.0
    if returns:
        arr = np.array(returns)
        mean = float(arr.mean())
        std = float(arr.std(ddof=0))
        sharpe = (mean / std * math.sqrt(252)) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return float(total_return), sharpe, float(max_dd * 100.0), trades


def _evaluate(close: np.ndarray, strategy: str, params: dict, mix: str = "") -> BacktestResult:
    sig = STRATEGIES[strategy](close, params)
    if mix:
        parts = [STRATEGIES[s](close, _coerce_strategy_params(s, params)) for s in mix.split("+")]
        sig = _mix_signals(parts, mix.split(":")[-1] if ":" in mix else "OR")
    total_return, sharpe, max_dd, trades = _backtest_from_signal(
        close,
        sig,
        stop_loss_pct=float(params.get("stop_loss_pct", 0.0)),
        take_profit_pct=float(params.get("take_profit_pct", 0.0)),
    )
    return BacktestResult(
        inst_id="",
        strategy=strategy,
        mix=mix,
        params=dict(params),
        total_return_pct=total_return,
        sharpe_like=sharpe,
        max_drawdown_pct=max_dd,
        trades=trades,
    )


def _backtest_from_signal(
    close: np.ndarray,
    signal: np.ndarray,
    *,
    initial_capital: float = 1000.0,
    position_pct: float = 1.0,
    stop_loss_pct: float = 0.0,
    take_profit_pct: float = 0.0,
) -> Tuple[float, float, float, int]:
    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    returns: List[float] = []
    trades = 0
    in_position = False
    entry = 0.0
    qty = 0.0
    for i in range(1, len(close)):
        price = float(close[i])
        if not in_position and int(signal[i]) == 1:
            entry = price
            qty = equity * position_pct / entry if entry > 0 else 0.0
            in_position = True
        elif in_position:
            move = (price - entry) / entry if entry > 0 else 0.0
            if int(signal[i]) == -1 or move <= -stop_loss_pct or move >= take_profit_pct:
                pnl = (price - entry) * qty
                prev = equity
                equity += pnl
                ret = (equity - prev) / prev if prev else 0.0
                returns.append(ret)
                peak = max(peak, equity)
                max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
                in_position = False
                trades += 1
    total_return = (equity / initial_capital - 1.0) * 100.0
    if returns:
        arr = np.array(returns)
        mean = float(arr.mean())
        std = float(arr.std(ddof=0))
        sharpe = (mean / std * math.sqrt(252)) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return float(total_return), sharpe, float(max_dd * 100.0), trades


def _signal_for_close(close: np.ndarray, strategy: str, params: dict, mix: str = "") -> np.ndarray:
    if mix:
        names = [s for s in mix.split(":")[0].split("+") if s]
        mode = mix.split(":")[-1] if ":" in mix else "OR"
        parts = [STRATEGIES[s](close, _coerce_strategy_params(s, params)) for s in names if s in STRATEGIES]
        if not parts:
            return STRATEGIES[strategy](close, params)
        return _mix_signals(parts, mode)
    return STRATEGIES[strategy](close, params)


def _align_universe(
    universe: List[Tuple[str, np.ndarray]],
    *,
    min_bars: int | None = None,
) -> List[Tuple[str, np.ndarray]]:
    """Drop short listings, then align remaining series on a shared bar window."""
    if not universe:
        return []
    lengths = [len(arr) for _, arr in universe]
    longest = max(lengths)
    # Prefer a near-full requested window; fall back gradually so we never
    # collapse a month of history down to a handful of bars from new listings.
    if min_bars is not None:
        candidates = [int(min_bars), max(60, int(min_bars * 0.9)), max(60, int(min_bars * 0.8))]
    else:
        candidates = [max(60, int(longest * 0.95)), max(60, int(longest * 0.8))]
    filtered: List[Tuple[str, np.ndarray]] = []
    for need in candidates:
        filtered = [(iid, arr) for iid, arr in universe if len(arr) >= need]
        if len(filtered) >= max(20, int(0.5 * len(universe))):
            break
    if not filtered:
        filtered = list(universe)
    target = min(len(arr) for _, arr in filtered)
    return [(iid, np.asarray(arr[-target:], dtype=float)) for iid, arr in filtered]


def _backtest_portfolio(
    universe: List[Tuple[str, np.ndarray]],
    strategy: str,
    params: dict,
    mix: str = "",
    *,
    initial_capital: float = 40.0,
    max_positions: int = 20,
    already_aligned: bool = False,
) -> Tuple[float, float, float, int]:
    if not universe:
        return 0.0, 0.0, 100.0, 0
    aligned = universe if already_aligned else _align_universe(universe)
    if not aligned:
        return 0.0, 0.0, 100.0, 0
    closes_arr = np.stack([arr for _, arr in aligned], axis=0)
    n, min_len = closes_arr.shape
    signals_arr = np.stack(
        [_signal_for_close(closes_arr[i], strategy, params, mix=mix) for i in range(n)],
        axis=0,
    )
    max_pos = max(1, min(int(params.get("max_positions", max_positions)), n))
    leverage = max(1.0, float(params.get("leverage", 1.0)))
    cash = float(initial_capital)
    peak = cash
    max_dd = 0.0
    returns: List[float] = []
    trades = 0
    entries = np.zeros(n, dtype=float)
    qtys = np.zeros(n, dtype=float)
    margins = np.zeros(n, dtype=float)
    in_pos = np.zeros(n, dtype=bool)
    stop = float(params.get("stop_loss_pct", 0.0))
    take = float(params.get("take_profit_pct", 0.0))
    open_idxs: list[int] = []

    def _mark_equity(idx: int) -> float:
        total = cash
        for j in open_idxs:
            price = closes_arr[j, idx]
            total += margins[j] + (price - entries[j]) * qtys[j]
        return float(total)

    for idx in range(1, min_len):
        # Exits first.
        still_open: list[int] = []
        for asset_idx in open_idxs:
            price = closes_arr[asset_idx, idx]
            entry = entries[asset_idx]
            move = (price - entry) / entry if entry > 0 else 0.0
            sig = int(signals_arr[asset_idx, idx])
            if sig == -1 or (stop > 0 and move <= -stop) or (take > 0 and move >= take):
                prev = _mark_equity(idx)
                pnl = (price - entry) * qtys[asset_idx]
                cash += margins[asset_idx] + pnl
                qtys[asset_idx] = 0.0
                entries[asset_idx] = 0.0
                margins[asset_idx] = 0.0
                in_pos[asset_idx] = False
                equity = _mark_equity(idx)
                if prev:
                    returns.append((equity - prev) / prev)
                peak = max(peak, equity)
                if peak:
                    max_dd = max(max_dd, (peak - equity) / peak)
                trades += 1
            else:
                still_open.append(asset_idx)
        open_idxs = still_open

        # Entries into free slots (only scan assets with long signals this bar).
        open_count = len(open_idxs)
        if open_count < max_pos and cash > 0:
            for asset_idx in np.flatnonzero(signals_arr[:, idx] == 1):
                if open_count >= max_pos:
                    break
                ai = int(asset_idx)
                if in_pos[ai]:
                    continue
                price = closes_arr[ai, idx]
                if price <= 0:
                    continue
                slots = max(1, max_pos - open_count)
                margin = cash / slots
                if margin <= 0:
                    break
                notional = margin * leverage
                qtys[ai] = notional / price
                entries[ai] = price
                margins[ai] = margin
                in_pos[ai] = True
                cash -= margin
                open_idxs.append(ai)
                open_count += 1

        equity = _mark_equity(idx)
        peak = max(peak, equity)
        if peak:
            max_dd = max(max_dd, (peak - equity) / peak)

    last = min_len - 1
    for asset_idx in list(open_idxs):
        price = closes_arr[asset_idx, last]
        pnl = (price - entries[asset_idx]) * qtys[asset_idx]
        cash += margins[asset_idx] + pnl
        qtys[asset_idx] = 0.0
        margins[asset_idx] = 0.0
        in_pos[asset_idx] = False
        trades += 1
    equity = cash
    total_return = (equity / initial_capital - 1.0) * 100.0 if initial_capital else 0.0
    if returns:
        arr = np.array(returns)
        mean = float(arr.mean())
        std = float(arr.std(ddof=0))
        sharpe = (mean / std * math.sqrt(252)) if std > 0 else 0.0
    else:
        sharpe = 0.0
    return float(total_return), sharpe, float(max_dd * 100.0), int(trades)


def _coerce_strategy_params(strategy: str, params: dict) -> dict:
    base: dict = {}
    suffix = f"__{strategy}"
    for k, v in params.items():
        if k.endswith(suffix):
            base[k[: -len(suffix)]] = v
        elif "__" not in k:
            base[k] = v
    if strategy == "sma_cross":
        base.setdefault("fast", 20)
        base.setdefault("slow", 50)
    elif strategy == "rsi_reversion":
        base.setdefault("period", 14)
        base.setdefault("low", 30)
        base.setdefault("high", 70)
    elif strategy == "roc_momentum":
        base.setdefault("period", 10)
        base.setdefault("threshold", 1.0)
    elif strategy == "breakout":
        base.setdefault("window", 20)
    return base


def _score_for_target(ret: float, target: float = 200.0) -> float:
    reward = max(0.0, ret)
    penalty = max(0.0, target - ret)
    return reward - 2.0 * penalty


def _evaluate_portfolio_strategy(
    universe: List[Tuple[str, np.ndarray]],
    strategy: str,
    params: dict,
    mix: str = "",
    *,
    target_return: float = 200.0,
    initial_capital: float = 40.0,
    already_aligned: bool = True,
) -> BacktestResult:
    total_return, sharpe, max_dd, trades = _backtest_portfolio(
        universe,
        strategy,
        params,
        mix=mix,
        initial_capital=initial_capital,
        already_aligned=already_aligned,
    )
    return BacktestResult(
        inst_id="",
        strategy=strategy,
        mix=mix,
        params=dict(params),
        total_return_pct=total_return,
        sharpe_like=sharpe,
        max_drawdown_pct=max_dd,
        trades=trades,
    )


def _portfolio_candidate_search(
    universe: List[Tuple[str, np.ndarray]],
    grids: Dict[str, List[dict]],
    *,
    target_return: float = 200.0,
    initial_capital: float = 40.0,
) -> Tuple[BacktestResult | None, List[BacktestResult]]:
    best: BacktestResult | None = None
    results: List[BacktestResult] = []
    aligned = _align_universe(universe)

    def _consider(r: BacktestResult) -> None:
        nonlocal best
        results.append(r)
        if best is None or _score_for_target(r.total_return_pct, target=target_return) > _score_for_target(
            best.total_return_pct, target=target_return
        ):
            best = r

    for strategy, param_sets in grids.items():
        logger.info("sweep strategy=%s candidates=%d", strategy, len(param_sets))
        for params in param_sets:
            try:
                _consider(
                    _evaluate_portfolio_strategy(
                        aligned,
                        strategy,
                        params,
                        target_return=target_return,
                        initial_capital=initial_capital,
                        already_aligned=True,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("portfolio eval failed %s %s: %s", strategy, params, exc)
        if best is not None:
            logger.info(
                "best after %s: return=%.2f%% equity=%.2f",
                strategy,
                best.total_return_pct,
                initial_capital * (1.0 + best.total_return_pct / 100.0),
            )

    if not results:
        return None, results

    # Best params per strategy, then every top-strategy combination.
    best_by_strategy: Dict[str, BacktestResult] = {}
    for r in results:
        prev = best_by_strategy.get(r.strategy)
        if prev is None or r.total_return_pct > prev.total_return_pct:
            best_by_strategy[r.strategy] = r
    top_strats = sorted(best_by_strategy.values(), key=lambda r: r.total_return_pct, reverse=True)
    mix_modes = ["OR", "AND", "VOTE_2_OF_3"]
    # all pairs
    for a, b in combinations(top_strats, 2):
        mix_sig = "+".join(sorted({a.strategy, b.strategy}))
        for mode in mix_modes:
            merged = dict(a.params)
            merged.update({f"{k}__{b.strategy}": v for k, v in b.params.items()})
            try:
                _consider(
                    _evaluate_portfolio_strategy(
                        aligned,
                        a.strategy,
                        merged,
                        mix=f"{mix_sig}:{mode}",
                        target_return=target_return,
                        initial_capital=initial_capital,
                        already_aligned=True,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("portfolio mix eval failed %s: %s", mix_sig, exc)
    # all triples when we have 3+ strategies
    if len(top_strats) >= 3:
        for a, b, c in combinations(top_strats, 3):
            mix_sig = "+".join(sorted({a.strategy, b.strategy, c.strategy}))
            for mode in mix_modes:
                merged = dict(a.params)
                merged.update({f"{k}__{b.strategy}": v for k, v in b.params.items()})
                merged.update({f"{k}__{c.strategy}": v for k, v in c.params.items()})
                try:
                    _consider(
                        _evaluate_portfolio_strategy(
                            aligned,
                            a.strategy,
                            merged,
                            mix=f"{mix_sig}:{mode}",
                            target_return=target_return,
                            initial_capital=initial_capital,
                            already_aligned=True,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("portfolio triple mix eval failed %s: %s", mix_sig, exc)
    # all four together
    if len(top_strats) >= 4:
        mix_sig = "+".join(sorted(r.strategy for r in top_strats[:4]))
        for mode in mix_modes:
            merged: dict = {}
            for r in top_strats[:4]:
                for k, v in r.params.items():
                    merged[f"{k}__{r.strategy}" if merged else k] = v
                    if r is not top_strats[0]:
                        merged[f"{k}__{r.strategy}"] = v
                    else:
                        merged[k] = v
            try:
                _consider(
                    _evaluate_portfolio_strategy(
                        aligned,
                        top_strats[0].strategy,
                        merged,
                        mix=f"{mix_sig}:{mode}",
                        target_return=target_return,
                        initial_capital=initial_capital,
                        already_aligned=True,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("portfolio full mix eval failed %s: %s", mix_sig, exc)
    return best, results


# --- Parameter grids ---


def _p(d: dict) -> List[dict]:
    items = [{}]
    for k, vs in d.items():
        new = []
        for it in items:
            for v in vs:
                new.append({**it, k: v})
        items = new
    return items


def _bounds(center: float, spreads: List[float], kind: str = "linear") -> List[float]:
    vals = []
    for s in spreads:
        if kind == "int":
            vals.append(max(2, int(round(center + s))))
        elif kind == "pct":
            vals.append(max(0.005, center + s))
        else:
            vals.append(center + s)
    return sorted(set(vals))


def default_param_grid(mode: str = "full") -> Dict[str, List[dict]]:
    # Aggressive grids aimed at $40 -> $120 on a concentrated portfolio.
    lev = [5.0, 10.0, 20.0] if mode == "full" else [5.0, 10.0, 20.0]
    if mode == "full":
        return {
            "sma_cross": _p({
                "fast": [5, 10, 20],
                "slow": [30, 50, 80],
                "stop_loss_pct": [0.02, 0.05],
                "take_profit_pct": [0.08, 0.15, 0.25],
                "leverage": lev,
                "max_positions": [3, 5, 10],
            }),
            "rsi_reversion": _p({
                "period": [7, 14],
                "low": [20, 25, 30],
                "high": [70, 75, 80],
                "stop_loss_pct": [0.03, 0.05],
                "take_profit_pct": [0.08, 0.15],
                "leverage": lev,
                "max_positions": [3, 5, 10],
            }),
            "roc_momentum": _p({
                "period": [3, 5, 10],
                "threshold": [0.3, 0.8, 1.5],
                "stop_loss_pct": [0.03, 0.05],
                "take_profit_pct": [0.1, 0.2],
                "leverage": lev,
                "max_positions": [3, 5, 10],
            }),
            "breakout": _p({
                "window": [5, 10, 20],
                "stop_loss_pct": [0.03, 0.05],
                "take_profit_pct": [0.1, 0.2, 0.3],
                "leverage": lev,
                "max_positions": [3, 5, 10],
            }),
        }
    return {
        "sma_cross": _p({
            "fast": [5, 10, 20],
            "slow": [30, 50, 80],
            "stop_loss_pct": [0.03],
            "take_profit_pct": [0.1, 0.2],
            "leverage": [10.0, 20.0],
            "max_positions": [3, 5],
        }),
        "rsi_reversion": _p({
            "period": [7, 14],
            "low": [20, 30],
            "high": [70, 80],
            "stop_loss_pct": [0.03],
            "take_profit_pct": [0.1, 0.2],
            "leverage": [10.0, 20.0],
            "max_positions": [3, 5],
        }),
        "roc_momentum": _p({
            "period": [3, 5, 10],
            "threshold": [0.3, 1.0],
            "stop_loss_pct": [0.03],
            "take_profit_pct": [0.1, 0.2],
            "leverage": [10.0, 20.0],
            "max_positions": [3, 5],
        }),
        "breakout": _p({
            "window": [5, 10, 20],
            "stop_loss_pct": [0.03],
            "take_profit_pct": [0.1, 0.25],
            "leverage": [10.0, 20.0],
            "max_positions": [3, 5],
        }),
    }


def _refine_grid(params: dict) -> List[dict]:
    # Only refine core scalar params (ignore mix-suffixed keys).
    clean = {k: v for k, v in params.items() if "__" not in k and k != "_score"}
    out = [dict(clean)]
    for k, v in clean.items():
        if isinstance(v, bool) or k in {"slow", "high"}:
            continue
        if isinstance(v, int):
            for delta in (-2, -1, 1, 2):
                cand = dict(clean)
                cand[k] = max(1, v + delta)
                out.append(cand)
        elif isinstance(v, float):
            for scale in (0.7, 0.85, 1.15, 1.3):
                cand = dict(clean)
                if k == "leverage":
                    cand[k] = max(1.0, round(v * scale, 2))
                else:
                    cand[k] = max(0.0, round(v * scale, 6))
                out.append(cand)
    seen = set()
    deduped = []
    for cand in out:
        key = tuple(sorted(cand.items()))
        if key not in seen:
            seen.add(key)
            deduped.append(cand)
    return deduped[:40]


# --- Synthetic data ---


def _make_synthetic_candles(seed: int, bars: int = DEFAULT_LIMIT) -> np.ndarray:
    rng = random.Random(seed)
    base = 10 ** rng.randint(1, 4) * rng.uniform(0.8, 1.5)
    prices = [base]
    # Regime-switching path so momentum/breakout/mix strategies have a real edge to discover.
    drift = rng.choice([-0.0004, -0.0001, 0.0002, 0.0006, 0.0010])
    vol = rng.uniform(0.008, 0.02)
    for i in range(bars - 1):
        if i % max(40, bars // 8) == 0:
            drift = rng.choice([-0.0005, -0.0002, 0.0001, 0.0005, 0.0012])
            vol = rng.uniform(0.007, 0.022)
        ret = rng.gauss(drift, vol)
        prices.append(float(prices[-1] * math.exp(ret)))
    return np.array(prices, dtype=float)


def generate_synthetic_universe(n: int, bars: int = DEFAULT_LIMIT) -> List[Tuple[str, np.ndarray]]:
    universe = []
    for i, iid in enumerate(synthetic_universe(n)):
        arr = _make_synthetic_candles(i + 1, bars)
        universe.append((iid, arr))
    return universe


def _http_json(url: str) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    # Prefer Chrome TLS impersonation — Blofin WAF blocks default Python clients on VPN exits.
    try:
        from curl_cffi import requests as curl_requests

        last_err: Exception | None = None
        for imp in ("chrome", "safari17_0", "edge101"):
            try:
                resp = curl_requests.get(url, headers=headers, impersonate=imp, timeout=20)
                if resp.status_code == 403 and "<!DOCTYPE html>" in (resp.text or ""):
                    last_err = RuntimeError(f"HTTP 403 HTML block for {url}")
                    continue
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code} for {url}")
                body = resp.text or ""
                if not body.strip():
                    return []
                return json.loads(body)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
        if last_err:
            raise last_err
    except ImportError:
        pass

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    if not body.strip():
        return []
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid json from {url}: {exc}") from exc


_BLOFIN_PUBLIC_URLS = [
    "https://openapi.blofin.com/api/v1/market/tickers?instType=SWAP",
    "https://openapi.blofin.com/api/v1/market/instruments?instType=SWAP",
    "https://openapi.blofin.com/api/v1/market/tickers?instType=SPOT",
    "https://openapi.blofin.com/api/v1/market/instruments?instType=SPOT",
]


def _instrument_ids_from_raw(raw: Any, prefix: str | None = None) -> List[str]:
    out: List[str] = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("data", raw.get("tickers", []))
    else:
        items = []
    for x in items:
        if not isinstance(x, dict):
            continue
        c = x.get("instId") or x.get("symbol") or x.get("channel") or ""
        if not c:
            continue
        out.append(str(c))
    out = sorted(set(out))
    if prefix:
        out = [c for c in out if c.startswith(prefix)]
    return out


def _fetch_public_candles(inst_id: str, bar: str = DEFAULT_BAR, limit: int = DEFAULT_LIMIT) -> np.ndarray:
    url = f"https://openapi.blofin.com/api/v1/market/candles?instId={inst_id}&bar={bar}&limit={min(limit, 1440)}"
    payload = _http_json(url)
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    candles = _rows_to_candles(rows or [])
    if not candles:
        return np.array([], dtype=float)
    return _array(candles)


def _public_universe_from_blofin(limit_instruments: int | None = None, limit_candles: int = DEFAULT_LIMIT, *, bar: str = DEFAULT_BAR) -> List[Tuple[str, np.ndarray]]:
    candidate_ids: List[str] = []
    for url in _BLOFIN_PUBLIC_URLS:
        try:
            raw = _http_json(url) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("public universe fetch failed %s: %s", url, exc)
            continue
        ids = [
            iid
            for iid in _instrument_ids_from_raw(raw)
            if iid.upper().endswith("-USDT") and "UP-" not in iid and "DOWN-" not in iid
        ]
        if ids:
            candidate_ids = ids
            logger.info("public universe discovered %d USDT instruments via %s", len(ids), url)
            break
    if not candidate_ids:
        return []
    if limit_instruments:
        candidate_ids = candidate_ids[:limit_instruments]
    universe_data: List[Tuple[str, np.ndarray]] = []
    for i, iid in enumerate(candidate_ids):
        try:
            close = _fetch_public_candles(iid, bar=bar, limit=limit_candles)
            if close.size >= 60:
                universe_data.append((iid, close))
        except Exception as exc:  # noqa: BLE001
            logger.debug("public candle fetch failed %s: %s", iid, exc)
        if (i + 1) % 25 == 0:
            logger.info("public candle progress %d/%d loaded=%d", i + 1, len(candidate_ids), len(universe_data))
            time.sleep(0.2)
        else:
            time.sleep(0.05)
    universe_data.sort(key=lambda x: x[0])
    return universe_data


def load_public_universe(limit_instruments: int | None = None, limit_candles: int = DEFAULT_LIMIT, *, bar: str = DEFAULT_BAR) -> List[Tuple[str, np.ndarray]]:
    try:
        data = _public_universe_from_blofin(limit_instruments=limit_instruments, limit_candles=limit_candles, bar=bar)
        if data:
            return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("blofin public universe failed: %s", exc)
    # Fallback: full synthetic Blofin-sized universe when live public endpoints are blocked.
    n = limit_instruments or 486
    logger.warning("falling back to synthetic universe n=%d (public endpoints unavailable)", n)
    return generate_synthetic_universe(n, limit_candles)


# --- Runner ---


def _sweep_singles(close: np.ndarray, grids: Dict[str, List[dict]]) -> List[BacktestResult]:
    results: List[BacktestResult] = []
    for strategy, param_sets in grids.items():
        for params in param_sets:
            try:
                r = _evaluate(close, strategy, params)
                results.append(r)
            except Exception as exc:  # noqa: BLE001
                logger.debug("evaluation failed %s %s: %s", strategy, params, exc)
    return results


def _sweep_mixes(
    close: np.ndarray,
    single_best: List[BacktestResult],
    grids: Dict[str, List[dict]],
) -> List[BacktestResult]:
    if len(single_best) < 2:
        return []
    top = sorted(single_best, key=lambda r: r.total_return_pct, reverse=True)[: max(2, min(6, len(single_best)))]
    results: List[BacktestResult] = []
    mix_modes = ["OR", "AND", "VOTE_2_OF_3"]
    for s1, s2 in combinations([r.strategy for r in top], 2):
        mix_sig = "+".join(sorted({s1, s2}))
        for mode in mix_modes:
            for p1 in grids[s1][:8]:
                for p2 in grids[s2][:8]:
                    merged = dict(p1)
                    merged.update({f"{k}__{s2}": v for k, v in p2.items()})
                    try:
                        r = _evaluate(close, s1, merged, mix=f"{mix_sig}:{mode}")
                        results.append(r)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("mix eval failed %s + %s %s: %s", s1, s2, mode, exc)
    return results


def _best_of(results: List[BacktestResult]) -> BacktestResult:
    if not results:
        raise ValueError("empty results")
    return max(results, key=lambda r: r.total_return_pct)


def run_instrument(client: BlofinClient, inst_id: str, grids: Dict[str, List[dict]], limit: int = DEFAULT_LIMIT) -> BacktestResult:
    rows = client.get_candles(inst_id, bar=DEFAULT_BAR, limit=limit)
    candles = _rows_to_candles(rows)
    if not candles or len(candles) < 60:
        return BacktestResult(inst_id, "", "", {}, -1e9, -1e9, 100.0, 0)
    close = _array(candles)
    single = _sweep_singles(close, grids)
    if not single:
        return BacktestResult(inst_id, "", "", {}, -1e9, -1e9, 100.0, 0)
    mixes = _sweep_mixes(close, single, grids)
    all_results = single + mixes
    best = _best_of(all_results)
    return BacktestResult(
        inst_id,
        best.strategy,
        best.mix,
        best.params,
        best.total_return_pct,
        best.sharpe_like,
        best.max_drawdown_pct,
        best.trades,
    )


# --- IO ---


def write_csv(results: List[BacktestResult], path: Path) -> None:
    fieldnames = [
        "inst_id", "strategy", "mix", "total_return_pct", "sharpe_like", "max_drawdown_pct", "trades"
    ] + sorted({rk: None for r in results for rk in r.params.keys()}.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "inst_id": r.inst_id,
                "strategy": r.strategy,
                "mix": r.mix,
                "total_return_pct": f"{r.total_return_pct:.4f}",
                "sharpe_like": f"{r.sharpe_like:.4f}",
                "max_drawdown_pct": f"{r.max_drawdown_pct:.4f}",
                "trades": r.trades,
            }
            for k, v in r.params.items():
                row[k] = v
            writer.writerow(row)


def write_best(best: BacktestResult, path: Path) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inst_id": best.inst_id,
        "strategy": best.strategy,
        "mix": best.mix,
        "total_return_pct": best.total_return_pct,
        "sharpe_like": best.sharpe_like,
        "max_drawdown_pct": best.max_drawdown_pct,
        "trades": best.trades,
        "params": best.params,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# --- Args ---


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hermes backtest + strategy mix optimizer")
    p.add_argument("--mode", choices=["quick", "full"], default="full")
    p.add_argument("--bar", default=DEFAULT_BAR)
    p.add_argument("--limit-instruments", type=int, default=None)
    p.add_argument("--limit-candles", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--universe", default=None, help="comma-separated instrument ids")
    p.add_argument("--out-dir", default=".")
    p.add_argument("--cache", default=None, help="load universe from universe_cache.npz instead of API")
    p.add_argument("--retrain-rounds", type=int, default=8)
    p.add_argument("--synthetic", action="store_true", help="use synthetic data instead of Blofin API")
    p.add_argument("--synthetic-instruments", type=int, default=486)
    p.add_argument("--public", action="store_true", help="use public live historical data without API credentials")
    return p.parse_args(argv)


# --- Main ---


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if getattr(args, "cache", None):
        cache_path = Path(args.cache)
        logger.info("loading universe cache %s", cache_path)
        blob = np.load(cache_path, allow_pickle=True)
        ids = list(blob["ids"])
        closes = blob["closes"]
        universe_data = [(str(ids[i]), closes[i].astype(float)) for i in range(len(ids))]
    elif args.synthetic:
        logger.info("synthetic mode with %d instruments", args.synthetic_instruments)
        universe_data = generate_synthetic_universe(args.synthetic_instruments, args.limit_candles)
    elif getattr(args, "public", False):
        logger.info("public live historical mode")
        universe_data = load_public_universe(
            limit_instruments=args.limit_instruments,
            limit_candles=args.limit_candles,
            bar=args.bar,
        )
    else:
        key = os.getenv("BLOFIN_API_KEY") or os.getenv("BLOFIN_KEY")
        secret = os.getenv("BLOFIN_API_SECRET") or os.getenv("BLOFIN_SECRET")
        passphrase = os.getenv("BLOFIN_PASSPHRASE") or os.getenv("BLOFIN_PASSWORD") or ""
        if not key or not secret:
            logger.error("missing Blofin API keys. Copy .env.example to .env and fill it, or rerun with --synthetic or --public.")
            return 2
        client = BlofinClient(api_key=key, api_secret=secret, passphrase=passphrase)
        if args.universe:
            universe = [x.strip() for x in args.universe.split(",") if x.strip()]
        else:
            universe = load_universe(client)
        universe_data = []
        for i, iid in enumerate(universe):
            try:
                rows = client.get_candles(iid, bar=args.bar, limit=args.limit_candles)
                # Client may return list[list] or list[dict]; normalize to rows.
                if rows and isinstance(rows[0], dict):
                    rows = [[r.get("ts"), r.get("o") or r.get("open"), r.get("h") or r.get("high"), r.get("l") or r.get("low"), r.get("c") or r.get("close"), r.get("vol") or r.get("volume") or 0] for r in rows]
                candles = _rows_to_candles(rows)
                if candles:
                    universe_data.append((iid, _array(candles)))
            except Exception as exc:  # noqa: BLE001
                logger.debug("candle fetch failed %s: %s", iid, exc)
            if (i + 1) % 25 == 0 or (i + 1) == len(universe):
                logger.info(
                    "live candle progress %d/%d loaded=%d",
                    i + 1,
                    len(universe),
                    len(universe_data),
                )
            time.sleep(0.08)
        if args.limit_instruments:
            universe_data = universe_data[: args.limit_instruments]

    if not universe_data:
        logger.error("empty instrument dataset")
        return 3

    logger.info("dataset size=%d mode=%s", len(universe_data), args.mode)
    # Persist live dataset so retrain loops can restart without re-fetching.
    # Drop short listings instead of truncating the whole universe to the shortest series
    # (that previously collapsed a 720-bar month window down to ~121 bars).
    try:
        cache_path = out_dir / "universe_cache.npz"
        min_bars = max(60, int(args.limit_candles))
        before = len(universe_data)
        universe_data = _align_universe(universe_data, min_bars=min_bars)
        ids = np.array([iid for iid, _ in universe_data], dtype=object)
        closes = np.stack([arr for _, arr in universe_data], axis=0)
        np.savez_compressed(cache_path, ids=ids, closes=closes)
        logger.info(
            "cached universe to %s assets=%d bars=%d dropped_short=%d min_bars=%d",
            cache_path,
            len(ids),
            closes.shape[1] if closes.ndim == 2 else 0,
            before - len(ids),
            min_bars,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("universe cache failed: %s", exc)
    target = 200.0
    initial_capital = 40.0
    evaluated: List[BacktestResult] = []
    top: BacktestResult | None = None
    for rnd in range(max(1, int(args.retrain_rounds))):
        logger.info("portfolio optimization pass %d/%d", rnd + 1, max(1, int(args.retrain_rounds)))
        grids = default_param_grid(args.mode)
        if evaluated:
            best_by_strategy: Dict[str, dict] = {}
            for res in evaluated:
                if not res.strategy or res.mix:
                    continue
                prev = best_by_strategy.get(res.strategy)
                score = _score_for_target(res.total_return_pct, target=target)
                if prev is None or score > _score_for_target(float(prev.get("_score", -1e18)), target=target):
                    cand = {k: v for k, v in res.params.items() if "__" not in k}
                    cand["_score"] = score
                    best_by_strategy[res.strategy] = cand
            if best_by_strategy:
                refined: Dict[str, List[dict]] = {}
                for s in grids:
                    if s in best_by_strategy:
                        refined[s] = _refine_grid(best_by_strategy[s])
                    else:
                        refined[s] = grids[s]
                grids = refined
                logger.info(
                    "refined grids: %s",
                    {s: len(v) for s, v in grids.items()},
                )
        top, pass_results = _portfolio_candidate_search(
            universe_data,
            grids,
            target_return=target,
            initial_capital=initial_capital,
        )
        evaluated.extend(pass_results)
        if top is None:
            continue
        logger.info(
            "pass %d portfolio equity=%.2f target=%.2f return=%.2f%% strategy=%s mix=%s",
            rnd + 1,
            initial_capital * (1.0 + top.total_return_pct / 100.0),
            initial_capital * (1.0 + target / 100.0),
            top.total_return_pct,
            top.strategy,
            top.mix,
        )
        if top.total_return_pct >= target - 1e-9:
            break

    if not evaluated:
        logger.error("no backtest results")
        return 4
    ranked = sorted(evaluated, key=lambda r: r.total_return_pct, reverse=True)
    best = ranked[0]
    if top is not None and top.total_return_pct > best.total_return_pct:
        best = top
    write_csv(ranked, out_dir / BENCHMARK)
    write_best(best, out_dir / BEST_FILE)
    summary = {
        "best_inst_id": best.inst_id,
        "strategy": best.strategy,
        "mix": best.mix,
        "total_return_pct": best.total_return_pct,
        "sharpe_like": best.sharpe_like,
        "max_drawdown_pct": best.max_drawdown_pct,
        "trades": best.trades,
        "target_return_pct": target,
        "initial_capital": initial_capital,
        "target_capital": initial_capital * (1.0 + target / 100.0),
        "portfolio_mode": True,
        "params": best.params,
        "benchmark_csv": str(out_dir / BENCHMARK),
        "best_json": str(out_dir / BEST_FILE),
        "ranked": [
            {
                "inst_id": r.inst_id,
                "strategy": r.strategy,
                "mix": r.mix,
                "total_return_pct": r.total_return_pct,
                "sharpe_like": r.sharpe_like,
                "max_drawdown_pct": r.max_drawdown_pct,
                "trades": r.trades,
                "params": r.params,
            }
            for r in ranked[:20]
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
