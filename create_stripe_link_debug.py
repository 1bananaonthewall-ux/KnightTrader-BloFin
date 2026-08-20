import urllib.request, urllib.parse, json, ssl

SECRET_KEY = open(r"C:\Users\mknig\OneDrive\Documents\Stripe Secret Key.txt", "r", encoding="utf-8").read().strip()
BACKUP_KEY = open(r"C:\Users\mknig\OneDrive\Documents\Stripe Backup Code.txt", "r", encoding="utf-8").read().strip()

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
    payload = {
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": "KnightTrader Walkthru - Hermes on Coinbase Setup Guide",
        "line_items[0][price_data][unit_amount]": "4700",
        "line_items[0][quantity]": "1",
        "mode": "payment",
    }
    print("Primary key debug:")
    r = stripe("/v1/payment_links", payload)
    print("status:", r["status"])
    print("body:", json.dumps(r.get("body", {}), indent=2))
    
    print("\nBackup key debug:")
    r = stripe("/v1/payment_links", payload, key=BACKUP_KEY)
    print("status:", r["status"])
    print("body:", json.dumps(r.get("body", {}), indent=2))

if __name__ == "__main__":
    main()
