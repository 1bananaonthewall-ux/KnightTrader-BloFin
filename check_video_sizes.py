import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

try:
    tree = repo.get_git_tree("main", recursive=True).tree
    for item in tree:
        if item.path.startswith("docs/video/") and item.path.endswith(".mp4"):
            print(f"{item.path}: {item.size} bytes ({item.size/1024/1024:.2f} MB)")
except Exception as e:
    print("tree error", e)
