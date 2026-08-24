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
for p in positions:
    iid = p.get('instId')
    side = p.get('positionSide', '').lower()
    sz = p.get('positions', '0')
    for close_sz in [sz, '0.3', '0.2', '0.1']:
        clid = f'emirald_close_{iid.replace("-","")}_{side}_{close_sz}'
        print(f'Trying close {iid} {side} sz={close_sz} clid={clid}')
        try:
            raw = client.place_order(
                inst_id=iid,
                side='sell' if side == 'long' else 'buy',
                sz=close_sz,
                ord_type='market',
                td_mode='isolated',
                cl_ord_id=clid,
            )
            print('CLOSE_OK', json.dumps(raw, ensure_ascii=False)[:500])
            break
        except BlofinAPIError as e:
            print('CLOSE_ERR', e.code, e.message)
            if 'Insufficient margin' not in str(e):
                break
        except Exception as e:
            print('CLOSE_EXC', repr(e))
            break
