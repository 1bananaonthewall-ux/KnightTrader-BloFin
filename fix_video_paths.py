import os
import re
import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

# Read current tutorial
content = repo.get_contents("docs/hermes-coinbase-setup.html", ref="main")
raw = content.content
html = base64.b64decode(raw).decode("utf-8", "replace")

# Update all video paths to absolute paths
html = html.replace('src="video/', 'src="/Polly-Poly-Bot/video/')
html = html.replace("src='video/", "src='/Polly-Poly-Bot/video/")

# Push updated HTML
new_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
repo.update_file("docs/hermes-coinbase-setup.html", "Update video paths to absolute for Pages", new_b64, content.sha, branch="main")
print("updated video paths to absolute")
