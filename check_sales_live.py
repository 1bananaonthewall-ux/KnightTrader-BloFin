import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/knighttrader-coinbase")
content = repo.get_contents("hermes-setup-coinbase-buy.html", ref="master")
raw = base64.b64decode(content.content).decode("utf-8", "replace")
print("sha:", content.sha, "size:", content.size, "lines:", raw.count("\n") + 1)
print("HEAD:\n", raw[:500])
print("TAIL:\n", raw[-500:])
