import json
from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(token)
repo = g.get_repo("mknight2690-sys/knighttrader-coinbase")
branch = repo.default_branch
print("default branch:", branch)

# PATCH /repos/{owner}/{repo}/pages
patch = {
    "source": {
        "branch": branch,
        "path": "/"
    }
}
# PyGithub doesn't expose Pages update directly in this snippet form, so use raw request
import requests
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
url = f"https://api.github.com/repos/mknight2690-sys/knighttrader-coinbase/pages"
resp = requests.patch(url, headers=headers, json=patch)
print("status", resp.status_code)
print(resp.text[:500])
