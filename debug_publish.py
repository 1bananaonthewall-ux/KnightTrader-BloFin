import json, os, urllib.request, urllib.error, base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()

def gh(url, data=None, method=None):
    hdrs = {
        "Authorization": "Bearer " + TOK,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=40)
        body = resp.read().decode("utf-8", "replace")
        print("URL:", url)
        print("STATUS:", resp.status)
        print("BODY:", body[:500])
        return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print("URL:", url)
        print("HTTP_ERROR:", e.code)
        print("BODY:", body[:1000])
        return {"error": e.code, "body": body}
    except Exception as e:
        print("URL:", url)
        print("EXC:", repr(e))
        return {"error": type(e).__name__, "body": str(e)[:500]}

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    sales_path = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
    tutorial_path = os.path.join(root, "hermes-coinbase-setup.html")
    for p in [sales_path, tutorial_path]:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        url = "https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html"
        if "Polly-Poly-Bot" in p:
            url = "https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html"
        payload = json.dumps({
            "message": "test publish",
            "content": b64,
            "branch": "master",
        }).encode("utf-8")
        print("\n=== PUT ===")
        r = gh(url, data=payload, method="PUT")
        print("RESULT_KEYS:", list(r.keys())[:10])

if __name__ == "__main__":
    main()
