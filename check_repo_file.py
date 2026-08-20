import json, urllib.request

tok = "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"

def headers():
    return {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}

def get(url):
    req = urllib.request.Request(url, headers=headers())
    try:
        data = urllib.request.urlopen(req).read()
        return json.loads(data)
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", "replace")}

urls = [
    "https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html",
    "https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-setup-coinbase-buy.html",
]

for u in urls:
    result = get(u)
    print(u)
    if "error" in result:
        print("  -> missing or error:", result["error"])
    else:
        print("  -> exists, sha:", result.get("sha"))
