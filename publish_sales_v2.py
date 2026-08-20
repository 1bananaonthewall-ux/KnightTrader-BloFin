import os, base64
from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
repo_path = "mknight2690-sys/knighttrader-coinbase"
local_file = r"C:\Users\mknig\hermes-trader\knighttrader-coinbase\hermes-setup-coinbase-buy.html"
remote_path = "hermes-setup-coinbase-buy.html"
branch = "main"

g = Github(token)
repo = g.get_repo(repo_path)

with open(local_file, "r", encoding="utf-8") as f:
    content = f.read()
content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

try:
    existing = repo.get_contents(remote_path, ref=branch)
    repo.update_file(remote_path, "Update Coinbase sales page wording", content_b64, existing.sha, branch=branch)
    print("updated sales page")
except Exception as e:
    print("creating sales page", e)
    repo.create_file(remote_path, "Publish Coinbase sales page", content_b64, branch=branch)
