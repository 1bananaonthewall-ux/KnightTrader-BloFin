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
    # Step 1: create product
    print("Creating product...")
    r = stripe("/v1/products", {"name": "KnightTrader Walkthru - Hermes on Coinbase Setup Guide", "description": "Complete beginner setup guide for Hermes on Coinbase with Windows and Mac walkthroughs."})
    print("product status:", r["status"])
    product = r.get("body", {})
    print("product id:", product.get("id"))
    
    if r["status"] != 200 or not product.get("id"):
        print("product error:", json.dumps(r.get("body", {}), indent=2))
        return
    
    # Step 2: create price
    print("\nCreating price...")
    r = stripe("/v1/prices", {"unit_amount": 4700, "currency": "usd", "product": product["id"]})
    print("price status:", r["status"])
    price = r.get("body", {})
    print("price id:", price.get("id"))
    
    if r["status"] != 200 or not price.get("id"):
        print("price error:", json.dumps(r.get("body", {}), indent=2))
        return
    
    # Step 3: create payment link
    print("\nCreating payment link...")
    payload = {
        "line_items[0][price]": price["id"],
        "line_items[0][quantity]": "1",
    }
    r = stripe("/v1/payment_links", payload)
    print("link status:", r["status"])
    body = r.get("body", {})
    print("url:", body.get("url"))
    print("id:", body.get("id"))
    print("error:", json.dumps(body.get("error", {}), indent=2))

if __name__ == "__main__":
    main()
