import json, os, urllib.request, urllib.error

tok = "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"

def headers():
    return {
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh_get(url):
    req = urllib.request.Request(url, headers=headers())
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode("utf-8", "replace")}

def main():
    os.makedirs("agent-tools", exist_ok=True)

    print("=== ppbs repo contents ===")
    ppbs = gh_get("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot-Sales/contents/")
    with open("agent-tools/ppbs-repo-contents.json", "w", encoding="utf-8") as f:
        json.dump(ppbs, f, ensure_ascii=False, indent=2)
    if "error" in ppbs:
        print("ERROR", ppbs["error"], ppbs.get("body", ""))
    else:
        for i in ppbs:
            if isinstance(i, dict):
                k = "dir" if i.get("type") == "dir" else "file"
                print(f"{i.get('name')} ({i.get('size') or 0:,} bytes, {k})")

    print("\n=== ppb coinbase tutorial check ===")
    ppb = gh_get("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html")
    with open("agent-tools/ppb-coinbase-tutorial-check.json", "w", encoding="utf-8") as f:
        json.dump(ppb, f, ensure_ascii=False, indent=2)
    if "error" in ppb:
        print("ERROR", ppb["error"])
    else:
        print("EXISTS sha:", ppb.get("sha"), "size:", ppb.get("size"))

    print("\n=== ppb docs contents ===")
    docs = gh_get("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs")
    with open("agent-tools/ppb-docs-contents.json", "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    if "error" in docs:
        print("ERROR", docs["error"])
    else:
        for i in docs:
            if isinstance(i, dict):
                k = "dir" if i.get("type") == "dir" else "file"
                print(f"{i.get('name')} ({i.get('size') or 0:,} bytes, {k})")

if __name__ == "__main__":
    main()
