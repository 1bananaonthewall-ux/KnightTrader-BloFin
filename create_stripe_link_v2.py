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
    print("Creating payment link...")
    payload = {
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": "KnightTrader Walkthru - Hermes on Coinbase Setup Guide",
        "line_items[0][price_data][unit_amount]": "4700",
        "line_items[0][quantity]": "1",
    }
    r = stripe("/v1/payment_links", payload)
    print("status:", r["status"])
    body = r.get("body", {})
    print("url:", body.get("url"))
    print("id:", body.get("id"))
    print("error:", json.dumps(body.get("error", {}), indent=2))
    
    if r["status"] != 200 or not body.get("url"):
        print("\nChecking existing prices...")
        r2 = stripe("/v1/prices", {"limit": 10, "active": "true"})
        prices = r2.get("body", {}).get("data", [])
        for p in prices:
            print("price:", p.get("id"), p.get("unit_amount"), p.get("currency"), p.get("product"))
        
        if prices:
            price_id = prices[0]["id"]
            print(f"\nCreating payment link with existing price {price_id}...")
            payload2 = {
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
            }
            r3 = stripe("/v1/payment_links", payload2)
            print("status:", r3["status"])
            body3 = r3.get("body", {})
            print("url:", body3.get("url"))
            print("id:", body3.get("id"))
            print("error:", json.dumps(body3.get("error", {}), indent=2))

if __name__ == "__main__":
    main()
