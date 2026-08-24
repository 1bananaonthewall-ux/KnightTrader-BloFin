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

positions = client.get_positions()
print('POSITIONS', json.dumps(positions, ensure_ascii=False))
for p in positions:
    iid = p.get('instId')
    side = p.get('positionSide', '').lower()
    sz = p.get('positions', '0')
    clid = f'emirald_close_{iid.replace("-","")}_{side}'
    print(f'Closing {iid} {side} {sz} clid={clid}')
    try:
        raw = client.place_order(
            inst_id=iid,
            side='sell' if side == 'long' else 'buy',
            sz=sz,
            ord_type='market',
            td_mode='isolated',
            cl_ord_id=clid,
        )
        print('CLOSE_OK', json.dumps(raw, ensure_ascii=False)[:500])
    except BlofinAPIError as e:
        print('CLOSE_ERR', e.code, e.message)
        print('PAYLOAD', json.dumps(getattr(e, 'payload', None), ensure_ascii=False)[:500])
