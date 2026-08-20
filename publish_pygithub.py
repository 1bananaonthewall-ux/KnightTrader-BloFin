import base64, os, time
from github import Github, GithubException

TOK = "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"

def main():
    g = Github(TOK)
    root = os.path.dirname(os.path.abspath(__file__))

    sales_local = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
    with open(sales_local, "rb") as f:
        sales_b64 = base64.b64encode(f.read()).decode("ascii")

    tutorial_local = os.path.join(root, "hermes-coinbase-setup.html")
    with open(tutorial_local, "rb") as f:
        tutorial_b64 = base64.b64encode(f.read()).decode("ascii")

    print("== knighttrader-coinbase ==")
    repo_ktc = g.get_repo("mknight2690-sys/knighttrader-coinbase")
    branch_ktc = repo_ktc.default_branch
    print("default_branch:", branch_ktc)
    try:
        existing = repo_ktc.get_contents("hermes-setup-coinbase-buy.html", ref=branch_ktc)
        print("existing file sha:", existing.sha)
        result = repo_ktc.update_file(
            "hermes-setup-coinbase-buy.html",
            "Rewrite sales page to sell Coinbase tutorial (KnightTrader Walkthru)",
            sales_b64.decode("ascii"),
            existing.sha,
            branch=branch_ktc,
        )
        print("update_file result:", result)
    except GithubException as e:
        print("GithubException:", e.data)

    print("\n== Polly-Poly-Bot ==")
    repo_ppb = g.get_repo("mknight2690-sys/Polly-Poly-Bot")
    branch_ppb = repo_ppb.default_branch
    print("default_branch:", branch_ppb)
    try:
        existing = repo_ppb.get_contents("docs/hermes-coinbase-setup.html", ref=branch_ppb)
        print("existing file sha:", existing.sha)
        result = repo_ppb.update_file(
            "docs/hermes-coinbase-setup.html",
            "Add Hermes on Coinbase beginner tutorial (Windows & Mac)",
            tutorial_b64.decode("ascii"),
            existing.sha,
            branch=branch_ppb,
        )
        print("update_file result:", result)
    except GithubException as e:
        print("GithubException:", e.data)

if __name__ == "__main__":
    main()
