import base64, os, json
from github import Github, GithubException

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

def read_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

root = os.path.dirname(os.path.abspath(__file__))
sales_b64 = read_b64(os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html"))
tutorial_b64 = read_b64(os.path.join(root, "hermes-coinbase-setup.html"))

ktc = g.get_repo("mknight2690-sys/knighttrader-coinbase")
ppb = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

ktc_branch = ktc.default_branch
ppb_branch = ppb.default_branch
print("ktc_branch", ktc_branch)
print("ppb_branch", ppb_branch)

for attempt in range(1, 4):
    try:
        existing = ktc.get_contents("hermes-setup-coinbase-buy.html", ref=ktc_branch)
        ktc.update_file("hermes-setup-coinbase-buy.html", "Rewrite sales page to sell Coinbase tutorial (KnightTrader Walkthru)", sales_b64, existing.sha, branch=ktc_branch)
    except GithubException as e:
        print("sales error", e.data)
        if e.status == 404 and attempt < 3:
            continue
        raise
    else:
        print("sales updated")
        break

for attempt in range(1, 4):
    try:
        existing = ppb.get_contents("docs/hermes-coinbase-setup.html", ref=ppb_branch)
        ppb.update_file("docs/hermes-coinbase-setup.html", "Add Hermes on Coinbase beginner tutorial (Windows & Mac)", tutorial_b64, existing.sha, branch=ppb_branch)
    except GithubException as e:
        print("tutorial error", e.data)
        if e.status == 404 and attempt < 3:
            continue
        raise
    else:
        print("tutorial updated")
        break

print("DONE")
