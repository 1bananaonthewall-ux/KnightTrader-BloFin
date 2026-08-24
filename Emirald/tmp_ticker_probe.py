import sys, json
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
print('INSTRUMENT_COUNT', len(instruments))
# Show some instruments with null lotSz/last
nulls = [i for i in instruments.values() if not i.lotSz or i.lotSz <= 0 or not i.contract_value][:10]
print('NULL_LOTS', json.dumps([{ 'instId': i.instId, 'lotSz': i.lotSz, 'contract_value': i.contract_value } for i in nulls], ensure_ascii=False))

inst_ids = [iid for iid, inst in instruments.items() if inst.state == 'live']
tickers = fetch_tickers(client, inst_ids[:50])
bad = [{'instId': k, 'last': v.last, 'chg': v.change_24h_pct} for k, v in tickers.items() if v.last <= 0 or v.change_24h_pct < 1.0]
print('BAD_TICKERS_SAMPLE', json.dumps(bad[:20], ensure_ascii=False))

top = select_top_n(tickers, instruments, n=5)
print('TOP5', json.dumps(top, ensure_ascii=False))
for iid in top:
    t = tickers.get(iid)
    inst = instruments.get(iid)
    print('TOP_DETAIL', json.dumps({
        'instId': iid,
        'last': t.last if t else None,
        'chg': t.change_24h_pct if t else None,
        'lotSz': inst.lotSz if inst else None,
        'minSz': inst.minSz if inst else None,
        'contract_value': inst.contract_value if inst else None,
    }, ensure_ascii=False))
