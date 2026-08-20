import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

for repo_name in ["mknight2690-sys/knighttrader-coinbase", "mknight2690-sys/Polly-Poly-Bot"]:
    repo = g.get_repo(repo_name)
    print(repo_name, "default_branch:", repo.default_branch)
