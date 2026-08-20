import base64
from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
repo_path = "mknight2690-sys/Polly-Poly-Bot"
local_file = r"C:\Users\mknig\hermes-trader\hermes-coinbase-setup.html"
remote_path = "hermes-coinbase-setup.html"

g = Github(token)
repo = g.get_repo(repo_path)
branch = repo.default_branch
print("default branch:", branch)

with open(local_file, "r", encoding="utf-8") as f:
    content = f.read()
updated = content.replace('src="video/', 'src="/Polly-Poly-Bot/video/')
if updated != content:
    with open(local_file, "w", encoding="utf-8") as f:
        f.write(updated)
    print("updated local paths")
else:
    print("paths already absolute")

content_b64 = base64.b64encode(updated.encode("utf-8")).decode("ascii")

try:
    existing = repo.get_contents(remote_path, ref=branch)
    repo.update_file(remote_path, "Update tutorial video paths for Pages", content_b64, existing.sha, branch=branch)
    print("updated tutorial")
except Exception as e:
    print("creating tutorial", e)
    repo.create_file(remote_path, "Publish Coinbase tutorial", content_b64, branch=branch)
