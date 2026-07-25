"""
ReceiptGG price scraper — full component coverage.

Pulls product name + price from Star Tech (startech.com.bd) category pages
across every major PC component + peripheral category, and writes the
results to data/prices.json.

Run manually:   python scripts/scrape_prices.py
Run automatically: see .github/workflows/scrape.yml (runs once a day for free)

IMPORTANT — read before relying on this:
- This scrapes public HTML. Retailer sites can change their page layout at
  any time, which will silently break the CSS selectors below. If prices
  stop updating, the first thing to check is whether the selectors still
  match the live page (open the category page, right-click a product,
  "Inspect", and compare against SELECTORS below).
- Scraping may be against a retailer's Terms of Service even when the page
  is public. Keep the request rate low (this script already adds a delay
  between requests) and consider reaching out to the retailer if you plan
  to run this at any real scale.
"""

import json
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


def scrape_category(url: str) -> list[dict]:
    """Scrape one Star Tech category page (page 1 only) and return a list
    of {name, price, url} dicts. Returns an empty list on any failure so
    one broken category never crashes the whole run."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [!] request failed for {url}: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []

    # Star Tech (OpenCart-based theme) typically wraps each product in a
    # container with a "product-thumb" class. If this stops matching,
    # inspect the live page and update the selector.
    products = soup.select(".product-thumb") or soup.select(".product-layout")

    for product in products[:MAX_ITEMS_PER_CATEGORY]:
        name_tag = product.select_one(".caption h4 a") or product.select_one("h4 a")
        price_tag = product.select_one(".price-new") or product.select_one(".price")

        if not name_tag or not price_tag:
            continue

        name = name_tag.get_text(strip=True)
        price_text = price_tag.get_text(strip=True)
        # Keep only digits/commas from the price text, e.g. "54,200৳" -> "54,200"
        price_digits = "".join(ch for ch in price_text if ch.isdigit() or ch == ",")

        if not price_digits:
            continue

        items.append({
            "name": name,
            "price_bdt": int(price_digits.replace(",", "")),
            "url": name_tag.get("href", ""),
        })

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
