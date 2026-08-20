import os
from github import Github

tok_path = r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt"
with open(tok_path, "r", encoding="utf-8") as f:
    tok = f.read().strip()

print("TOKEN_LEN", len(tok))
g = Github(tok)
user = g.get_user()
print("USER", user.login)
print("AUTH_OK")
