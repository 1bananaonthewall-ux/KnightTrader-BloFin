import sys
sys.path.insert(0, 'src')
from emirald.decision import Decision
from emirald.executor import _cl_ord_id

close_short = Decision(instId='BTC-USDT', action='close', side='buy', orderType='market', sz='0.3')
close_long = Decision(instId='BTC-USDT', action='close', side='sell', orderType='market', sz='0.6')

for d in [close_short, close_long]:
    action_l = (getattr(d, 'action', '') or '').lower()
    positionSide = 'short' if d.side == 'buy' and action_l in {'close', 'reduce', 'cancel_and_replace'} else ('long' if d.side == 'buy' else 'short')
    body = {
        'instId': d.instId,
        'marginMode': 'isolated',
        'side': d.side,
        'orderType': d.orderType,
        'size': str(d.sz),
        'positionSide': positionSide,
    }
    print(d.action, d.side, '->', body)
