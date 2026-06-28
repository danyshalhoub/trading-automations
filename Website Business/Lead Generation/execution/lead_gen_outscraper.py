#!/usr/bin/env python3
"""Lead Generation System — Outscraper variant
Scrapes Google Maps via Outscraper (~10x more free credits than Apify),
filters businesses without websites, and exports to CSV in the outputs/ folder.

Use this when Apify credits run out. Switch back with lead_gen_apify.py.
"""

from __future__ import annotations

import os
import csv
import sys
from io import BytesIO

import requests
from dotenv import load_dotenv
from outscraper import ApiClient
from PIL import Image

load_dotenv()

OUTSCRAPER_KEY = os.getenv("OUTSCRAPER_API_KEY")

CSV_FIELDS = [
    "Business Name",
    "Phone",
    "Category",
    "Location",
    "Services",
    "Main Colors",
]


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def save_csv(leads: list[dict], filepath: str) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(leads)
    print(f"\nSaved {len(leads)} leads → {filepath}")


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def build_category(business: dict) -> str:
    """Return the primary business category."""
    return business.get("type") or "N/A"


def build_services(business: dict) -> str:
    """Return subtypes joined, or primary type as fallback."""
    subtypes = business.get("subtypes") or []
    if isinstance(subtypes, list) and subtypes:
        return ", ".join(subtypes)
    return business.get("type") or business.get("description") or "N/A"


def build_logo(business: dict) -> str:
    """Return the first available image URL for the business."""
    url = business.get("imageUrl") or ""
    if not url:
        photos = business.get("photos") or business.get("images") or []
        if photos:
            first = photos[0]
            url = first.get("url") or first.get("imageUrl") or ""
    return url or "N/A"


def extract_main_colors(image_url: str, num_colors: int = 3) -> str:
    """Download image and return the top dominant colors as hex codes."""
    if not image_url or image_url == "N/A":
        return "N/A"
    try:
        resp = requests.get(image_url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB").resize((100, 100))
        quantized = img.quantize(colors=num_colors)
        palette = quantized.getpalette()
        hexes = [
            f"#{palette[i * 3]:02X}{palette[i * 3 + 1]:02X}{palette[i * 3 + 2]:02X}"
            for i in range(num_colors)
        ]
        return ", ".join(hexes)
    except Exception:
        return "N/A"


def process_business(business: dict, idx: int, total: int) -> dict:
    """Extract all required fields from one Outscraper record."""
    name = business.get("name") or "N/A"
    print(f"  [{idx}/{total}] {name}")
    logo = build_logo(business)
    return {
        "Business Name": name,
        "Phone": business.get("phone") or "N/A",
        "Category": build_category(business),
        "Location": business.get("full_address") or "N/A",
        "Services": build_services(business),
        "Main Colors": extract_main_colors(logo),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not OUTSCRAPER_KEY or OUTSCRAPER_KEY == "your_outscraper_key_here":
        sys.exit(
            "Error: OUTSCRAPER_API_KEY is not set.\n"
            "Get your key at https://app.outscraper.com/profile and add it to .env"
        )

    print("=" * 40)
    print("   Lead Generation System (Outscraper)")
    print("=" * 40)
    niche = input("Business niche  (e.g. plumbers, hair salons): ").strip()
    location = input("Location        (e.g. Houston TX, Chicago):    ").strip()
    max_results = int(input("Max results to scrape:                       ").strip())

    search_query = f"{niche} in {location}"
    print(f"\nSearching Outscraper for: \"{search_query}\"")

    client = ApiClient(api_key=OUTSCRAPER_KEY)
    raw = client.google_maps_search(search_query, limit=max_results, language="en")

    # Outscraper returns a list-of-lists (one inner list per query string)
    businesses = raw[0] if raw else []
    print(f"Total businesses found: {len(businesses)}")

    no_website = [b for b in businesses if not b.get("site")]
    print(f"Businesses without a website: {len(no_website)}")

    if not no_website:
        print("No leads without websites found. Try a broader niche or different location.")
        return

    print("\nProcessing leads...")
    leads = [
        process_business(biz, i + 1, len(no_website))
        for i, biz in enumerate(no_website)
    ]

    safe = lambda s: s.lower().replace(" ", "_").replace(",", "")
    filename = f"leads_{safe(niche)}_{safe(location)}.csv"
    outputs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    save_csv(leads, os.path.join(outputs_dir, filename))
    print(f"\nDone! Import \"{filename}\" into Google Sheets.")
    print("File → Import → Upload → Replace current sheet.")


if __name__ == "__main__":
    main()
