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

for close_sz in ['0.1', '0.05']:
    clid = f'emirald_close_long_{close_sz}'
    print('TRY close long sz=', close_sz, 'clid=', clid)
    try:
        raw = client.place_order(
            inst_id='BTC-USDT',
            side='sell',
            sz=close_sz,
            ord_type='market',
            td_mode='isolated',
            cl_ord_id=clid,
        )
        print('CLOSE_OK', json.dumps(raw, ensure_ascii=False)[:500])
        break
    except BlofinAPIError as e:
        print('CLOSE_ERR', e.code, e.message)
        print('PAYLOAD', json.dumps(getattr(e, 'payload', None), ensure_ascii=False)[:500])
