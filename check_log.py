import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

for repo_name, path in [
    ("mknight2690-sys/knighttrader-coinbase", "hermes-setup-coinbase-buy.html"),
    ("mknight2690-sys/Polly-Poly-Bot", "docs/hermes-coinbase-setup.html"),
]:
    repo = g.get_repo(repo_name)
    print("\nREPO", repo_name, "path", path)
    commits = repo.get_commits(path=path)
    for i, commit in enumerate(commits[:5]):
        print(i, commit.sha[:7], commit.commit.message[:120], commit.commit.author.date)
