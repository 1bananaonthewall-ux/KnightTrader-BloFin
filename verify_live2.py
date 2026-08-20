import urllib.request, base64

url = "https://mknight2690-sys.github.io/Polly-Poly-Bot/hermes-coinbase-setup.html"
raw = urllib.request.urlopen(url, timeout=40).read().decode("utf-8", "replace")

if raw[:2] == "PG":
    html = raw
    encoding = "raw html"
elif raw[:2] == "TV" or raw[:4] == "TVM=":
    html = base64.b64decode(raw).decode("utf-8", "replace")
    encoding = "base64"
else:
    html = raw
    encoding = "unknown"

print("encoding:", encoding)
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

if all(checks.values()):
    print("\nLIVE TUTORIAL VERIFICATION PASSED")
else:
    print("\nLIVE TUTORIAL VERIFICATION FAILED")
    failed = [k for k, v in checks.items() if not v]
    print("missing:", failed)
