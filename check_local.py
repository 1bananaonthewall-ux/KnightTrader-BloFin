import os

for path in [
    r"C:\Users\mknig\hermes-trader\knighttrader-coinbase\hermes-setup-coinbase-buy.html",
    r"C:\Users\mknig\hermes-trader\hermes-coinbase-setup.html",
]:
    print("\nFILE", path)
    with open(path, "rb") as f:
        data = f.read()
    text = data.decode("utf-8", "replace")
    print("size:", len(data))
    print("line_count:", text.count("\n") + 1)
    print("HEAD:\n", text[:500])
    print("TAIL:\n", text[-500:])
