"""The 1-minute wake -> think -> act -> sleep loop.

Each tick:
1. Pull market + account state.
2. Build the prompt.
3. Call LLM. On timeout/429, log and skip — do not place any order.
4. Parse + validate the LLM output.
5. (Future) apply risk controls — currently a no-op via risk_none.
6. Execute decisions sequentially.
7. Maybe trigger summary refresh.
8. Log a one-line cycle summary.

Graceful shutdown: Ctrl+C (SIGINT) or SIGTERM finishes the in-flight tick
and exits 0. APScheduler's job is registered with `coalesce=True` so a
backlog of missed ticks won't fire a burst on resume.
"""
from __future__ import annotations

import json
import logging
import random
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from rich.console import Console
from rich.logging import RichHandler

from . import risk_none as risk
from .blofin_client import BlofinAPIError, BlofinClient
from .config import AppConfig, Secrets
from .decision import CycleDecision, parse
from .demo_fallback import demo_fallback_decisions
from .executor import execute_decisions
from .journal import Journal
from .market_data import build_snapshot, fetch_universe
from .nous_client import LLMUnavailable, NousClient
from .paper_broker import PaperBroker
from .playbook import format_playbook, load_backtest_best, merge_summary_with_playbook, seed_journal_playbook
from .strategy_prompt import SYSTEM, build_user_prompt

logger = logging.getLogger(__name__)
console = Console()


class HermesLoop:
    def __init__(self, secrets: Secrets, config: AppConfig):
        self.config = config
        self.secrets = secrets
        self.tick_num = 0
        self.session_start_equity: float | None = None
        self.demo = str(config.trading_mode).lower() == "demo"

        self.blofin = BlofinClient(
            api_key=secrets.blofin_api_key,
            api_secret=secrets.blofin_api_secret,
            passphrase=secrets.blofin_passphrase,
            broker_id=getattr(secrets, "blofin_broker_id", "") or "",
        )
        self.llm = NousClient(
            api_key=secrets.nous_portal_key,
            model=config.llm.model,
            base_url=config.llm.base_url,
            timeout_seconds=config.llm.timeout_seconds,
            reasoning_effort=config.llm.reasoning_effort,
            max_output_tokens=config.llm.max_output_tokens,
        )
        # Demo uses a separate journal so live history is not polluted.
        journal_path = config.journal.db_path
        if self.demo and "demo" not in str(journal_path).lower():
            journal_path = "./data/demo_journal.sqlite"
        self.journal = Journal(journal_path)

        self.paper: PaperBroker | None = None
        if self.demo:
            self.paper = PaperBroker(
                config.paper.state_path,
                starting_equity=float(config.paper.starting_equity),
                reset=bool(config.paper.reset_on_start),
            )

        # Universe is loaded at startup. Re-loaded hourly to catch new listings.
        self.instruments: dict = {}
        self._last_universe_sync: float = 0.0

    # --- lifecycle -------------------------------------------------------- #

    def startup(self) -> None:
        mode = "DEMO paper" if self.demo else "LIVE"
        logger.info("starting Hermes in %s mode", mode)
        logger.info("loading instrument universe from Blofin...")
        self.instruments = fetch_universe(self.blofin)
        self._last_universe_sync = time.time()
        logger.info("loaded %d USDT perps", len(self.instruments))
        if not self.instruments:
            raise RuntimeError("No USDT perps returned by Blofin. Check API key & permissions.")

        # Capture session-start equity for drawdown display.
        try:
            snap = self._build_tick_snapshot(top_n=min(20, int(self.config.paper.top_n if self.demo else 20)))
            self.session_start_equity = snap.account.equity
            if self.paper:
                self.paper.update_marks(snap.tickers, tick=0, universe_count=len(self.instruments))
        except Exception:  # noqa: BLE001
            logger.exception("could not fetch initial account/market state")
            if self.demo and self.paper:
                self.session_start_equity = float(self.config.paper.starting_equity)

        # Seed offline backtest winner into journal memory (persistent learning prior).
        try:
            if seed_journal_playbook(self.journal):
                logger.info("optimized playbook loaded into agent journal memory")
        except Exception:  # noqa: BLE001
            logger.exception("failed to seed optimized playbook into journal")

        if self.demo:
            console.print(
                f"[bold cyan]DEMO mode[/bold cyan]: ${self.config.paper.starting_equity:.2f} paper account, "
                f"{len(self.instruments)} Blofin USDT perps, no live orders."
            )

    def _build_tick_snapshot(self, *, top_n: int):
        if self.demo and self.paper is not None:
            return build_snapshot(
                self.blofin,
                self.instruments,
                top_n=top_n,
                account=self.paper.account_snapshot(),
                positions=self.paper.position_snapshots(),
                open_orders=[],
            )
        return build_snapshot(self.blofin, self.instruments, top_n=top_n)

    def refresh_universe_if_due(self) -> None:
        if time.time() - self._last_universe_sync > 3600:
            try:
                self.instruments = fetch_universe(self.blofin)
                self._last_universe_sync = time.time()
                logger.info("refreshed universe: %d USDT perps", len(self.instruments))
            except Exception:  # noqa: BLE001
                logger.exception("universe refresh failed; keeping previous list")

    # --- the tick --------------------------------------------------------- #

    def run_one_tick(self) -> None:
        """One decision cycle. Never raises — a crash here must not kill the process."""
        self.tick_num += 1
        tick = self.tick_num
        t0 = time.time()
        logger.info("tick=%d start", tick)
        try:
            self._run_one_tick_inner(tick, t0)
        except Exception:  # noqa: BLE001
            logger.exception("tick=%d crashed; continuing scheduler", tick)

    def _run_one_tick_inner(self, tick: int, t0: float) -> None:
        self.refresh_universe_if_due()

        raw_reason: str | None = None
        raw: str | None = None
        decision = CycleDecision.empty("prompt_build_skipped")
        snapshot = None

        # 1. Market snapshot (full Blofin USDT universe tickers; candles for top_n)
        try:
            top_n = int(self.config.paper.top_n) if self.demo else 20
            snapshot = self._build_tick_snapshot(top_n=top_n)
            if self.paper is not None:
                self.paper.update_marks(
                    snapshot.tickers,
                    tick=tick,
                    universe_count=len(self.instruments),
                )
                # Refresh account/positions after marks for the prompt.
                snapshot = self._build_tick_snapshot(top_n=top_n)
        except BlofinAPIError as e:
            raw_reason = f"snapshot_failed: {e}"
            logger.warning("market snapshot failed: %s", e)
        except Exception:  # noqa: BLE001
            raw_reason = "snapshot_crashed"
            logger.exception("snapshot crashed")

        if raw_reason is None:
            # 2. Build prompt
            try:
                user_prompt = build_user_prompt(
                    snapshot, self.journal,
                    verbatim_n=self.config.journal.verbatim_window,
                    tick_num=tick,
                )
                if self.demo:
                    user_prompt = (
                        "## DEMO MODE\n"
                        f"You are trading a simulated ${self.config.paper.starting_equity:.2f} USDT account "
                        f"across all {len(self.instruments)} Blofin USDT perps. No live orders are placed. "
                        "Trade as if real: concentrated book, playbook-first, respect cash/margin.\n\n"
                        + user_prompt
                    )
            except Exception:  # noqa: BLE001
                raw_reason = "prompt_build_crashed"
                logger.exception("prompt build crashed")

        if raw_reason is None:
            # 3. LLM call
            t_llm = time.time()
            try:
                raw = self.llm.decide(SYSTEM, user_prompt)
            except LLMUnavailable as e:
                raw_reason = f"llm_unavailable: {e}"
                logger.warning("LLM unavailable, skipping tick: %s", e)
            except Exception:  # noqa: BLE001
                raw_reason = "llm_crashed"
                logger.exception("LLM call crashed")
            llm_ms = int((time.time() - t_llm) * 1000)
        else:
            llm_ms = 0

        if raw_reason is not None:
            eq = None
            try:
                eq = float(self.paper.equity()) if self.paper is not None else float(snapshot.account.equity)
            except Exception:
                eq = None
            self._log_summary(
                tick,
                llm_ms=llm_ms,
                decision=CycleDecision.empty(raw_reason),
                outcomes=[],
                equity=eq,
            )
            return

        # 4. Parse + validate
        decision = parse(raw, snapshot)
        decision = risk.apply(decision, snapshot)  # currently a no-op

        # If the LLM produced no actionable JSON, use playbook momentum fallback
        # (same stop-based sizing). Demo always; live when book is flat so the
        # stack actually trades instead of idling on empty responses.
        if not decision.decisions:
            open_n = (
                len(self.paper.position_snapshots())
                if self.paper is not None
                else len(snapshot.positions)
            )
            if self.demo or open_n == 0:
                try:
                    fb = demo_fallback_decisions(snapshot, self.paper)
                    if fb.decisions:
                        logger.info(
                            "%s fallback producing %d decisions",
                            "demo" if self.demo else "live",
                            len(fb.decisions),
                        )
                        decision = fb
                except Exception:  # noqa: BLE001
                    logger.exception("fallback crashed; continuing with LLM decision")

        # Force stop-based playbook sizing on opens (never all-in cash/slots).
        if decision.decisions:
            try:
                from .sizing import apply_playbook_sizing, load_playbook_risk

                pb = load_playbook_risk()
                cash = float(self.paper.state.cash) if self.paper is not None else float(snapshot.account.available)
                equity = float(self.paper.equity()) if self.paper is not None else float(snapshot.account.equity)
                open_n = len(self.paper.position_snapshots()) if self.paper is not None else len(snapshot.positions)
                margin_used = float(self.paper.margin_used()) if self.paper is not None else float(snapshot.account.margin_used)
                sized = apply_playbook_sizing(
                    decision.decisions,
                    snapshot=snapshot,
                    cash=cash,
                    equity=equity,
                    open_count=open_n,
                    margin_already_used=margin_used,
                    risk=pb,
                )
                if len(sized) != len(decision.decisions):
                    logger.info(
                        "playbook sizing applied: %d -> %d decision(s) (lev=%dx max_pos=%d risk=%.1f%%)",
                        len(decision.decisions),
                        len(sized),
                        pb.leverage,
                        pb.max_positions,
                        pb.risk_per_trade_pct * 100,
                    )
                decision = decision.model_copy(update={"decisions": sized})
            except Exception:  # noqa: BLE001
                logger.exception("playbook sizing failed; using raw decisions")

        # 5. Execute (paper broker in demo — never hits live trade endpoints)
        outcomes: list[dict] = []
        if decision.decisions:
            exec_client = self.paper if (self.demo and self.paper is not None) else self.blofin
            outcomes = execute_decisions(
                decision.decisions,
                tick=tick,
                client=exec_client,
                journal=self.journal,
                td_mode=self.config.mode,
                decision_raw=raw,
                demo=self.demo,
            )
            if self.paper is not None:
                self.paper.update_marks(snapshot.tickers, tick=tick, universe_count=len(self.instruments))
        else:
            # No-trade cycle. Record a heartbeat trade row so the journal
            # reflects the decision-making activity (no P&L, no action).
            self.journal.add_trade(
                tick=tick,
                inst_id="(no_trade)",
                side="hold",
                action="hold",
                sz="0",
                px=None,
                leverage=None,
                rationale=(decision.thesis or "")[:500] or decision.no_trade_reason or "no_trade",
                decision_raw=raw,
            )

        # 6. Summary refresh?
        if self.journal.should_refresh_summary_tick(self.tick_num, every_n=self.config.journal.summary_refresh_every_ticks):
            self._refresh_summary(snapshot)

        self._log_summary(
            tick,
            llm_ms=llm_ms,
            decision=decision,
            outcomes=outcomes,
            equity=(
                float(self.paper.equity())
                if self.paper is not None
                else (float(snapshot.account.equity) if snapshot is not None else None)
            ),
        )
        # Persist a tiny live snapshot for the dashboard last_tick / equity.
        if not self.demo and snapshot is not None:
            try:
                path = Path("data/live_state.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "mode": "live",
                            "equity": snapshot.account.equity,
                            "available": snapshot.account.available,
                            "margin_used": snapshot.account.margin_used,
                            "unrealized_pnl": snapshot.account.unrealized_pnl,
                            "last_tick": tick,
                            "updated_at": time.time(),
                            "open_positions": len(snapshot.positions),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
        logger.info("tick=%d total=%.1fs", tick, time.time() - t0)

    def _log_summary(
        self,
        tick: int,
        llm_ms: int,
        decision: CycleDecision,
        outcomes: list[dict],
        equity: float | None = None,
    ) -> None:
        pnl_today = self.journal.pnl_today()
        fills = sum(1 for o in outcomes if o.get("status") == "submitted")
        rejections = sum(1 for o in outcomes if o.get("status") in ("rejected", "error"))
        reason = decision.no_trade_reason or (decision.decisions[0].rationale if decision.decisions else "")
        # ASCII-only for Windows consoles (cp1252) — never crash the tick on glyphs.
        reason_safe = (reason or "").encode("ascii", "replace").decode("ascii")
        if equity is None and self.paper is not None:
            equity = self.paper.equity()
        eq_txt = f" equity={equity:.2f}" if equity is not None else ""
        mode = "demo" if self.demo else "live"
        console.print(
            f"[cyan]tick={tick}[/cyan]  mode={mode}  llm_ms={llm_ms}  "
            f"decisions={len(decision.decisions)}  fills={fills}  rejected={rejections}  "
            f"pnl_today={pnl_today:+.2f}USDT{eq_txt}  reason={reason_safe!r}"
        )
        logger.info(
            "tick=%d mode=%s equity=%s fills=%d rejected=%d pnl_today=%+.4f",
            tick, mode, f"{equity:.4f}" if equity is not None else "n/a", fills, rejections, pnl_today,
        )

    # --- summary refresh -------------------------------------------------- #

    def _refresh_summary(self, snapshot) -> None:
        """Every N ticks, ask the LLM to compress the older half of the
        journal into a short paragraph the prompt can carry cheaply.
        """
        trades = self.journal.get_verbatim(self.config.journal.verbatim_window * 4)
        if len(trades) <= self.config.journal.verbatim_window:
            return  # not enough history to need a summary
        older = trades[: -self.config.journal.verbatim_window]
        serialized = "\n".join(
            f"#{t.id} {t.instId} {t.side} {t.action} sz={t.sz} "
            f"px={t.px or '?'} lev={t.leverage or '?'} "
            f"pnl={t.pnl_usdt if t.pnl_usdt is not None else 'open'} "
            f"| {t.rationale or ''}"
            for t in older
        )
        prompt = (
            "You are Hermes. Below are your older trades (the ones you no "
            "longer see verbatim in your prompt). Compress them into a "
            "short paragraph (max 250 words) highlighting: what patterns "
            "worked, what didn't, what market regimes hurt you, and any "
            "self-corrections you want to remember. Plain prose, no JSON, "
            "no lists. Future-you will read this when deciding what to do.\n\n"
            f"{serialized}"
        )
        try:
            summary = self.llm.cheap_call(prompt)
            playbook = format_playbook(load_backtest_best())
            self.journal.set_summary(merge_summary_with_playbook(summary, playbook))
            logger.info("summary refreshed (%d chars)", len(self.journal.get_summary()))
        except LLMUnavailable as e:
            logger.warning("summary refresh failed: %s", e)
        except Exception:  # noqa: BLE001
            logger.exception("summary refresh crashed")

    # --- scheduler -------------------------------------------------------- #

    def run_forever(self) -> None:
        scheduler = BlockingScheduler()
        interval = self.config.loop.interval_seconds
        jitter = self.config.loop.jitter_seconds

        def _job():
            self.run_one_tick()
            # Sleep the jitter INSIDE the job so the scheduler interval stays
            # constant but our actual cadence is jittered. This avoids the
            # scheduler drifting if a tick takes longer than the interval.
            if jitter > 0:
                time.sleep(random.uniform(0, max(0.0, float(jitter))))

        # Fire one tick immediately, then on interval. Passing next_run_time=None
        # pauses the job on some APScheduler versions.
        self.run_one_tick()
        scheduler.add_job(
            _job,
            trigger="interval",
            seconds=max(1, int(interval)),
            coalesce=True,        # if we fall behind, fire once on resume
            max_instances=1,      # never two ticks at once
        )

        def _shutdown(signum, frame):
            console.print("[yellow]shutting down...[/yellow]")
            try:
                scheduler.shutdown(wait=True)
            finally:
                console.print("[green]Hermes sleeping.[/green]")
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _shutdown)

        mode = "DEMO" if self.demo else "LIVE"
        console.print(
            f"[bold green]Hermes is awake ({mode}). Interval: {interval}s (+/- {jitter}s).[/bold green]"
        )
        scheduler.start()
