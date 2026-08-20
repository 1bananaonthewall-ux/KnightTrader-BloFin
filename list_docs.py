import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

try:
    docs = repo.get_contents("docs")
    for item in docs:
        print(item.type, item.name, item.size)
except Exception as e:
    print("docs error", e)
