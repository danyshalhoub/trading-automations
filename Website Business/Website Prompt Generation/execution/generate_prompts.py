#!/usr/bin/env python3
"""Website Prompt Generation
Reads a CSV of business leads and writes one personalized website-AI prompt
per business to the outputs/ folder.
"""

from __future__ import annotations

import csv
import os
import sys

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """\
You are an elite conversion-focused web designer and copywriter.

Create a clean, modern, high-converting landing page for a local business using ONLY the information provided below.

The goal is to make visitors immediately:
1. Understand what the business does
2. Trust the business
3. Contact the business quickly

Do NOT overcomplicate the design.
Keep it simple, professional, mobile-friendly, and conversion-focused.

BUSINESS INFORMATION:
Business Name: {business_name}
Phone: {phone}
Category: {category}
Location: {location}
Services: {services}
Main Colors: {main_colors}

IMPORTANT RULES:
- Use the business category and services to intelligently generate realistic copy
- Make the business sound trustworthy, professional, and established
- Do not use generic AI wording
- Keep paragraphs short and readable
- Prioritize mobile responsiveness
- Make the phone number highly visible
- Include multiple call-to-action buttons
- Use strong spacing and visual hierarchy
- Design should feel premium but simple
- Fast-loading layout only
- Avoid clutter
- Never use em dashes (—) anywhere in the website text

REQUIRED SECTIONS:

1. HERO SECTION
- Strong headline focused on customer benefit
- Short supporting text
- Large call button using the phone number
- A real photograph will be placed as a full-width background image in the hero section, faded behind the text with a semi-transparent dark overlay so the text remains fully readable. Design the hero layout assuming this image is already provided — do not suggest a placeholder or generate an image URL.

2. SERVICES SECTION
- Clean cards or list of services
- Short benefit-focused descriptions

3. WHY CHOOSE US
Include 3-5 trust-focused points such as:
- Reliable service
- Fast response
- Professional quality
- Local expertise
- Customer satisfaction

4. SERVICE AREA
Mention the location naturally for local trust and SEO.

5. FINAL CTA SECTION
- Strong closing headline
- Repeat phone number
- Encourage immediate contact

6. FOOTER
- Business name
- Phone number
- Location
- Simple clean footer

DESIGN REQUIREMENTS:
- Modern UI
- Mobile-first
- React + Tailwind
- Clean typography
- Rounded cards/buttons
- Subtle shadows
- Professional color palette using the provided main colors
- Sticky mobile call button
- Clear spacing between sections
- Minimal but polished animations

COPYWRITING STYLE:
- Direct
- Clear
- Confident
- Benefit-focused
- No fluff
- No corporate jargon

OUTPUT:
Generate the complete landing page with:
- Full copy
- Layout structure
- Styling
- Responsive design
- Components
- CTA placement\
"""

# ---------------------------------------------------------------------------
# Column aliases — handles CSV variants from different lead sources
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, list[str]] = {
    "business_name": ["Business Name", "Company Name", "Name"],
    "phone":         ["Phone", "Phone Number"],
    "category":      ["Category", "Industry", "Type"],
    "location":      ["Location", "Address", "City"],
    "services":      ["Services", "Service", "Services Offered"],
}

# ---------------------------------------------------------------------------
# Category color defaults
# ---------------------------------------------------------------------------

CATEGORY_COLORS: list[tuple[str, str]] = [
    ("plumb",                    "#1A6DB5, #F0F4F8"),
    ("electric",                 "#F5A623, #1A1A2E"),
    ("hvac",                     "#2E86AB, #F5F5F5"),
    ("heat",                     "#2E86AB, #F5F5F5"),
    ("cool",                     "#2E86AB, #F5F5F5"),
    ("air condition",            "#2E86AB, #F5F5F5"),
    ("roof",                     "#8B1A1A, #F5F0EB"),
    ("landscap",                 "#2D6A4F, #F8FFF4"),
    ("lawn",                     "#2D6A4F, #F8FFF4"),
    ("garden",                   "#2D6A4F, #F8FFF4"),
    ("clean",                    "#0077B6, #EAF4FB"),
    ("pest",                     "#4A7C59, #F5F5DC"),
    ("restaurant",               "#C0392B, #FFF8F0"),
    ("food",                     "#C0392B, #FFF8F0"),
    ("pizza",                    "#C0392B, #FFF8F0"),
    ("cafe",                     "#C0392B, #FFF8F0"),
    ("salon",                    "#C06B8A, #FFF0F5"),
    ("spa",                      "#C06B8A, #FFF0F5"),
    ("beauty",                   "#C06B8A, #FFF0F5"),
    ("nail",                     "#C06B8A, #FFF0F5"),
    ("auto",                     "#2C3E50, #ECF0F1"),
    ("car",                      "#2C3E50, #ECF0F1"),
    ("mechanic",                 "#2C3E50, #ECF0F1"),
    ("tire",                     "#2C3E50, #ECF0F1"),
    ("dental",                   "#2980B9, #EAF4FB"),
    ("dentist",                  "#2980B9, #EAF4FB"),
    ("legal",                    "#1A1A2E, #F5F0E8"),
    ("attorney",                 "#1A1A2E, #F5F0E8"),
    ("lawyer",                   "#1A1A2E, #F5F0E8"),
    ("real estate",              "#1B4332, #F0F4F0"),
    ("realt",                    "#1B4332, #F0F4F0"),
]

DEFAULT_COLORS = "#2C3E50, #F5F5F5"

# ---------------------------------------------------------------------------
# Image stock — categories with available hero photos
# ---------------------------------------------------------------------------

IMAGE_STOCK: dict[str, int] = {
    "plumbing":    7,
    "roofing":     10,
    "solar panel": 10,
}

IMAGE_KEYWORDS: list[tuple[str, str]] = [
    ("plumb", "plumbing"),
    ("roof",  "roofing"),
    ("solar", "solar panel"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_row(raw_row: dict) -> dict[str, str]:
    """Map raw CSV columns to canonical field names using COLUMN_ALIASES."""
    result: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in raw_row and raw_row[alias].strip():
                result[canonical] = raw_row[alias].strip()
                break
        if canonical not in result:
            result[canonical] = "N/A"
    return result


def resolve_colors(category: str) -> str:
    """Return a color pair string based on category keywords."""
    lower = category.lower()
    for keyword, colors in CATEGORY_COLORS:
        if keyword in lower:
            return colors
    return DEFAULT_COLORS


def slugify(name: str) -> str:
    """Convert a business name to a safe filename slug."""
    slug = name.lower().strip().replace("'", "").replace('"', "")
    for ch in (" ", "/", "\\", ":", "*", "?", "<", ">", "|", ",", "."):
        slug = slug.replace(ch, "_")
    # Collapse consecutive underscores
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "business"


def unique_slug(slug: str, used: set[str]) -> str:
    """Append a numeric suffix if the slug has already been used."""
    candidate = slug
    counter = 2
    while candidate in used:
        candidate = f"{slug}_{counter}"
        counter += 1
    return candidate


def resolve_image_type(category: str) -> str | None:
    """Return the image type key for a category, or None if not in stock."""
    lower = category.lower()
    for keyword, img_type in IMAGE_KEYWORDS:
        if keyword in lower:
            return img_type
    return None


def assign_image(category: str, location: str, image_state: dict) -> str | None:
    """Return a hero image recommendation like 'plumbing 4', or None.

    Diversification rules:
    - Same (type + location) companies never repeat a number (up to stock limit).
    - A global counter per type advances across all companies for cross-location spread.
    """
    img_type = resolve_image_type(category)
    if img_type is None:
        return None
    max_images = IMAGE_STOCK[img_type]
    loc_key = location.lower().strip()

    loc_used: list[int] = image_state.setdefault(("loc", img_type, loc_key), [])
    global_next: int = image_state.get(("global", img_type), 1)

    # Find the first candidate (starting from global_next) unused in this location.
    candidate = None
    for offset in range(max_images):
        num = (global_next - 1 + offset) % max_images + 1
        if num not in loc_used:
            candidate = num
            break

    if candidate is None:
        # All images exhausted for this location — fall back to global counter.
        candidate = global_next

    loc_used.append(candidate)
    image_state[("global", img_type)] = global_next % max_images + 1
    return f"{img_type} {candidate}"


def fill_template(row: dict[str, str]) -> str:
    """Return the prompt with all placeholders replaced by business data."""
    colors = resolve_colors(row["category"])
    return PROMPT_TEMPLATE.format(
        business_name=row["business_name"],
        phone=row["phone"],
        category=row["category"],
        location=row["location"],
        services=row["services"],
        main_colors=colors,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 50)
    print("   Website Prompt Generation")
    print("=" * 50)

    csv_path = input("Path to input CSV file: ").strip().strip('"').strip("'")
    if not os.path.isfile(csv_path):
        sys.exit(f"Error: file not found — {csv_path}")

    outputs_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "outputs"
    )
    os.makedirs(outputs_dir, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    if total == 0:
        sys.exit("Error: CSV is empty or has no data rows.")

    print(f"\nProcessing {total} businesses...\n")

    used_slugs: set[str] = set()
    image_state: dict = {}
    succeeded = 0
    failed = 0

    for i, raw_row in enumerate(rows, start=1):
        try:
            row = normalize_row(raw_row)
            prompt_text = fill_template(row)
            image_rec = assign_image(row["category"], row["location"], image_state)

            base_slug = slugify(row["business_name"])
            slug = unique_slug(base_slug, used_slugs)
            used_slugs.add(slug)

            out_path = os.path.join(outputs_dir, f"{slug}.txt")
            with open(out_path, "w", encoding="utf-8") as out_f:
                if image_rec:
                    out_f.write(f"HERO IMAGE: {image_rec}\n")
                    out_f.write("─" * 42 + "\n\n")
                out_f.write(prompt_text)

            image_label = f"  |  Hero image: {image_rec}" if image_rec else ""
            print(f"  [{i}/{total}] Generated prompt for {row['business_name']}{image_label}")
            succeeded += 1

        except Exception as exc:
            print(f"  [{i}/{total}] ERROR — {raw_row}: {exc}")
            failed += 1

    print(f"\nDone. {succeeded} succeeded, {failed} failed.")
    print(f"Prompts saved to: {os.path.abspath(outputs_dir)}")


if __name__ == "__main__":
    main()
