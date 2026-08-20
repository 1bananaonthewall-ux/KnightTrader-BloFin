from github import Github
import base64

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(token)
repo = g.get_repo("mknight2690-sys/knighttrader-coinbase")
branch = repo.default_branch
print("default branch:", branch)

try:
    existing = repo.get_contents("hermes-setup-coinbase-buy.html", ref=branch)
    raw = base64.b64decode(existing.content)
    text = raw.decode("utf-8", errors="ignore")
    print("size", len(text))
    print("head:", text[:300])
    print("tail:", text[-300:])
except Exception as e:
    print("error", e)
