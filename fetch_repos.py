import json, os, urllib.request

tok = "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"

def headers():
    return {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}

def get(url):
    req = urllib.request.Request(url, headers=headers())
    return json.loads(urllib.request.urlopen(req).read())

def list_repo(full_name, out_path):
    data = get(f"https://api.github.com/repos/{full_name}/contents/")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    for i in data:
        if isinstance(i, dict):
            kind = "dir" if i.get("type") == "dir" else "file"
            size = i.get("size") or 0
            print(f"{full_name} :: {i.get('name')} ({size:,} bytes, {kind})")

if __name__ == "__main__":
    list_repo("mknight2690-sys/Polly-Poly-Bot", "agent-tools/ppb-repo-contents.json")
    print("----")
    list_repo("mknight2690-sys/Polly-Poly-Bot-Sales", "agent-tools/ppbs-repo-contents.json")
