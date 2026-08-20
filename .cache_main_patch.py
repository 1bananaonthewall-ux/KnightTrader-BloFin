def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        logger.info("synthetic mode with %d instruments", args.synthetic_instruments)
        universe_data = generate_synthetic_universe(args.synthetic_instruments, args.limit_candles)
        client = None  # type: ignore
    else:
        key = os.getenv("BLOFIN_API_KEY") or os.getenv("BLOFIN_KEY")
        secret = os.getenv("BLOFIN_API_SECRET") or os.getenv("BLOFIN_SECRET")
        if not key or not secret:
            logger.error("missing Blofin API keys. Copy .env.example to .env and fill it, or rerun with --synthetic.")
            return 2
        client = BlofinClient(api_key=key, api_secret=secret)
        if args.universe:
            universe = [x.strip() for x in args.universe.split(",") if x.strip()]
        else:
            universe = load_universe(client)
        universe_data = []
        for iid in universe:
            rows = client.get_candles(iid, bar=args.bar, limit=args.limit_candles)
            candles = _rows_to_candles(rows)
            if candles:
                universe_data.append((iid, _array(candles)))
        if args.limit_instruments:
            universe_data = universe_data[: args.limit_instruments]

    if not universe_data:
        logger.error("empty instrument dataset")
        return 3

    logger.info("dataset size=%d mode=%s", len(universe_data), args.mode)
    target = 200.0 if not args.synthetic else 200.0
    initial_capital = 40.0 if not args.synthetic else 40.0
    evaluated: List[BacktestResult] = []
    top: BacktestResult | None = None
    for rnd in range(max(1, int(args.retrain_rounds))):
        logger.info("portfolio optimization pass %d/%d", rnd + 1, max(1, int(args.retrain_rounds)))
        grids = default_param_grid(args.mode)
        if evaluated:
            best_by_strategy: Dict[str, dict] = {}
            for res in evaluated:
                if not res.strategy:
                    continue
                prev = best_by_strategy.get(res.strategy)
                score = _score_for_target(res.total_return_pct, target=target)
                if prev is None or score > _score_for_target(float(prev.get("_score", -1e18)), target=target):
                    cand = dict(res.params)
                    cand["_score"] = score
                    best_by_strategy[res.strategy] = cand
            if best_by_strategy:
                grids = {s: _refine_grid(next(iter(best_by_strategy.values()), {})) if s in best_by_strategy else default_param_grid(args.mode)[s] for s in grids}
        top, pass_results = _portfolio_candidate_search(
            universe_data,
            grids,
            target_return=target,
            initial_capital=initial_capital,
        )
        evaluated.extend(pass_results)
        if not top:
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
    ranked = sorted(evaluated, key=lambda r: _score_for_target(r.total_return_pct, target=target), reverse=True)
    best = top or ranked[0]
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
