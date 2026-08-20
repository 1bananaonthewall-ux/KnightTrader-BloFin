import urllib.request, base64, sys

url = "https://raw.githubusercontent.com/mknight2690-sys/Polly-Poly-Bot/main/docs/hermes-coinbase-setup.html"
raw = urllib.request.urlopen(url, timeout=40).read().decode("utf-8", "replace")
try:
    html = base64.b64decode(raw).decode("utf-8", "replace")
except Exception as e:
    print("decode error:", e)
    html = raw

print("tutorial len:", len(html))
print("tutorial title:", html[html.find("<title>"):html.find("</title>") + 7])
checks = {
    "video tag": "<video" in html,
    "windows data-os": 'data-os="windows"' in html or "data-os='windows'" in html,
    "mac data-os": 'data-os="mac"' in html or "data-os='mac'" in html,
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

if any(c for c in checks.values()):
    print("\ncontent check PASSED")
else:
    print("\ncontent check FAILED")
    sys.exit(1)
