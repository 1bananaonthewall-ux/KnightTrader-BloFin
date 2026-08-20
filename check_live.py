import base64, os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

def show(repo_name, path, branch):
    repo = g.get_repo(repo_name)
    print("\nREPO", repo_name, "branch", branch, "path", path)
    try:
        content = repo.get_contents(path, ref=branch)
        raw = base64.b64decode(content.content).decode("utf-8", "replace")
        print("sha:", content.sha, "size:", content.size, "encoding:", content.encoding)
        print("HEAD:\n", raw[:500])
        print("TAIL:\n", raw[-500:])
        print("LINE_COUNT:", raw.count("\n") + 1)
    except Exception as e:
        print("ERR", repr(e))

show("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html", "master")
show("mknight2690-sys/Polly-Poly-Bot", "docs/hermes-coinbase-setup.html", "main")
