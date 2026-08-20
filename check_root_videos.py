import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

try:
    tree = repo.get_git_tree("main", recursive=True).tree
    root_videos = [item.path for item in tree if item.path.startswith("video/") and item.path.endswith(".mp4")]
    docs_videos = [item.path for item in tree if item.path.startswith("docs/video/") and item.path.endswith(".mp4")]
    print("root videos:", len(root_videos))
    print("docs videos:", len(docs_videos))
    if root_videos:
        print("root samples:", root_videos[:5])
except Exception as e:
    print("tree error", e)
