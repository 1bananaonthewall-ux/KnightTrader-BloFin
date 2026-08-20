import urllib.request, base64

def get(url):
    return urllib.request.urlopen(url, timeout=40).read().decode("utf-8", "replace")

def decode_if_needed(raw):
    if raw[:2] == "PG":
        return raw, "raw html"
    try:
        return base64.b64decode(raw).decode("utf-8", "replace"), "base64"
    except Exception:
        return raw, "unknown"

sales_url = "https://mknight2690-sys.github.io/knighttrader-coinbase/hermes-setup-coinbase-buy.html"
tutorial_url = "https://mknight2690-sys.github.io/Polly-Poly-Bot/hermes-coinbase-setup.html"

print("== SALES PAGE ==")
raw = get(sales_url)
html, how = decode_if_needed(raw)
print("encoding:", how)
print("len:", len(html))
print("title:", html[html.find("<title>"):html.find("</title>") + 7])
print("has new branding:", "KnightTrader Walkthru" in html)
print('has new CTA:', "Get the Coinbase setup guide" in html)
print("has preview link:", "Preview the tutorial first" in html)
print("has guarantee:", "30-day money-back guarantee" in html)

print("\n== TUTORIAL ==")
raw = get(tutorial_url)
html, how = decode_if_needed(raw)
print("encoding:", how)
print("len:", len(html))
print("title:", html[html.find("<title>"):html.find("</title>") + 7])
checks = {
    "video tag": "<video" in html,
    "windows data-os": 'data-os="windows"' in html,
    "mac data-os": 'data-os="mac"' in html,
    "every 10 minutes": "every 10 minutes" in html,
    "three tabs": "three tabs" in html.lower(),
    "glossary": "Glossary" in html,
    "nous link": "portal.nousresearch.com" in html,
    "coinbase link": "www.coinbase.com" in html,
    "dashboard link": "127.0.0.1:9119" in html,
    "cron prompt block": "COINBASE PERPETUALS" in html,
}
for k, v in checks.items():
    print(f"{k}: {v}")
print("\nall tutorial checks passed:", all(checks.values()))
