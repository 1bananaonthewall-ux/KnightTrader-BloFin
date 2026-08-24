from __future__ import annotations

import json
import math
import random
import signal
import time
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler

from .blofin_client import BlofinClient
from .config import settings
from .decision import CycleDecision, parse_decision
from .journal import AxiomJournal, Trade
from .llm_client import AxiomLLM
from .market_data import AxiomMarketData
from .paper_broker import PaperBroker
from .playbook import AxiomPlaybook
from .sizing import compute_size


class AxiomLoop:
    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or settings.mode
        self.blofin = BlofinClient()
        self.llm = AxiomLLM()
        self.market = AxiomMarketData(self.blofin)
        self.journal = AxiomJournal()
        self.playbook = AxiomPlaybook(self.journal, self.llm)
        self.broker = PaperBroker()
        self.tick_num = self.journal.last_tick() + 1
        self.running = True
        self.last_decision_raw: str | None = None
        self.current_snapshot: Any = None
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        self.running = False

    def start(self, interval_seconds: int | None = None, jitter_seconds: int | None = None) -> None:
        interval = interval_seconds or settings.loop.interval_seconds
        jitter = jitter_seconds or settings.loop.jitter_seconds
        scheduler = BlockingScheduler()
        scheduler.add_job(self.run_one_tick, "interval", seconds=interval, jitter=jitter, next_run_time=datetime.now(timezone.utc))
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.blofin.close()

    def run_one_tick(self) -> None:
        if not self.running:
            return
        tick = self.tick_num
        self.tick_num += 1
        try:
            snap = self.market.snapshot(top_n=20)
            self.current_snapshot = snap
            account_text = self.market.formatted_account()
            open_positions_text = self.market.formatted_open_positions()
            top20_table = self.market.formatted_top20_table()
            recent_candles_text = self._format_recent_candles(snap)
            recent_trades_text = self._format_recent_trades()
            summary_text = self.playbook.summary()
            lot_sizes_text = self._format_lot_sizes(snap)
            user_prompt = self._build_prompt(
                tick=tick,
                account_text=account_text,
                open_positions_text=open_positions_text,
                top20_table=top20_table,
                lot_sizes_text=lot_sizes_text,
                recent_candles_text=recent_candles_text,
                recent_trades_text=recent_trades_text,
                summary_text=summary_text,
            )
            raw = self.llm.chat_completion_text(settings.model.model, user_prompt)
            self.last_decision_raw = raw
            decision = parse_decision(raw)
            self.playbook.maybe_refresh(tick)
            self._execute_decisions(decision, snap)
            self.journal.append_heartbeat(tick, raw if decision.is_empty else None)
            if decision.is_empty:
                self._momentum_fallback(snap)
        except Exception as exc:
            self.journal.append_heartbeat(tick, f"tick_error: {exc}")
        finally:
            if self.tick_num % settings.journal.summary_refresh_ticks == 0:
                self.playbook.maybe_refresh(self.tick_num)

    def _execute_decisions(self, decision: CycleDecision, snap: Any) -> None:
        for d in decision.decisions:
            try:
                inst = snap.instruments.get(d.instId)
                if not inst:
                    continue
                price = self._decision_price(d, snap)
                if price is None or price <= 0:
                    continue
                sizing = compute_size(inst, price=price, side=d.side, leverage=d.leverage, equity=float(snap.balances[0].eq) if snap.balances else 0.0)
                sz = sizing.sz
                stop = d.stopLoss or sizing.stop_loss
                tp = d.takeProfit or sizing.take_profit
                payload: dict[str, Any] = {
                    "instId": d.instId,
                    "side": d.side,
                    "orderType": d.orderType,
                    "sz": sz,
                    "leverage": d.leverage,
                    "tdMode": "isolated",
                    "tgtCcy": "USDT",
                }
                if d.orderType == "limit":
                    payload["px"] = d.px
                if stop:
                    payload["slOrdPx"] = stop
                    payload["slTriggerPx"] = stop
                if tp:
                    payload["tpOrdPx"] = tp
                    payload["tpTriggerPx"] = tp
                if self.mode == "live":
                    resp = self.blofin.place_order(payload)
                else:
                    resp = self.broker.place_order(payload)
                trade = Trade(
                    tick=self.tick_num,
                    instId=d.instId,
                    side=d.side,
                    action=d.action,
                    sz=sz,
                    px=d.px or str(price),
                    leverage=d.leverage,
                    rationale=d.rationale,
                    decision_raw=json.dumps(d.model_dump(), ensure_ascii=False) if hasattr(d, "model_dump") else str(d),
                )
                trade_id = self.journal.append_trade(trade)
                if d.action in {"open", "add"}:
                    self.journal.add_open_lots(trade_id, [
                        type("L", (), {"instId": d.instId, "side": d.side, "sz": sz, "entry_px": str(price), "ts": datetime.now(timezone.utc), "trade_id": trade_id})()
                    ])
            except Exception:
                continue

    def _momentum_fallback(self, snap: Any) -> None:
        candidates = [t for t in snap.top20_tickers if getattr(t, "instId", "")]
        if not candidates:
            return
        best = max(candidates, key=lambda x: float(getattr(x, "quoteVolume", 0) or 0))
        try:
            inst = snap.instruments.get(best.instId)
            if not inst:
                return
            price = float(best.last or 0)
            if price <= 0:
                return
            equity = float(snap.balances[0].eq) if snap.balances else 0.0
            sizing = compute_size(inst, price=price, side="buy", equity=equity)
            if float(sizing.sz) <= 0:
                return
            payload = {
                "instId": best.instId,
                "side": "buy",
                "orderType": "market",
                "sz": sizing.sz,
                "leverage": settings.risk.leverage,
                "tdMode": "isolated",
                "tgtCcy": "USDT",
            }
            if sizing.stop_loss:
                payload.update({"slOrdPx": sizing.stop_loss, "slTriggerPx": sizing.stop_loss})
            if sizing.take_profit:
                payload.update({"tpOrdPx": sizing.take_profit, "tpTriggerPx": sizing.take_profit})
            if self.mode == "live":
                self.blofin.place_order(payload)
            else:
                self.broker.place_order(payload)
            trade = Trade(tick=self.tick_num, instId=best.instId, side="buy", action="open", sz=sizing.sz, px=str(price), leverage=settings.risk.leverage, rationale="momentum_fallback")
            trade_id = self.journal.append_trade(trade)
            self.journal.add_open_lots(trade_id, [
                type("L", (), {"instId": best.instId, "side": "buy", "sz": sizing.sz, "entry_px": str(price), "ts": datetime.now(timezone.utc), "trade_id": trade_id})()
            ])
        except Exception:
            pass

    def _format_recent_candles(self, snap: Any) -> str:
        lines: list[str] = []
        for t in snap.top20_tickers:
            candles = snap.top20_candles.get(t.instId, [])
            if not candles:
                continue
            oldest = candles[0]
            newest = candles[-1]
            lines.append(f"{t.instId}: {oldest.ts}:{oldest.o},{oldest.h},{oldest.l},{oldest.c},{oldest.vol} -> {newest.ts}:{newest.o},{newest.h},{newest.l},{newest.c},{newest.vol}")
        return "\n".join(lines) if lines else "No recent candle data."

    def _format_recent_trades(self) -> str:
        trades = self.journal.recent_trades(30)
        return "\n".join(
            f"#{t.id} t={t.tick} {t.instId} {t.side} {t.action} sz={t.sz} px={t.px} lev={t.leverage} pnl={t.pnl_usdt} | {t.rationale}"
            for t in trades
        )

    def _format_lot_sizes(self, snap: Any) -> str:
        lines: list[str] = []
        for t in snap.top20_tickers:
            inst = snap.instruments.get(t.instId)
            if not inst:
                continue
            lines.append(f"{t.instId}: lotSz={getattr(inst, 'lot_sz', '1')} minSz={getattr(inst, 'min_sz', '1')}")
        return "\n".join(lines) if lines else "No instrument lot size data."

    def _build_prompt(self, **kwargs: Any) -> str:
        return (
            f"=== TICK {kwargs['tick']} ===\n"
            f"## Account: {kwargs['account_text']}\n"
            f"## Open positions:\n{kwargs['open_positions_text']}\n"
            f"## Top 20 market:\n{kwargs['top20_table']}\n"
            f"## Instrument lot sizes:\n{kwargs['lot_sizes_text']}\n"
            f"## Recent 1m candles:\n{kwargs['recent_candles_text']}\n"
            f"## Your last 30 trades:\n{kwargs['recent_trades_text']}\n"
            f"## Summary:\n{kwargs['summary_text']}\n"
            "## Your move: Call to action enforcing raw JSON output.\n"
        )

    def _decision_price(self, decision: Any, snap: Any) -> float | None:
        if decision.orderType == "market":
            try:
                ticker = next(t for t in snap.top20_tickers if getattr(t, "instId", "") == decision.instId)
                return float(ticker.last or 0)
            except StopIteration:
                return None
        try:
            return float(decision.px)
        except (TypeError, ValueError):
            return None
