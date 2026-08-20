import json, os, urllib.request, urllib.error, base64

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

def repo_latest_branch_sha(full_name):
    for b in ("main", "master"):
        r = gh(f"https://api.github.com/repos/{full_name}/git/refs/heads/{b}")
        if "error" not in r and r.get("object", {}).get("sha"):
            return b, r["object"]["sha"]
    return None, None

def blob_sha_for_file(full_name, path, branch):
    r = gh(f"https://api.github.com/repos/{full_name}/contents/{path}?ref={branch}")
    if "error" in r:
        return None
    return r.get("sha")

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

    tutorial_local = os.path.join(root, "hermes-coinbase-setup.html")
    with open(tutorial_local, "rb") as f:
        tutorial_b64 = base64.b64encode(f.read()).decode("ascii")

    sales_local = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
    with open(sales_local, "rb") as f:
        sales_b64 = base64.b64encode(f.read()).decode("ascii")

    ppb_branch, ppb_commit_sha = repo_latest_branch_sha("mknight2690-sys/Polly-Poly-Bot")
    ktc_branch, ktc_commit_sha = repo_latest_branch_sha("mknight2690-sys/knighttrader-coinbase")

    ppb_file_sha = blob_sha_for_file("mknight2690-sys/Polly-Poly-Bot", "docs/hermes-coinbase-setup.html", ppb_branch)
    ktc_file_sha = blob_sha_for_file("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html", ktc_branch)

    print("ppb branch:", ppb_branch, "commit sha:", ppb_commit_sha, "file sha:", ppb_file_sha)
    print("ktc branch:", ktc_branch, "commit sha:", ktc_commit_sha, "file sha:", ktc_file_sha)

    print("\n=== upload coinbase tutorial ===")
    r = upload_blob("mknight2690-sys/Polly-Poly-Bot", "docs/hermes-coinbase-setup.html",
                    tutorial_b64, "Add Hermes on Coinbase beginner tutorial (Windows & Mac)",
                    file_sha=ppb_file_sha, branch=ppb_branch or "main")
    print(json.dumps(r, indent=2, ensure_ascii=False))

    print("\n=== upload sales page ===")
    r = upload_blob("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html",
                    sales_b64, "Rewrite sales page to sell Coinbase tutorial (KnightTrader Walkthru)",
                    file_sha=ktc_file_sha, branch=ktc_branch or "master")
    print(json.dumps(r, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
