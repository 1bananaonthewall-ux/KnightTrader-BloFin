import base64, os, json
from github import Github, GithubException

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
root = os.path.dirname(os.path.abspath(__file__))

sales_local = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
tutorial_local = os.path.join(root, "hermes-coinbase-setup.html")

def read_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

sales_b64 = read_b64(sales_local)
tutorial_b64 = read_b64(tutorial_local)

ktc = g.get_repo("mknight2690-sys/knighttrader-coinbase")
ppb = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

ktc_branch = ktc.default_branch
ppb_branch = ppb.default_branch
print("ktc_branch", ktc_branch)
print("ppb_branch", ppb_branch)

ktc_path = "hermes-setup-coinbase-buy.html"
ppb_path = "docs/hermes-coinbase-setup.html"

def put(repo, path, b64, message, branch):
    try:
        existing = repo.get_contents(path, ref=branch)
        print("existing sha", path, existing.sha)
        result = repo.update_file(path, message, b64, existing.sha, branch=branch)
        print("updated", path, result["content"].html_url)
    except GithubException as e:
        print("get/update exception", path, e.data)
        if e.status == 404:
            result = repo.create_file(path, message, b64, branch=branch)
            print("created", path, result["content"].html_url)
        else:
            raise

put(ktc, ktc_path, sales_b64, "Rewrite sales page to sell Coinbase tutorial (KnightTrader Walkthru)", ktc_branch)
put(ppb, ppb_path, tutorial_b64, "Add Hermes on Coinbase beginner tutorial (Windows & Mac)", ppb_branch)
print("DONE")
