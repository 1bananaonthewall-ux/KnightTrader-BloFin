from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
repo_path = "mknight2690-sys/Polly-Poly-Bot"
g = Github(token)
repo = g.get_repo(repo_path)
print("default_branch attr:", repo.default_branch)
for branch in repo.get_branches():
    print("branch:", branch.name)
