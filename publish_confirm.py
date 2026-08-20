import json, os, urllib.request, urllib.error, base64, time

TOK = "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"

def headers(extra=None):
    h = {
        "Authorization": "Bearer " + TOK,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra:
        h.update(extra)
    return h

def gh(url, data=None, method=None):
    hdrs = headers()
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=40).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", "replace")}
    except Exception as e:
        return {"error": type(e).__name__, "body": str(e)[:500]}

def repo_branch(full_name):
    for b in ("main", "master"):
        r = gh(f"https://api.github.com/repos/{full_name}/git/refs/heads/{b}")
        if "error" not in r and r.get("object", {}).get("sha"):
            return b
    return None

def file_sha(full_name, path, branch):
    r = gh(f"https://api.github.com/repos/{full_name}/contents/{path}?ref={branch}")
    if "error" in r:
        return None
    return r.get("sha")

def put_file(full_name, path, b64, message, branch, file_sha=None):
    url = f"https://api.github.com/repos/{full_name}/contents/{path}"
    payload = {
        "message": message,
        "content": b64,
        "branch": branch,
    }
    if file_sha:
        payload["sha"] = file_sha
    data = json.dumps(payload).encode("utf-8")
    return gh(url, data=data)

def test_write(full_name, path, branch, new_content):
    print("repo:", full_name, "path:", path, "branch:", branch)
    existing_sha = file_sha(full_name, path, branch)
    print("existing sha:", existing_sha)

    payload = {
        "message": "confirmatory publish test - tiny timestamped edit",
        "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    data = json.dumps(payload).encode("utf-8")
    url = f"https://api.github.com/repos/{full_name}/contents/{path}"
    print("POST", url)
    print("payload preview:", json.dumps(payload, indent=2, ensure_ascii=False)[:400])

    start = time.time()
    resp = gh(url, data=data)
    dur = time.time() - start
    print("elapsed_ms:", int(dur * 1000))
    print("response:")
    print(json.dumps(resp, indent=2, ensure_ascii=False))
    return resp

def main():
    ktc_branch = repo_branch("mknight2690-sys/knighttrader-coinbase")
    ppb_branch = repo_branch("mknight2690-sys/Polly-Poly-Bot")
    print("branches:", ktc_branch, ppb_branch)

    ktc_content = "<!-- publish-test marker -->\nOK\n"
    ppb_content = "# publish-test marker\n\nOK\n"

    print("\n=== confirmatory write: knighttrader-coinbase README.md ===")
    r = test_write("mknight2690-sys/knighttrader-coinbase", "README.md", ktc_branch, ktc_content)

    print("\n=== confirmatory write: Polly-Poly-Bot README.md ===")
    r = test_write("mknight2690-sys/Polly-Poly-Bot", "README.md", ppb_branch, ppb_content)

if __name__ == "__main__":
    main()
