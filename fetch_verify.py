import json, urllib.request, urllib.error

TOK = "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"

def headers():
    return {
        "Authorization": "Bearer " + TOK,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh(url):
    req = urllib.request.Request(url, headers=headers())
    try:
        return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return json.dumps({"error": e.code, "body": e.read().decode("utf-8", "replace")})
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "body": str(e)[:500]})

def main():
    print("== sales page raw file ==")
    print(gh("https://raw.githubusercontent.com/mknight2690-sys/knighttrader-coinbase/master/hermes-setup-coinbase-buy.html")[:300])
    print("\n== repo file metadata ==")
    print(gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html"))
    print("\n== tutorial raw file ==")
    print(gh("https://raw.githubusercontent.com/mknight2690-sys/Polly-Poly-Bot/main/docs/hermes-coinbase-setup.html")[:300])
    print("\n== gh-pages branch check ==")
    print(gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/git/refs/heads/gh-pages"))
    print("\n== default branch ==")
    print(gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot")[:300])

if __name__ == "__main__":
    main()
