import os
import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)

repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")
video_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_videos")

# Ensure videos directory exists
try:
    repo.get_contents("docs/video")
except Exception:
    repo.create_file("docs/video/.gitkeep", "Add video directory", "", branch="main")
    print("created docs/video/")

mp4_files = sorted([f for f in os.listdir(video_root) if f.endswith(".mp4")])
print(f"found {len(mp4_files)} mp4 files")

for filename in mp4_files:
    path = os.path.join(video_root, filename)
    with open(path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")
    
    github_path = f"docs/video/{filename}"
    try:
        existing = repo.get_contents(github_path, ref="main")
        print(f"updating {filename} (sha={existing.sha})")
        repo.update_file(github_path, f"Add {filename} video", content_b64, existing.sha, branch="main")
    except Exception as e:
        print(f"creating {filename}")
        repo.create_file(github_path, f"Add {filename} video", content_b64, branch="main")

print("DONE")
