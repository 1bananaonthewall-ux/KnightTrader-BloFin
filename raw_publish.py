import base64, json, os, urllib.request, urllib.error

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
        body = json.loads(resp.read().decode("utf-8"))
        print("STATUS", resp.status)
        return body
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8", "replace"))
        print("HTTP_ERROR", e.code, body)
        return body
    except Exception as e:
        print("EXC", repr(e))
        return {"error": repr(e)}

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    
    # Read local files
    sales_path = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
    tutorial_path = os.path.join(root, "hermes-coinbase-setup.html")
    
    with open(sales_path, "rb") as f:
        sales_b64 = base64.b64encode(f.read()).decode("ascii")
    with open(tutorial_path, "rb") as f:
        tutorial_b64 = base64.b64encode(f.read()).decode("ascii")
    
    print("local sales b64 len:", len(sales_b64))
    print("local tutorial b64 len:", len(tutorial_b64))
    
    # Get current file SHAs
    sales_meta = gh("https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html?ref=master")
    tutorial_meta = gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html?ref=main")
    
    sales_sha = sales_meta.get("sha")
    tutorial_sha = tutorial_meta.get("sha")
    print("sales_sha:", sales_sha)
    print("tutorial_sha:", tutorial_sha)
    
    # Update sales page
    sales_payload = json.dumps({
        "message": "Force rewrite sales page with exact local HTML bytes",
        "content": sales_b64,
        "branch": "master",
        "sha": sales_sha,
    }).encode("utf-8")
    sales_result = gh("https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html", data=sales_payload, method="PUT")
    print("sales result sha:", sales_result.get("content", {}).get("sha"))
    print("sales result size:", sales_result.get("content", {}).get("size"))
    
    # Update tutorial
    tutorial_payload = json.dumps({
        "message": "Force rewrite tutorial with exact local HTML bytes",
        "content": tutorial_b64,
        "branch": "main",
        "sha": tutorial_sha,
    }).encode("utf-8")
    tutorial_result = gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html", data=tutorial_payload, method="PUT")
    print("tutorial result sha:", tutorial_result.get("content", {}).get("sha"))
    print("tutorial result size:", tutorial_result.get("content", {}).get("size"))
    
    print("DONE")

if __name__ == "__main__":
    main()
