import base64, os
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

def read_file(path):
    with open(path, "rb") as f:
        return f.read()

def force_update(repo, path, data, message, branch):
    b64 = base64.b64encode(data).decode("ascii")
    try:
        existing = repo.get_contents(path, ref=branch)
        print("updating", path, "existing_sha", existing.sha, "size", existing.size)
        result = repo.update_file(path, message, b64, existing.sha, branch=branch)
        print("updated", path, "new_sha", result["content"].sha, "new_size", result["content"].size)
    except Exception as e:
        print("update failed", path, e)
        result = repo.create_file(path, message, b64, branch=branch)
        print("created", path, "new_sha", result["content"].sha, "new_size", result["content"].size)

root = os.path.dirname(os.path.abspath(__file__))
sales_path = os.path.join(root, "knighttrader-coinbase", "hermes-setup-coinbase-buy.html")
tutorial_path = os.path.join(root, "hermes-coinbase-setup.html")

sales_data = read_file(sales_path)
tutorial_data = read_file(tutorial_path)

print("local sales size:", len(sales_data), "lines:", sales_data.decode("utf-8", "replace").count("\n") + 1)
print("local tutorial size:", len(tutorial_data), "lines:", tutorial_data.decode("utf-8", "replace").count("\n") + 1)

ktc = g.get_repo("mknight2690-sys/knighttrader-coinbase")
ppb = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

force_update(ktc, "hermes-setup-coinbase-buy.html", sales_data, "Force rewrite sales page with local formatted HTML", "master")
force_update(ppb, "docs/hermes-coinbase-setup.html", tutorial_data, "Force rewrite tutorial with local formatted HTML", "main")

# Add .nojekyll to both repos to prevent Jekyll from interfering
for repo, path, message in [
    (ktc, ".nojekyll", "Add .nojekyll to disable Jekyll processing"),
    (ppb, "docs/.nojekyll", "Add .nojekyll to disable Jekyll processing in docs"),
]:
    try:
        repo.get_contents(path)
        print(".nojekyll already exists in", path)
    except Exception:
        repo.create_file(path, message, "", branch=repo.default_branch)
        print("created .nojekyll in", path)

print("DONE")
