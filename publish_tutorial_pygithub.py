import base64, os
from github import Github, GithubException

TOK = "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"

def main():
    g = Github(TOK)
    root = os.path.dirname(os.path.abspath(__file__))

    tutorial_local = os.path.join(root, "hermes-coinbase-setup.html")
    with open(tutorial_local, "rb") as f:
        tutorial_b64 = base64.b64encode(f.read()).decode("ascii")

    repo_ppb = g.get_repo("mknight2690-sys/Polly-Poly-Bot")
    branch_ppb = repo_ppb.default_branch
    print("default_branch:", branch_ppb)

    path = "docs/hermes-coinbase-setup.html"
    try:
        existing = repo_ppb.get_contents(path, ref=branch_ppb)
        print("existing file sha:", existing.sha)
        result = repo_ppb.update_file(
            path,
            "Add Hermes on Coinbase beginner tutorial (Windows & Mac)",
            tutorial_b64,
            existing.sha,
            branch=branch_ppb,
        )
        print("update_file result:", result)
    except GithubException as e:
        print("get/update exception:", e.data)
        if e.status == 404:
            print("creating new file instead")
            result = repo_ppb.create_file(
                path,
                "Add Hermes on Coinbase beginner tutorial (Windows & Mac)",
                tutorial_b64,
                branch=branch_ppb,
            )
            print("create_file result:", result)
        else:
            raise

if __name__ == "__main__":
    main()
