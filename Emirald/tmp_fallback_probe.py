import sys
sys.path.insert(0, 'src')
from emirald.config import load_all
from emirald.blofin_client import BlofinClient
from emirald.market_data import build_snapshot, fetch_universe
from emirald.demo_fallback import demo_fallback_decisions

secrets, cfg = load_all('config.yaml')
client = BlofinClient(
    secrets.blofin_api_key,
    secrets.blofin_api_secret,
    secrets.blofin_passphrase,
    broker_id=getattr(secrets, 'blofin_broker_id', '') or '',
    position_mode=getattr(cfg, 'position_mode', 'net') or 'net',
)
instruments = fetch_universe(client)
snapshot = build_snapshot(client, instruments)
print('EQUITY', snapshot.account.equity, 'AVAILABLE', snapshot.account.available)
fb = demo_fallback_decisions(snapshot, None)
print('FALLBACK', fb.thesis)
print('DECISIONS', len(fb.decisions))
for d in fb.decisions:
    print('DEC', d.instId, d.action, d.side, d.sz, d.leverage, d.rationale)
