import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

for repo_name in ["mknight2690-sys/knighttrader-coinbase", "mknight2690-sys/Polly-Poly-Bot"]:
    repo = g.get_repo(repo_name)
    print("\nREPO", repo_name, "default_branch", repo.default_branch)
    try:
        tree = repo.get_git_tree(repo.default_branch, recursive=True).tree
        found = [item.path for item in tree if item.path.startswith("video/") or item.path.endswith(".mp4") or item.path.endswith(".png") or item.path.endswith(".jpg") or item.path.endswith(".jpeg")]
        print("media files:", found[:50])
        if not found:
            print("NO MEDIA FILES FOUND")
    except Exception as e:
        print("tree error", e)
