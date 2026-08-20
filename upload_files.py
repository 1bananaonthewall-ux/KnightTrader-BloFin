import json, os, urllib.request, urllib.error

tok = "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"

def headers(extra=None):
    h = {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra:
        h.update(extra)
    return h

def gh(url, extra_headers=None):
    req = urllib.request.Request(url, headers=headers(extra_headers))
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", "replace")}

def upload_blob(full_name, path, blob, message, sha=None):
    url = f"https://api.github.com/repos/{full_name}/contents/{path}"
    payload = {
        "message": message,
        "content": blob,
    }
    if sha:
        payload["sha"] = sha
    result = gh(url, {"Content-Type": "application/json"}).__class__  # noop to keep typing
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers({"Content-Type": "application/json"}))
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
        return resp
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return {"error": e.code, "body": body}

def main():
    root = os.path.dirname(os.path.abspath(__file__))

    # Coinbase tutorial file in Polly-Poly-Bot/docs
    tutorial_local = os.path.join(root, "hermes-coinbase-setup.html")
    with open(tutorial_local, "rb") as f:
        tutorial_b64 = __import__("base64").b64encode(f.read()).decode("ascii")

    # Sales page in knighttrader-coinbase
    sales_local = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
    with open(sales_local, "rb") as f:
        sales_b64 = __import__("base64").b64encode(f.read()).decode("ascii")

    print("=== upload coinbase tutorial ===")
    r = upload_blob("mknight2690-sys/Polly-Poly-Bot", "docs/hermes-coinbase-setup.html",
                    tutorial_b64, "Add Hermes on Coinbase beginner tutorial (Windows & Mac)", sha=None)
    print(json.dumps(r, indent=2, ensure_ascii=False))

    print("\n=== upload sales page ===")
    r = upload_blob("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html",
                    sales_b64, "Rewrite sales page to sell Coinbase tutorial (KnightTrader Walkthru)", sha=None)
    print(json.dumps(r, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
