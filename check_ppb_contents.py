from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
repo_path = "mknight2690-sys/Polly-Poly-Bot"
g = Github(token)
repo = g.get_repo(repo_path)
contents = repo.get_contents("", ref="main")
for item in contents[:50]:
    print(item.type, item.path)
