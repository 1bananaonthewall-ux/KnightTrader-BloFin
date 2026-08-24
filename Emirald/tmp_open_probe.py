import sys, json
sys.path.insert(0, 'src')
from emirald.config import load_all
from emirald.blofin_client import BlofinClient, BlofinAPIError

secrets, cfg = load_all('config.yaml')
client = BlofinClient(
    secrets.blofin_api_key,
    secrets.blofin_api_secret,
    secrets.blofin_passphrase,
    broker_id=getattr(secrets, 'blofin_broker_id', '') or '',
    position_mode=getattr(cfg, 'position_mode', 'net') or 'net',
)

cases = [
    {'label': 'btc_no_sl_tp', 'kwargs': {'inst_id': 'BTC-USDT', 'side': 'buy', 'sz': '0.1', 'ord_type': 'market', 'td_mode': 'isolated', 'cl_ord_id': 'emirald_probe_btc_1'}},
    {'label': 'eth_no_sl_tp', 'kwargs': {'inst_id': 'ETH-USDT', 'side': 'buy', 'sz': '0.5', 'ord_type': 'market', 'td_mode': 'isolated', 'cl_ord_id': 'emirald_probe_eth_1'}},
]
for case in cases:
    try:
        raw = client.place_order(**case['kwargs'])
        print(case['label'], 'OK', json.dumps(raw, ensure_ascii=False)[:500])
    except BlofinAPIError as e:
        print(case['label'], 'API_ERROR', e.code, e.message)
        print('PAYLOAD', json.dumps(getattr(e, 'payload', None), ensure_ascii=False)[:800])
    except Exception as e:
        print(case['label'], 'ERR', repr(e))
