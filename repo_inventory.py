import json, os, urllib.request

tok = "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"

def headers():
    return {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}

def get(url):
    req = urllib.request.Request(url, headers=headers())
    return json.loads(urllib.request.urlopen(req).read())

def repo_tree(full_name):
    root = get(f"https://api.github.com/repos/{full_name}/contents/")
    items = []
    for i in root:
        if isinstance(i, dict):
            kind = "dir" if i.get("type") == "dir" else "file"
            size = i.get("size") or 0
            items.append((i.get("name"), kind, size, i.get("url")))
    return items

if __name__ == "__main__":
    os.makedirs("agent-tools", exist_ok=True)
    out = "agent-tools/kt-repo-contents.json"
    data = get("https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("=== knighttrader-coinbase ===")
    for name, kind, size, _ in repo_tree("mknight2690-sys/knighttrader-coinbase"):
        print(f"{name} ({size:,} bytes, {kind})")
