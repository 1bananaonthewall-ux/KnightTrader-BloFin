import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")
content = repo.get_contents("docs/hermes-coinbase-setup.html", ref="main")
html = base64.b64decode(content.content).decode("utf-8", "replace")
print("HAS_ABSOLUTE_VIDEO:", "/Polly-Poly-Bot/video/" in html)
print("sample:", [line for line in html.splitlines() if "video/" in line][:3])
