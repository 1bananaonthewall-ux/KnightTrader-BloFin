import os
import base64
import json
import urllib.request
import urllib.error
import time

TOK = open(r"C:\Users\mknig\OneDrive\Documents\Github Token All Repos Everything.txt", "r", encoding="utf-8").read().strip()
REPO = "mknight2690-sys/Polly-Poly-Bot"
BRANCH = "main"
VIDEO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_videos")

def gh(url, data=None, method=None):
    hdrs = {
        "Authorization": "Bearer " + TOK,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return {"error": e.code, "body": body}
    except Exception as e:
        return {"error": repr(e)}

def main():
    mp4_files = sorted([f for f in os.listdir(VIDEO_ROOT) if f.endswith(".mp4")])
    print("found", len(mp4_files), "mp4 files")
    for filename in mp4_files:
        local_path = os.path.join(VIDEO_ROOT, filename)
        repo_path = f"docs/video/{filename}"
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        url = f"https://api.github.com/repos/{REPO}/contents/{repo_path}?ref={BRANCH}"
        meta = gh(url)
        sha = meta.get("sha") if isinstance(meta, dict) and meta.get("type") == "file" else None
        payload = json.dumps({
            "message": f"Add {filename}",
            "content": b64,
            "branch": BRANCH,
            **({"sha": sha} if sha else {}),
        }).encode("utf-8")
        r = gh(f"https://api.github.com/repos/{REPO}/contents/{repo_path}", data=payload, method="PUT")
        if isinstance(r, dict) and r.get("content"):
            print("uploaded", filename, r["content"].get("html_url"))
        else:
            print("upload failed", filename, r)
        time.sleep(0.5)
    print("DONE")

if __name__ == "__main__":
    main()
