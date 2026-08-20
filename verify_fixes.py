import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

def check(repo_name, path, branch):
    repo = g.get_repo(repo_name)
    content = repo.get_contents(path, ref=branch)
    raw = base64.b64decode(content.content).decode("utf-8", "replace")
    print("\nREPO:", repo_name, "PATH:", path)
    print("SIZE:", content.size, "LINES:", raw.count("\n") + 1)
    print("HAS_COPY_BTN:", "copybtn" in raw)
    print("HAS_VIDEO_FALLBACK:", "Video walkthrough will appear here" in raw)
    print("HAS_BROKEN_CANCEL:", "Checkout cancelled.</h4>" in raw)

check("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html", "master")
check("mknight2690-sys/Polly-Poly-Bot", "docs/hermes-coinbase-setup.html", "main")
