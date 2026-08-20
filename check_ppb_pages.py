import os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")
print("name:", repo.name)
print("default_branch:", repo.default_branch)
print("html_url:", repo.html_url)
print("homepage:", repo.homepage)
print("has_pages:", repo.has_pages)
