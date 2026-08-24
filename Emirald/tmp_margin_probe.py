import sys, json
sys.path.insert(0, 'src')
from emirald.config import load_all
from emirald.blofin_client import BlofinClient

secrets, cfg = load_all('config.yaml')
client = BlofinClient(
    secrets.blofin_api_key,
    secrets.blofin_api_secret,
    secrets.blofin_passphrase,
    broker_id=getattr(secrets, 'blofin_broker_id', '') or '',
    position_mode=getattr(cfg, 'position_mode', 'net') or 'net',
)
try:
    bal = client.get_balance()
    print('BALANCE', json.dumps(bal, ensure_ascii=False)[:2000])
except Exception as e:
    print('BALANCE_ERROR', repr(e))
try:
    instruments = client.list_usdt_perps()
    btc = next((i for i in instruments if i.get('instId') == 'BTC-USDT'), None)
    print('BTC_INSTRUMENT', json.dumps(btc, ensure_ascii=False)[:2000])
except Exception as e:
    print('INSTRUMENT_ERROR', repr(e))
