"""
ReceiptGG price scraper — structure-based version.

Pulls product name + price from Star Tech (startech.com.bd) category pages
across every major PC component + peripheral category, and writes the
results to data/prices.json.

Run manually:   python scripts/scrape_prices.py
Run automatically: see .github/workflows/scrape.yml (runs once a day for free)

WHY THIS VERSION IS DIFFERENT:
Earlier versions guessed CSS class names (like ".product-thumb") based on
a generic OpenCart theme. Star Tech's actual theme uses different class
names, so that version found 0 products everywhere even though the pages
loaded fine. This version instead looks for the *pattern* every product
follows on the page — a heading (<h4>) containing a link to a product,
with a Taka ("৳") price nearby in the same block — rather than a specific
class name. This is more resilient to theme differences, though still not
bulletproof.

IMPORTANT — read before relying on this:
- Scraping may be against a retailer's Terms of Service even when the page
  is public. Keep the request rate low (this script already adds a delay
  between requests) and consider reaching out to the retailer if you plan
  to run this at any real scale.
- If results look wrong (missing items, wrong prices), the site's HTML
  structure may have changed again — see the README for how to debug.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ReceiptGG-PriceBot/1.0; contact: youremail@example.com)"
}

# Category key -> Star Tech category URL.
# Keys here must match CATEGORY_LABELS in builder.html's JS.
CATEGORIES = {
    "processor": "https://www.startech.com.bd/component/processor",
    "graphics-card": "https://www.startech.com.bd/component/graphics-card",
    "motherboard": "https://www.startech.com.bd/component/motherboard",
    "ram": "https://www.startech.com.bd/component/ram",
    "ssd": "https://www.startech.com.bd/ssd",
    "power-supply": "https://www.startech.com.bd/component/power-supply",
    "casing": "https://www.startech.com.bd/component/casing",
    "monitor": "https://www.startech.com.bd/monitor",
    "keyboard": "https://www.startech.com.bd/accessories/keyboards",
    "mouse": "https://www.startech.com.bd/accessories/mouse",
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "prices.json"
MAX_ITEMS_PER_CATEGORY = 40
REQUEST_DELAY_SECONDS = 2  # be polite — don't hammer the site
PRICE_PATTERN = re.compile(r"([\d,]+)\s*৳")


def scrape_category(url: str) -> list[dict]:
    """Scrape one Star Tech category page (page 1 only) and return a list
    of {name, price_bdt, url} dicts. Returns an empty list on any failure
    so one broken category never crashes the whole run."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [!] request failed for {url}: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    seen = set()

    # Every product on a Star Tech listing page has its name in an <h4>
    # containing a link to the product page. We find every such heading,
    # then look for a nearby Taka price by walking up a few ancestor
    # levels (the smallest ancestor that contains a price is almost
    # always this product's own card, not a neighboring one).
    for h4 in soup.find_all("h4"):
        link = h4.find("a", href=True)
        if not link:
            continue

        name = link.get_text(strip=True)
        href = link["href"]
        if not name or len(name) < 5 or href in seen:
            continue

        price_bdt = None
        node = h4
        for _ in range(4):
            node = node.parent
            if node is None:
                break
            match = PRICE_PATTERN.search(node.get_text(" ", strip=True))
            if match:
                price_bdt = int(match.group(1).replace(",", ""))
                break

        if price_bdt is None:
            continue

        seen.add(href)
        items.append({
            "name": name,
            "price_bdt": price_bdt,
            "url": href,
        })

        if len(items) >= MAX_ITEMS_PER_CATEGORY:
            break

    return items


def main():
    all_data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "startech.com.bd",
        "categories": {},
    }

    for category, url in CATEGORIES.items():
        print(f"Scraping {category} from {url} ...")
        items = scrape_category(url)
        print(f"  -> found {len(items)} items")
        all_data["categories"][category] = items
        time.sleep(REQUEST_DELAY_SECONDS)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(all_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
