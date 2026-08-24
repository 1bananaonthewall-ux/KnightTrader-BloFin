import sys
sys.path.insert(0, 'src')
from emirald.config import load_all
from emirald.blofin_client import BlofinClient
from emirald.market_data import fetch_universe, fetch_tickers, select_top_n

secrets, cfg = load_all('config.yaml')
client = BlofinClient(
    secrets.blofin_api_key,
    secrets.blofin_api_secret,
    secrets.blofin_passphrase,
    broker_id=getattr(secrets, 'blofin_broker_id', '') or '',
    position_mode=getattr(cfg, 'position_mode', 'net') or 'net',
)
instruments = fetch_universe(client)
inst_ids = [iid for iid, inst in instruments.items() if inst.state == 'live']
tickers = fetch_tickers(client, inst_ids[:100])
equity = 7.67
threshold = max(250_000.0, equity * 25_000.0)
print('THRESHOLD', threshold)
ranked = sorted(tickers.values(), key=lambda t: (t.change_24h_pct, t.vol_24h_quote), reverse=True)
eligible = [t for t in ranked if t.last > 0 and t.change_24h_pct >= 1.0 and t.vol_24h_quote >= threshold and t.instId in instruments]
print('ELIGIBLE_COUNT', len(eligible))
for t in eligible[:10]:
    print('ELIGIBLE', t.instId, 'chg=', round(t.change_24h_pct, 2), 'vol=', round(t.vol_24h_quote, 2))
