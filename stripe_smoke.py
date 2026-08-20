import urllib.request, urllib.parse, json, ssl

SECRET_KEY = open(r"C:\Users\mknig\OneDrive\Documents\Stripe Secret Key.txt", "r", encoding="utf-8").read().strip()

def stripe(path, payload, key=None):
    url = "https://api.stripe.com" + path
    headers = {"Authorization": "Bearer " + (key or SECRET_KEY)}
    data = urllib.parse.urlencode(payload).encode("utf-8")
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, timeout=40, context=ctx)
        body = json.loads(resp.read().decode("utf-8"))
        return {"status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8", "replace"))
        return {"status": e.code, "body": body}
    except Exception as e:
        return {"status": None, "body": {"error": str(e)}}

print("account...")
r = stripe("/v1/account", {})
print("status", r["status"])
print("body", json.dumps(r.get("body", {}), indent=2)[:1000])
