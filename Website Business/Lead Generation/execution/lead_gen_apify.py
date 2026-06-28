#!/usr/bin/env python3
"""Lead Generation System
Scrapes Google Maps via Apify, filters businesses without websites,
and exports to CSV.
"""

from __future__ import annotations

import os
import csv
import time
import sys
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
ACTOR_ID = "compass~crawler-google-places"

CSV_FIELDS = [
    "Business Name",
    "Phone",
    "Category",
    "Location",
    "Services",
    "Main Colors",
]


# ---------------------------------------------------------------------------
# Apify helpers
# ---------------------------------------------------------------------------

def start_actor_run(search_query: str, max_results: int) -> tuple[str, str]:
    """Start the Apify Google Maps Scraper actor and return (run_id, dataset_id)."""
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
    payload = {
        "searchStringsArray": [search_query],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "includeReviews": False,
        "includeImages": True,
    }
    resp = requests.post(url, params={"token": APIFY_TOKEN}, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()["data"]
    return data["id"], data["defaultDatasetId"]


def wait_for_run(run_id: str, poll_interval: int = 8) -> None:
    """Poll until the actor run finishes. Raises on failure."""
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs/{run_id}"
    terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
    while True:
        resp = requests.get(url, params={"token": APIFY_TOKEN}, timeout=15)
        resp.raise_for_status()
        status = resp.json()["data"]["status"]
        print(f"  Run status: {status}", end="\r", flush=True)
        if status in terminal:
            print()
            if status != "SUCCEEDED":
                raise RuntimeError(f"Apify actor run ended with status: {status}")
            return
        time.sleep(poll_interval)


def fetch_dataset(dataset_id: str) -> list[dict]:
    """Download all items from an Apify dataset."""
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    resp = requests.get(
        url,
        params={"token": APIFY_TOKEN, "format": "json", "clean": "true"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def build_location(business: dict) -> str:
    """Assemble a full address string from available fields."""
    if business.get("address"):
        return business["address"]
    parts = [
        business.get("street", ""),
        business.get("city", ""),
        business.get("state", ""),
        business.get("postalCode", ""),
        business.get("countryCode", ""),
    ]
    combined = ", ".join(p for p in parts if p)
    return combined or "N/A"


def build_category(business: dict) -> str:
    """Return the primary business category."""
    return business.get("categoryName") or "N/A"


def build_services(business: dict) -> str:
    """Return all business categories joined, or description as fallback."""
    cats = business.get("categories") or []
    if isinstance(cats, list) and cats:
        return ", ".join(cats)
    return business.get("description") or "N/A"


def build_logo(business: dict) -> str:
    """Return the first available image URL for the business."""
    url = business.get("imageUrl") or ""
    if not url:
        images = business.get("images") or []
        if images:
            first = images[0]
            url = first.get("imageUrl") or first.get("url") or ""
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
    """Extract all required fields from one Apify record."""
    name = business.get("title", "N/A") or "N/A"
    print(f"  [{idx}/{total}] {name}")
    logo = build_logo(business)
    return {
        "Business Name": name,
        "Phone": business.get("phone") or business.get("phoneUnformatted") or "N/A",
        "Category": build_category(business),
        "Location": build_location(business),
        "Services": build_services(business),
        "Main Colors": extract_main_colors(logo),
    }


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
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not APIFY_TOKEN:
        sys.exit(
            "Error: APIFY_API_TOKEN is not set.\n"
            "Copy .env.example → .env and add your token."
        )

    print("=" * 40)
    print("   Lead Generation System")
    print("=" * 40)
    niche = input("Business niche  (e.g. plumbers, hair salons): ").strip()
    location = input("Location        (e.g. Houston TX, Chicago):    ").strip()
    max_results = int(input("Max results to scrape:                       ").strip())

    search_query = f"{niche} in {location}"
    print(f"\nSearching Apify for: \"{search_query}\"")

    run_id, dataset_id = start_actor_run(search_query, max_results)
    print(f"Actor run started (ID: {run_id}) — waiting for completion...")
    wait_for_run(run_id)

    print("Fetching results...")
    businesses = fetch_dataset(dataset_id)
    print(f"Total businesses found: {len(businesses)}")

    no_website = [b for b in businesses if not b.get("website")]
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
    filepath = os.path.join(outputs_dir, filename)
    save_csv(leads, filepath)
    print(f"\nDone! Import \"{filename}\" into Google Sheets.")
    print("File → Import → Upload → Replace current sheet.")


if __name__ == "__main__":
    main()
