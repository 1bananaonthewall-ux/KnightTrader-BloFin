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

def main():
    print("Creating product...")
    r = stripe("/v1/products", {"name": "KnightTrader Walkthru - Hermes on Coinbase Setup Guide"})
    product = r.get("body", {})
    print("product:", product.get("id"))
    
    print("Creating price...")
    r = stripe("/v1/prices", {"unit_amount": 4700, "currency": "usd", "product": product["id"]})
    price = r.get("body", {})
    print("price:", price.get("id"))
    
    print("Creating payment link with return URLs...")
    success_url = "https://mknight2690-sys.github.io/knighttrader-coinbase/hermes-setup-coinbase-buy.html?success"
    cancel_url = "https://mknight2690-sys.github.io/knighttrader-coinbase/hermes-setup-coinbase-buy.html?cancel"
    payload = {
        "line_items[0][price]": price["id"],
        "line_items[0][quantity]": "1",
        "after_completion[type]": "redirect",
        "after_completion[redirect][url]": success_url,
    }
    r = stripe("/v1/payment_links", payload)
    print("status:", r["status"])
    body = r.get("body", {})
    print("url:", body.get("url"))
    print("id:", body.get("id"))
    if body.get("error"):
        print("error:", json.dumps(body["error"], indent=2))

if __name__ == "__main__":
    main()
