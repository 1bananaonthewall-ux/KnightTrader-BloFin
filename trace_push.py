import json, os, urllib.request, urllib.error, base64, time

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
        return urllib.request.urlopen(req).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return json.dumps({"error": e.code, "body": body})
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "body": str(e)[:500]})

def repo_latest_branch_sha(full_name):
    for b in ("main", "master"):
        raw = gh(f"https://api.github.com/repos/{full_name}/git/refs/heads/{b}")
        try:
            j = json.loads(raw)
            if "error" not in j and j.get("object", {}).get("sha"):
                return b, j["object"]["sha"]
        except Exception:
            continue
    return None, None

def blob_sha_for_file(full_name, path, branch):
    raw = gh(f"https://api.github.com/repos/{full_name}/contents/{path}?ref={branch}")
    try:
        j = json.loads(raw)
        if "error" in j:
            return None
        return j.get("sha")
    except Exception:
        return None

def upload_blob(full_name, path, blob_b64, message, file_sha, branch="main"):
    url = f"https://api.github.com/repos/{full_name}/contents/{path}"
    payload = {
        "message": message,
        "content": blob_b64,
        "branch": branch,
        "sha": file_sha,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers({"Content-Type": "application/json"}))
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", "replace")}

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    sales_local = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
    with open(sales_local, "rb") as f:
        sales_b64 = base64.b64encode(f.read()).decode("ascii")

    print("1) branch + file sha")
    ktc_branch, ktc_commit_sha = repo_latest_branch_sha("mknight2690-sys/knighttrader-coinbase")
    ktc_file_sha = blob_sha_for_file("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html", ktc_branch)
    print("ktc branch:", ktc_branch)
    print("ktc commit sha:", ktc_commit_sha)
    print("ktc file sha:", ktc_file_sha)

    print("2) raw file fetch (console-friendly)")
    raw = gh(f"https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html?ref={ktc_branch}")
    print(raw[:400])

    print("3) push request payload preview")
    push_url = f"https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html"
    payload = {
        "message": "Rewrite sales page to sell Coinbase tutorial (KnightTrader Walkthru)",
        "content": sales_b64,
        "branch": ktc_branch or "master",
        "sha": ktc_file_sha,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:800])

    print("4) attempt push next (separate step)")

if __name__ == "__main__":
    main()
