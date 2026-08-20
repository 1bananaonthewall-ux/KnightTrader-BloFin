import json, urllib.request, urllib.error

tok = "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"

def headers():
    return {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh(url):
    req = urllib.request.Request(url, headers=headers())
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", "replace")}

tests = [
    "https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/README.md",
    "https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html",
    "https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs",
]

for u in tests:
    print(u)
    r = gh(u)
    if "error" in r:
        print("  ERROR", r["error"])
    else:
        print("  OK", r.get("name"), r.get("sha"))
