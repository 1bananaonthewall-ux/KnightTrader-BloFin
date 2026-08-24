import sys, json
sys.path.insert(0, 'src')
from emirald.config import load_all
from emirald.blofin_client import BlofinClient
from emirald.market_data import fetch_universe, fetch_account, fetch_positions, fetch_tickers

secrets, cfg = load_all('config.yaml')
client = BlofinClient(
    secrets.blofin_api_key,
    secrets.blofin_api_secret,
    secrets.blofin_passphrase,
    broker_id=getattr(secrets, 'blofin_broker_id', '') or '',
    position_mode=getattr(cfg, 'position_mode', 'net') or 'net',
)
try:
    raw_bal = client.get_balance()
    print('RAW_BALANCE', json.dumps(raw_bal, ensure_ascii=False)[:4000])
except Exception as e:
    print('RAW_BALANCE_ERROR', repr(e))
try:
    instruments = fetch_universe(client)
    inst = instruments.get('PROM-USDT') or instruments.get('PORTAL-USDT') or next(iter(instruments.values()))
    print('INSTRUMENT', json.dumps({
        'instId': inst.instId,
        'lotSz': inst.lotSz,
        'minSz': inst.minSz,
        'contract_value': inst.contract_value,
        'state': inst.state,
    }, ensure_ascii=False))
except Exception as e:
    print('INSTRUMENT_ERROR', repr(e))
try:
    acct = fetch_account(client)
    print('ACCOUNT', json.dumps({
        'equity': acct.equity,
        'available': acct.available,
        'margin_used': acct.margin_used,
        'unrealized_pnl': acct.unrealized_pnl,
    }, ensure_ascii=False))
except Exception as e:
    print('ACCOUNT_ERROR', repr(e))
try:
    positions = fetch_positions(client)
    print('POSITIONS', json.dumps(positions, ensure_ascii=False)[:2000])
except Exception as e:
    print('POSITIONS_ERROR', repr(e))
try:
    raw_orders = client.get_open_orders() or []
    print('OPEN_ORDERS_COUNT', len(raw_orders))
    for o in raw_orders[:5]:
        print('OPEN_ORDER', json.dumps(o, ensure_ascii=False)[:500])
except Exception as e:
    print('OPEN_ORDERS_ERROR', repr(e))
