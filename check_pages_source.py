import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

try:
    pages = repo.get_pages()
    print("pages:", pages)
except Exception as e:
    print("pages_exc:", repr(e))

try:
    contents = {c.name: c for c in repo.get_contents("")}
    for name in [".nojekyll", "docs/.nojekyll"]:
        if name in contents:
            print(name, "exists")
        else:
            print(name, "missing")
except Exception as e:
    print("root_exc:", repr(e))

try:
    docs = repo.get_contents("docs")
    print("docs items:", [c.name for c in docs][:20])
except Exception as e:
    print("docs_exc:", repr(e))
