"""
us_probe.py - READ-ONLY probe for Polymarket US.

Places NO orders. Prints what the SDK offers and what BTC 15-minute
markets look like, so the real bot can be built against real data.

Run on Render with start command:
    pip install polymarket-us && python us_probe.py
"""
import os
import sys
import json
import time
import importlib.metadata


def show(title, obj, limit=1500):
    print(f"\n--- {title} ---")
    try:
        text = json.dumps(obj, indent=2, default=str)
    except Exception:
        text = repr(obj)
    print(text[:limit] + ("\n... [truncated]" if len(text) > limit else ""))
    sys.stdout.flush()


def public_methods(obj):
    return [n for n in dir(obj) if not n.startswith("_")]


def extract_items(res):
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("markets", "events", "data", "results", "items"):
            if isinstance(res.get(k), list):
                return res[k]
    return []


def try_calls(label, fn, variants):
    for args, kwargs in variants:
        try:
            res = fn(*args, **kwargs)
            print(f"{label}: OK with args={args} kwargs={kwargs}")
            return res
        except Exception as e:
            print(f"{label}: failed args={args} kwargs={kwargs} -> "
                  f"{type(e).__name__}: {str(e)[:200]}")
    return None


def main():
    try:
        version = importlib.metadata.version("polymarket-us")
    except Exception:
        version = "unknown"
    print(f"polymarket-us version: {version}")

    from polymarket_us import PolymarketUS

    key_id = os.getenv("POLYMARKET_US_KEY_ID")
    secret = os.getenv("POLYMARKET_US_SECRET_KEY")
    if key_id and secret:
        client = PolymarketUS(key_id=key_id, secret_key=secret)
        print("auth: yes (keys found)")
    else:
        client = PolymarketUS()
        print("auth: no (public endpoints only)")

    # 1. What does the SDK offer?
    show("client resources", public_methods(client))
    for name in ("events", "markets", "series", "orders", "search"):
        res = getattr(client, name, None)
        if res is not None:
            show(f"methods on client.{name}", public_methods(res))

    # 2. Try to list markets / events and look for BTC
    matches = []
    for name in ("markets", "events"):
        res = getattr(client, name, None)
        if res is None or not hasattr(res, "list"):
            continue
        data = try_calls(
            f"{name}.list",
            res.list,
            [
                (({"limit": 100, "active": True, "closed": False},), {}),
                (({"limit": 100},), {}),
                ((), {}),
            ],
        )
        items = extract_items(data)
        print(f"{name}.list returned {len(items)} items")
        for item in items:
            blob = json.dumps(item, default=str).lower()
            if "btc" in blob or "bitcoin" in blob:
                matches.append((name, item))

    print(f"\nBTC-related items found: {len(matches)}")
    for name, item in matches[:15]:
        if isinstance(item, dict):
            print(f"  [{name}] slug={item.get('slug')} | "
                  f"title={item.get('title') or item.get('question') or item.get('name')}")
        else:
            print(f"  [{name}] {str(item)[:150]}")

    if matches:
        show("FIRST BTC ITEM (raw)", matches[0][1], limit=2500)

    # 3. Try the order book for the first 15-minute-looking slug
    slug = None
    for _, item in matches:
        if isinstance(item, dict):
            s = str(item.get("slug", ""))
            if "15" in s:
                slug = s
                break
    if slug is None and matches and isinstance(matches[0][1], dict):
        slug = matches[0][1].get("slug")

    if slug:
        print(f"\nTrying order book for slug: {slug}")
        try:
            book = client.markets.book(slug)
            show(f"order book for {slug}", book, limit=2000)
        except Exception as e:
            print(f"book failed: {type(e).__name__}: {str(e)[:300]}")
    else:
        print("\nNo BTC slug found, skipping order book test.")

    print("\n=== PROBE DONE. Copy the output above, then SUSPEND the service. ===")
    sys.stdout.flush()
    # Sleep so Render doesn't restart-loop and reprint everything.
    time.sleep(86400)


if __name__ == "__main__":
    main()
