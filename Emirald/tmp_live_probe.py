import sys, json
sys.path.insert(0, 'src')
from emirald.config import load_all
from emirald.blofin_client import BlofinClient
from emirald.sizing import load_playbook_risk, plan_open

secrets, cfg = load_all('config.yaml')
client = BlofinClient(
    secrets.blofin_api_key,
    secrets.blofin_api_secret,
    secrets.blofin_passphrase,
    broker_id=getattr(secrets, 'blofin_broker_id', '') or '',
    position_mode=getattr(cfg, 'position_mode', 'net') or 'net',
)
instruments = client.list_usdt_perps()
inst = next(i for i in instruments if i.get('instId') == 'PROM-USDT')
print('INST', json.dumps({k: inst.get(k) for k in ['instId','lotSz','minSz','contractValue','state','last']}, ensure_ascii=False))
price = float(inst.get('last') or 0)
risk = load_playbook_risk()
plan = plan_open(
    equity=7.67,
    cash=7.67,
    open_count=0,
    price=price,
    lot=float(inst.get('lotSz', 1) or 1),
    min_sz=float(inst.get('minSz', 1) or 1),
    contract_value=float(inst.get('contractValue', 1) or 1) or None,
    margin_already_used=0.0,
    risk=risk,
)
print('PLAN', json.dumps(plan.__dict__ if plan else None, ensure_ascii=False))
if plan:
    body = {
        'instId': 'PROM-USDT',
        'marginMode': 'isolated',
        'positionSide': 'long',
        'side': 'buy',
        'orderType': 'market',
        'size': str(int(plan.sz)),
    }
    print('BODY', json.dumps(body, ensure_ascii=False))
    try:
        raw = client.place_order(
            inst_id='PROM-USDT',
            side='buy',
            sz=str(int(plan.sz)),
            ord_type='market',
            td_mode='isolated',
            leverage=5,
            stop_loss=None,
            take_profit=None,
            cl_ord_id='emirald_live_probe',
        )
        print('ORDER_OK', json.dumps(raw, ensure_ascii=False)[:1200])
    except Exception as e:
        print('ORDER_ERR', repr(e))
        if hasattr(e, 'payload'):
            print('PAYLOAD', json.dumps(e.payload, ensure_ascii=False)[:1200])
