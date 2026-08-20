from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
repo_path = "mknight2690-sys/Polly-Poly-Bot"
g = Github(token)
repo = g.get_repo(repo_path)
branch = repo.default_branch
print("default branch:", branch)

try:
    contents = repo.get_contents("", ref=branch)
    for item in contents:
        print(item.type, item.path)
except Exception as e:
    print("contents error", e)

try:
    existing = repo.get_contents("hermes-coinbase-setup.html", ref=branch)
    print("tutorial sha", existing.sha)
except Exception as e:
    print("tutorial missing", e)
