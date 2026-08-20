from github import Github

token = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(token)
repo = g.get_repo("mknight2690-sys/knighttrader-coinbase")
try:
    pages = repo.get_pages()
    print(pages)
except Exception as e:
    print("pages error", e)
