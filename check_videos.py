import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

for repo_name in ["mknight2690-sys/knighttrader-coinbase", "mknight2690-sys/Polly-Poly-Bot"]:
    repo = g.get_repo(repo_name)
    print("\nREPO", repo_name)
    try:
        tree = repo.get_git_tree(repo.default_branch, recursive=True).tree
        for item in tree:
            if item.path.startswith("video/") or item.path.endswith(".mp4") or item.path.endswith(".png") or item.path.endswith(".jpg"):
                print(item.type, item.path, item.size)
    except Exception as e:
        print("tree error", e)
