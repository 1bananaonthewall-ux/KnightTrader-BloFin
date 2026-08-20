import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

for repo_name in ["mknight2690-sys/knighttrader-coinbase", "mknight2690-sys/Polly-Poly-Bot"]:
    repo = g.get_repo(repo_name)
    print("REPO", repo_name)
    print("name:", getattr(repo, "name", None))
    print("default_branch:", getattr(repo, "default_branch", None))
    print("homepage:", getattr(repo, "homepage", None))
    print("has_pages:", getattr(repo, "has_pages", None))
    try:
        pages = repo.get_pages()
        print("pages:", pages)
    except Exception as e:
        print("pages_exc:", repr(e))
    try:
        contents = {c.name: c for c in repo.get_contents("")}
        print("root_names:", list(contents.keys()))
        for name in ["CNAME", "README.md", "hermes-setup-coinbase-buy.html"]:
            if name in contents:
                c = contents[name]
                print(name, "sha:", c.sha, "size:", c.size)
    except Exception as e:
        print("root_exc:", repr(e))
    print()
