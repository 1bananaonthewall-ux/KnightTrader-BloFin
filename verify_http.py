import urllib.request, urllib.error, sys

urls = [
    "https://mknight2690-sys.github.io/Polly-Poly-Bot/hermes-coinbase-setup.html",
    "https://mknight2690-sys.github.io/Polly-Poly-Bot/docs/hermes-coinbase-setup.html",
    "https://mknight2690-sys.github.io/knighttrader-coinbase/hermes-setup-coinbase-buy.html",
]
for u in urls:
    try:
        resp = urllib.request.urlopen(u, timeout=40)
        print(f"{resp.status}  {u}")
    except urllib.error.HTTPError as e:
        print(f"{e.code}  {u}")
    except Exception as e:
        print(f"ERR  {u}  {type(e).__name__} {str(e)[:120]}")
