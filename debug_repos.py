import os, urllib.request, urllib.error, json

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()

def gh(url):
    hdrs = {
        "Authorization": "Bearer " + TOK,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=hdrs)
    try:
        resp = urllib.request.urlopen(req, timeout=40)
        body = resp.read().decode("utf-8", "replace")
        print("URL:", url)
        print("STATUS:", resp.status)
        print("BODY:", body[:1500])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print("URL:", url)
        print("HTTP_ERROR:", e.code)
        print("BODY:", body[:2000])
    except Exception as e:
        print("URL:", url)
        print("EXC:", repr(e))

def main():
    gh("https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase")
    print("\n---\n")
    gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot")
    print("\n---\n")
    gh("https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html?ref=master")
    print("\n---\n")
    gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html?ref=master")
    print("\n---\n")
    gh("https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/contents/hermes-setup-coinbase-buy.html?ref=main")
    print("\n---\n")
    gh("https://api.github.com/repos/mknight2690-sys/Polly-Poly-Bot/contents/docs/hermes-coinbase-setup.html?ref=main")

if __name__ == "__main__":
    main()
