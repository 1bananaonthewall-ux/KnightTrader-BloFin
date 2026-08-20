import json, os, urllib.request

tok = "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"

def headers():
    return {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}

def get(url):
    req = urllib.request.Request(url, headers=headers())
    return json.loads(urllib.request.urlopen(req).read())

def tree(full_name, path="/", out_path=None, depth=0, max_depth=3):
    url = f"https://api.github.com/repos/{full_name}/contents/{path.lstrip('/')}"
    data = get(url)
    rows = []
    for i in data:
        if not isinstance(i, dict):
            continue
        name = i.get("name") or i.get("path", "").split("/")[-1]
        kind = i.get("type")
        rows.append((depth, kind, name, i.get("download_url"), i.get("html_url")))
        if kind == "dir" and depth < max_depth:
            rows.extend(tree(full_name, i.get("path", ""), out_path, depth + 1, max_depth))
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([{"depth": d, "kind": k, "name": n, "download_url": du, "html_url": hu}
                       for d, k, n, du, hu in rows], f, ensure_ascii=False, indent=2)
    return rows

if __name__ == "__main__":
    print("=== Polly-Poly-Bot/docs ===")
    for d, k, n, du, hu in tree("mknight2690-sys/Polly-Poly-Bot", "/docs", "agent-tools/ppb-docs-tree.json", max_depth=2):
        print(f"{'  '*d}{k} {n} {du or hu}")
    print("\n=== Polly-Poly-Bot-Sales ===")
    for d, k, n, du, hu in tree("mknight2690-sys/Polly-Poly-Bot-Sales", "/", "agent-tools/ppbs-tree.json", max_depth=2):
        print(f"{'  '*d}{k} {n} {du or hu}")
