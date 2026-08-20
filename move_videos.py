import os
import base64
from github import Github

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
g = Github(TOK)
repo = g.get_repo("mknight2690-sys/Polly-Poly-Bot")

video_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_videos")
mp4_files = sorted([f for f in os.listdir(video_root) if f.endswith(".mp4")])

# Create new folder
try:
    repo.get_contents("docs/walkthrough-videos")
except Exception:
    repo.create_file("docs/walkthrough-videos/.gitkeep", "Add walkthrough videos folder", "", branch="main")
    print("created docs/walkthrough-videos/")

for filename in mp4_files:
    path = os.path.join(video_root, filename)
    with open(path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")
    
    new_path = f"docs/walkthrough-videos/{filename}"
    try:
        existing = repo.get_contents(new_path, ref="main")
        repo.update_file(new_path, f"Move {filename} to walkthrough-videos/", content_b64, existing.sha, branch="main")
    except Exception as e:
        repo.create_file(new_path, f"Move {filename} to walkthrough-videos/", content_b64, branch="main")
    print(f"uploaded {filename}")

# Delete old files
for filename in mp4_files:
    old_path = f"docs/video/{filename}"
    try:
        existing = repo.get_contents(old_path, ref="main")
        repo.delete_file(old_path, f"Remove {filename} from video/", existing.sha, branch="main")
        print(f"deleted {old_path}")
    except Exception as e:
        print(f"skip delete {old_path}: {e}")

print("DONE")
