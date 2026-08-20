import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

try:
    tree = repo.get_git_tree("main", recursive=True).tree
    for item in tree:
        if "hermes-coinbase" in item.path or item.path.lower() in ["cname", "docs/index.html"]:
            print(item.type, item.path)
except Exception as e:
    print("tree error", e)
