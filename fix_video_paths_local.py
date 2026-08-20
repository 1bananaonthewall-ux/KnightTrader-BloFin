import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermes-coinbase-setup.html")
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

# The page lives at docs/hermes-coinbase-setup.html.
# videos are at docs/video/, so relative path is video/ not docs/video/
html = html.replace('src="docs/video/', 'src="video/')
html = html.replace("src='docs/video/", "src='video/")

with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("fixed local video paths to video/")
