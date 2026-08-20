import os
import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

# Remove docs/.nojekyll if it exists
try:
    existing = repo.get_contents("docs/.nojekyll", ref="main")
    repo.delete_file("docs/.nojekyll", "Remove docs/.nojekyll to restore Pages asset serving", existing.sha, branch="main")
    print("removed docs/.nojekyll")
except Exception as e:
    print("no docs/.nojekyll to remove:", e)

# Move videos from docs/video/ to root video/
video_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_videos")
mp4_files = sorted([f for f in os.listdir(video_root) if f.endswith(".mp4")])
print(f"found {len(mp4_files)} mp4 files to move")

# Create video/ directory at root if needed
try:
    repo.get_contents("video")
except Exception:
    repo.create_file("video/.gitkeep", "Add video directory at root for Pages", "", branch="main")
    print("created video/ at root")

for filename in mp4_files:
    src_path = os.path.join(video_root, filename)
    with open(src_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")
    
    root_path = f"video/{filename}"
    try:
        existing = repo.get_contents(root_path, ref="main")
        print(f"updating {root_path}")
        repo.update_file(root_path, f"Move {filename} to root video/ for Pages", content_b64, existing.sha, branch="main")
    except Exception as e:
        print(f"creating {root_path}")
        repo.create_file(root_path, f"Move {filename} to root video/ for Pages", content_b64, branch="main")

print("DONE")
