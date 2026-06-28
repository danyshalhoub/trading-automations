#!/usr/bin/env python3
"""Website Creation System
Reads a leads CSV (from the lead generation tool) and generates a complete
landing page folder (index.html + style.css) for each business.
"""

from __future__ import annotations

import csv
import datetime
import os
import re
import sys

# ---------------------------------------------------------------------------
# Column alias resolution (handles both old and new CSV schemas)
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, list[str]] = {
    "business_name": ["Business Name", "Company Name"],
    "phone":         ["Phone", "Phone Number"],
    "category":      ["Category"],
    "location":      ["Location", "Address"],
    "services":      ["Services", "What the Business Sells"],
    "main_colors":   ["Main Colors", "Main Color Scheme"],
}

# ---------------------------------------------------------------------------
# Industry configuration
# ---------------------------------------------------------------------------

INDUSTRY_CONFIG: dict[str, dict] = {
    "plumb": {
        "hero_headline_template": "Fast, Reliable Plumbing in {city}",
        "cta_primary": "Call Now",
        "cta_icon": "fa-phone",
        "trust_tagline": "Licensed and Local. Honest Work, Fair Prices.",
        "about_intro": "We're a locally owned plumbing company committed to fast response times, honest pricing, and work done right the first time.",
        "colors": {"primary": "#1B4F8A", "accent": "#F5A623", "bg": "#F4F6F9", "text": "#1A1A2E"},
        "service_icon_default": "fa-wrench",
        "highlights": ["Fast Emergency Response", "Licensed & Insured", "Upfront Pricing"],
    },
    "heat": {
        "hero_headline_template": "Expert Heating & HVAC Service in {city}",
        "cta_primary": "Call Now",
        "cta_icon": "fa-phone",
        "trust_tagline": "Fast Response. Stay Warm When It Matters Most.",
        "about_intro": "We keep homes and businesses comfortable year-round with expert heating, cooling, and ventilation service.",
        "colors": {"primary": "#C0392B", "accent": "#E67E22", "bg": "#FDF6F0", "text": "#1A1A2E"},
        "service_icon_default": "fa-fire",
        "highlights": ["24/7 Emergency Service", "Factory-Certified Technicians", "All Makes & Models"],
    },
    "air condition": {
        "hero_headline_template": "Professional AC & HVAC Service in {city}",
        "cta_primary": "Call Now",
        "cta_icon": "fa-phone",
        "trust_tagline": "Cool and Comfortable. Fast Local Service.",
        "about_intro": "We provide reliable air conditioning installation, repair, and maintenance to keep your space comfortable all year.",
        "colors": {"primary": "#2471A3", "accent": "#1ABC9C", "bg": "#EBF5FB", "text": "#1A1A2E"},
        "service_icon_default": "fa-snowflake",
        "highlights": ["Same-Day Diagnostics", "Energy-Efficient Systems", "Preventative Maintenance"],
    },
    "roof": {
        "hero_headline_template": "Trusted Roofing Contractors in {city}",
        "cta_primary": "Get Free Estimate",
        "cta_icon": "fa-clipboard-check",
        "trust_tagline": "Quality Roofing That Protects What Matters Most",
        "about_intro": "We're a roofing company built on safety, craftsmanship, and standing behind every job we complete.",
        "colors": {"primary": "#34495E", "accent": "#E74C3C", "bg": "#F2F3F4", "text": "#1A1A2E"},
        "service_icon_default": "fa-house-chimney",
        "highlights": ["Free Roof Inspections", "Storm Damage Experts", "Material Warranties"],
    },
    "landscap": {
        "hero_headline_template": "Beautiful Landscaping Services in {city}",
        "cta_primary": "Get Free Quote",
        "cta_icon": "fa-leaf",
        "trust_tagline": "Your Yard, Done Right. Every Time.",
        "about_intro": "We transform outdoor spaces with professional care, from routine lawn maintenance to complete landscape design.",
        "colors": {"primary": "#27AE60", "accent": "#F39C12", "bg": "#F0FDF4", "text": "#1A1A2E"},
        "service_icon_default": "fa-seedling",
        "highlights": ["Custom Landscape Design", "Seasonal Maintenance Plans", "Eco-Friendly Practices"],
    },
    "spa": {
        "hero_headline_template": "Premium Wellness & Med Spa in {city}",
        "cta_primary": "Book Consultation",
        "cta_icon": "fa-calendar-check",
        "trust_tagline": "Feel Your Best. Expert Care in a Relaxing Setting.",
        "about_intro": "We offer premium wellness and aesthetic treatments in a calm, professional environment focused entirely on your comfort.",
        "colors": {"primary": "#7D6B91", "accent": "#C9A96E", "bg": "#FAF7FF", "text": "#2D2D2D"},
        "service_icon_default": "fa-spa",
        "highlights": ["Personalized Treatment Plans", "Medical-Grade Equipment", "Trained Specialists"],
    },
    "salon": {
        "hero_headline_template": "Expert Hair & Beauty Services in {city}",
        "cta_primary": "Book Appointment",
        "cta_icon": "fa-calendar-check",
        "trust_tagline": "Look Your Best. Skilled Stylists, Relaxed Atmosphere.",
        "about_intro": "We're a full-service salon dedicated to helping every client look and feel their most confident.",
        "colors": {"primary": "#AD5D6D", "accent": "#E8C4B8", "bg": "#FFF9F9", "text": "#2D2D2D"},
        "service_icon_default": "fa-scissors",
        "highlights": ["Experienced Stylists", "Premium Products", "Welcoming Atmosphere"],
    },
    "restaurant": {
        "hero_headline_template": "Great Food & Great Times in {city}",
        "cta_primary": "View Menu",
        "cta_icon": "fa-utensils",
        "trust_tagline": "Fresh Ingredients, Every Plate, Every Day",
        "about_intro": "We're a local restaurant focused on great food, warm hospitality, and making every visit worth coming back for.",
        "colors": {"primary": "#922B21", "accent": "#F0B27A", "bg": "#FFF8F5", "text": "#1A1A2E"},
        "service_icon_default": "fa-utensils",
        "highlights": ["Fresh Local Ingredients", "Dine-In & Takeout", "Family-Friendly Environment"],
    },
    "__default__": {
        "hero_headline_template": "Professional {category} Services in {city}",
        "cta_primary": "Contact Us",
        "cta_icon": "fa-envelope",
        "trust_tagline": "Reliable, Local, and Ready to Help",
        "about_intro": "We are a locally owned business committed to delivering quality service and putting our customers first.",
        "colors": {"primary": "#2C3E50", "accent": "#3498DB", "bg": "#F8F9FA", "text": "#1A1A2E"},
        "service_icon_default": "fa-star",
        "highlights": ["Experienced Professionals", "Quality You Can Trust", "Local & Community-Focused"],
    },
}

# ---------------------------------------------------------------------------
# Service definitions (Google Maps category → human-readable card)
# ---------------------------------------------------------------------------

SERVICE_DEFINITIONS: dict[str, dict] = {
    "plumber": {
        "title": "Plumbing Repair & Installation",
        "desc": "From leaky faucets to full pipe replacements, we handle all your plumbing needs quickly and correctly.",
        "icon": "fa-wrench",
    },
    "heating contractor": {
        "title": "Heating System Service",
        "desc": "Furnace installation, repair, and tune-ups to keep your home warm throughout the cold months.",
        "icon": "fa-fire",
    },
    "air conditioning contractor": {
        "title": "Air Conditioning Service",
        "desc": "AC installation, repair, and seasonal maintenance for year-round comfort in your home or business.",
        "icon": "fa-snowflake",
    },
    "hvac contractor": {
        "title": "HVAC Systems",
        "desc": "Complete heating, ventilation, and air conditioning services for homes and commercial properties.",
        "icon": "fa-fan",
    },
    "service establishment": {
        "title": "Full-Service Shop",
        "desc": "A complete service location equipped and staffed to handle a wide range of jobs efficiently.",
        "icon": "fa-store",
    },
    "roofing contractor": {
        "title": "Roof Installation & Repair",
        "desc": "New roofs, targeted repairs, and full inspections. Built to last through any weather.",
        "icon": "fa-house-chimney",
    },
    "landscaping": {
        "title": "Lawn & Landscape Care",
        "desc": "Professional lawn maintenance, seasonal planting, and landscape design tailored to your property.",
        "icon": "fa-seedling",
    },
    "lawn care service": {
        "title": "Lawn Care",
        "desc": "Regular mowing, edging, and lawn treatments to keep your property looking its best.",
        "icon": "fa-leaf",
    },
    "electrician": {
        "title": "Electrical Services",
        "desc": "Safe, certified electrical work for residential and commercial properties. Wiring, panels, and more.",
        "icon": "fa-bolt",
    },
    "painter": {
        "title": "Interior & Exterior Painting",
        "desc": "Clean, precise painting work that refreshes your space and adds lasting curb appeal.",
        "icon": "fa-paint-roller",
    },
    "general contractor": {
        "title": "General Contracting",
        "desc": "Renovations, additions, and construction projects managed from start to finish with care.",
        "icon": "fa-hard-hat",
    },
    "hair salon": {
        "title": "Hair Styling & Cuts",
        "desc": "Expert haircuts, coloring, and styling treatments for every look and hair type.",
        "icon": "fa-scissors",
    },
    "beauty salon": {
        "title": "Beauty Services",
        "desc": "Full beauty treatments including facials, waxing, and cosmetic services.",
        "icon": "fa-spa",
    },
    "nail salon": {
        "title": "Nail Care",
        "desc": "Manicures, pedicures, and nail art in a clean, relaxing environment.",
        "icon": "fa-hand-sparkles",
    },
    "restaurant": {
        "title": "Dine-In & Takeout",
        "desc": "Fresh, made-to-order meals enjoyed in-house or conveniently taken on the go.",
        "icon": "fa-utensils",
    },
    "cleaning service": {
        "title": "Cleaning Services",
        "desc": "Thorough residential and commercial cleaning on a schedule that works for you.",
        "icon": "fa-broom",
    },
    "moving company": {
        "title": "Moving & Hauling",
        "desc": "Professional, careful moving services for local and long-distance relocations.",
        "icon": "fa-truck",
    },
    "auto repair shop": {
        "title": "Auto Repair",
        "desc": "Honest, reliable vehicle repairs and maintenance from certified mechanics.",
        "icon": "fa-car",
    },
    "veterinarian": {
        "title": "Veterinary Care",
        "desc": "Compassionate medical care for your pets, from routine checkups to urgent needs.",
        "icon": "fa-paw",
    },
    "dentist": {
        "title": "Dental Care",
        "desc": "Comprehensive dental services including cleanings, fillings, and cosmetic treatments.",
        "icon": "fa-tooth",
    },
}

# Fallback service cards per industry when services field is empty
INDUSTRY_FALLBACK_CARDS: dict[str, list[dict]] = {
    "plumb": [
        {"title": "Plumbing Repair",      "desc": "Fast fixes for leaks, clogs, and broken pipes.", "icon": "fa-wrench"},
        {"title": "Drain Cleaning",       "desc": "Clear blocked drains safely and effectively.",    "icon": "fa-droplet"},
        {"title": "Water Heater Service", "desc": "Installation and repair of water heaters.",       "icon": "fa-fire"},
    ],
    "heat": [
        {"title": "Furnace Repair",       "desc": "Get your heat back on fast.",                    "icon": "fa-fire"},
        {"title": "System Installation",  "desc": "New HVAC systems installed professionally.",      "icon": "fa-fan"},
        {"title": "Seasonal Tune-Up",     "desc": "Keep your system running efficiently all year.",  "icon": "fa-sliders"},
    ],
    "air condition": [
        {"title": "AC Repair",            "desc": "Fast diagnosis and repair for any AC issue.",     "icon": "fa-snowflake"},
        {"title": "AC Installation",      "desc": "New unit installation done right the first time.","icon": "fa-fan"},
        {"title": "Maintenance Plans",    "desc": "Keep your system efficient with regular service.", "icon": "fa-sliders"},
    ],
    "roof": [
        {"title": "Roof Repair",          "desc": "Fix leaks, damage, and worn materials quickly.",  "icon": "fa-house-chimney"},
        {"title": "New Roof Installation","desc": "Full replacement with quality materials.",         "icon": "fa-hard-hat"},
        {"title": "Roof Inspection",      "desc": "Identify issues before they become expensive.",   "icon": "fa-magnifying-glass"},
    ],
    "landscap": [
        {"title": "Lawn Maintenance",     "desc": "Regular mowing, edging, and cleanup.",            "icon": "fa-seedling"},
        {"title": "Tree & Shrub Care",    "desc": "Trimming and shaping for healthy growth.",         "icon": "fa-tree"},
        {"title": "Seasonal Cleanup",     "desc": "Spring and fall cleanup to keep your yard tidy.", "icon": "fa-leaf"},
    ],
    "spa": [
        {"title": "Skin Treatments",      "desc": "Facials and skin care for healthy, glowing skin.","icon": "fa-spa"},
        {"title": "Body Treatments",      "desc": "Relaxing and therapeutic body care services.",    "icon": "fa-heart"},
        {"title": "Wellness Consultations","desc": "Personalized plans for your beauty goals.",      "icon": "fa-calendar-check"},
    ],
    "salon": [
        {"title": "Haircuts & Styling",   "desc": "Expert cuts and styles for every hair type.",     "icon": "fa-scissors"},
        {"title": "Color Services",       "desc": "Full color, highlights, and balayage treatments.","icon": "fa-palette"},
        {"title": "Hair Treatments",      "desc": "Deep conditioning and restorative treatments.",   "icon": "fa-star"},
    ],
    "restaurant": [
        {"title": "Dine-In",              "desc": "Enjoy a relaxed meal in our welcoming dining room.","icon": "fa-utensils"},
        {"title": "Takeout & Delivery",   "desc": "Fresh food ready when and where you need it.",    "icon": "fa-bag-shopping"},
        {"title": "Catering",             "desc": "Event catering for groups large and small.",       "icon": "fa-star"},
    ],
    "__default__": [
        {"title": "Expert Service",       "desc": "Professional service you can count on.",          "icon": "fa-star"},
        {"title": "Local & Reliable",     "desc": "We're in your area and ready to help.",           "icon": "fa-map-marker-alt"},
        {"title": "Customer First",       "desc": "Your satisfaction is our top priority.",          "icon": "fa-handshake"},
    ],
}

# US state abbreviations for city parsing
_STATE_ABBRS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC",
}

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def normalize_row(raw_row: dict) -> dict:
    """Resolve column aliases and return a canonical dict."""
    result = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        value = "N/A"
        for alias in aliases:
            if alias in raw_row and raw_row[alias].strip():
                value = raw_row[alias].strip()
                break
        result[canonical] = value
    return result


def slugify(name: str, existing: set[str]) -> str:
    """Convert a business name to a filesystem-safe folder name."""
    s = name.lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    s = s[:60]
    base = s or "business"
    slug = base
    counter = 2
    while slug in existing:
        slug = f"{base}_{counter}"
        counter += 1
    existing.add(slug)
    return slug


def parse_city(location: str) -> str:
    """Extract city name from an address string."""
    if not location or location.strip().upper() == "N/A":
        return "Your Area"
    parts = [p.strip() for p in location.split(",")]
    for part in reversed(parts):
        if not part:
            continue
        tokens = part.split()
        if not tokens:
            continue
        # Skip state abbreviations (with or without a following ZIP)
        if tokens[0].upper() in _STATE_ABBRS:
            continue
        # Skip pure ZIP codes
        if re.fullmatch(r"\d{5}(-\d{4})?", part):
            continue
        # Skip street addresses (start with a house number)
        if re.match(r"^\d+\s+\w", part):
            continue
        return part
    return parts[0] if parts else "Your Area"


def resolve_industry(category: str, services: str) -> dict:
    """Match business to an industry config entry."""
    combined = (category + " " + services).lower()
    for key, cfg in INDUSTRY_CONFIG.items():
        if key == "__default__":
            continue
        if key in combined:
            return cfg
    return INDUSTRY_CONFIG["__default__"]


def _find_fallback_cards(industry_cfg: dict) -> list[dict]:
    """Find fallback service cards matching this industry config."""
    cfg_key = next(
        (k for k, v in INDUSTRY_CONFIG.items() if v is industry_cfg and k != "__default__"),
        None,
    )
    if cfg_key and cfg_key in INDUSTRY_FALLBACK_CARDS:
        return INDUSTRY_FALLBACK_CARDS[cfg_key]
    return INDUSTRY_FALLBACK_CARDS["__default__"]


def parse_services(services_str: str, industry_cfg: dict) -> list[dict]:
    """Convert raw services string into service card dicts (max 6)."""
    if services_str.strip().upper() == "N/A" or not services_str.strip():
        return _find_fallback_cards(industry_cfg)

    raw_cats = [s.strip() for s in services_str.split(",") if s.strip()]
    cards: list[dict] = []
    seen_titles: set[str] = set()

    for cat in raw_cats:
        defn = SERVICE_DEFINITIONS.get(cat.lower())
        if defn:
            card = dict(defn)
        else:
            card = {
                "title": cat.title(),
                "desc": f"Professional {cat.lower()} services you can rely on.",
                "icon": industry_cfg["service_icon_default"],
            }
        if card["title"] not in seen_titles:
            seen_titles.add(card["title"])
            cards.append(card)
        if len(cards) >= 6:
            break

    return cards if cards else _find_fallback_cards(industry_cfg)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _darken_hex(hex_color: str, factor: float = 0.7) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return "#{:02X}{:02X}{:02X}".format(int(r * factor), int(g * factor), int(b * factor))


def _lighten_hex(hex_color: str, opacity: float = 0.12) -> str:
    """Return an rgba string for a semi-transparent tint (used for icon backgrounds)."""
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r},{g},{b},{opacity})"


def resolve_colors(main_colors_str: str, industry_cfg: dict) -> dict:
    """Build a colors dict from CSV hex codes or fall back to industry defaults."""
    defaults = industry_cfg["colors"].copy()
    hexes = re.findall(r"#[0-9A-Fa-f]{6}", main_colors_str)
    if not hexes:
        return defaults
    result = defaults.copy()
    result["primary"] = hexes[0]
    if len(hexes) >= 2:
        result["accent"] = hexes[1]
    return result


# ---------------------------------------------------------------------------
# CSS renderer
# ---------------------------------------------------------------------------

def render_css(colors: dict) -> str:
    primary = colors["primary"]
    accent = colors["accent"]
    bg = colors["bg"]
    text = colors["text"]
    primary_dark = _darken_hex(primary, 0.72)
    icon_bg = _lighten_hex(primary, 0.12)

    return f"""\
/* ===== Reset & Base ===== */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; font-size: 16px; }}
body {{ font-family: var(--font-sans); color: var(--color-text); background: var(--color-bg); line-height: 1.65; }}
img  {{ max-width: 100%; height: auto; display: block; }}
a    {{ color: inherit; text-decoration: none; }}

/* ===== Design Tokens ===== */
:root {{
  --color-primary:      {primary};
  --color-primary-dark: {primary_dark};
  --color-accent:       {accent};
  --color-bg:           {bg};
  --color-text:         {text};
  --color-text-muted:   #6B7280;
  --color-surface:      #FFFFFF;
  --color-border:       #E5E7EB;
  --color-icon-bg:      {icon_bg};

  --font-display: 'Barlow', system-ui, sans-serif;
  --font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  --radius:    8px;
  --radius-lg: 16px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,.10);
  --shadow-md: 0 4px 16px rgba(0,0,0,.12);
  --shadow-lg: 0 8px 32px rgba(0,0,0,.16);

  --container-max: 1100px;
  --space-sm:  0.75rem;
  --space-md:  1.5rem;
  --space-lg:  3rem;
  --space-xl:  5rem;
}}

/* ===== Utilities ===== */
.container {{
  max-width: var(--container-max);
  margin: 0 auto;
  padding: 0 1.25rem;
}}
.section-title {{
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 4vw, 2.25rem);
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: var(--space-sm);
}}
.section-sub {{
  color: var(--color-text-muted);
  font-size: 1.05rem;
  margin-bottom: var(--space-lg);
}}
.btn {{
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.75rem;
  border-radius: 6px;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  border: 2px solid transparent;
  transition: opacity .15s, transform .15s, box-shadow .15s;
  white-space: nowrap;
}}
.btn:hover {{ opacity: .9; transform: translateY(-2px); }}
.btn-primary {{ background: var(--color-primary); color: #fff; border-color: var(--color-primary); box-shadow: 0 4px 14px rgba(0,0,0,.18); }}
.btn-outline  {{ background: transparent; color: var(--color-primary); border-color: var(--color-primary); }}
.btn-lg {{ padding: 1rem 2.25rem; font-size: 1.125rem; }}

/* ===== Navigation ===== */
.site-nav {{
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}}
.nav-inner {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 68px;
}}
.nav-logo-text {{
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-primary);
  letter-spacing: -0.02em;
}}
.nav-toggle {{
  display: none;
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--color-text);
  cursor: pointer;
  padding: 0.25rem;
}}
.nav-menu {{
  display: flex;
  align-items: center;
  gap: 2rem;
}}
.nav-menu a {{
  font-weight: 500;
  font-size: 0.95rem;
  color: var(--color-text);
  transition: color .15s;
}}
.nav-menu a:hover {{ color: var(--color-primary); }}
.nav-phone {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--color-primary) !important;
  font-weight: 600 !important;
  font-size: 0.95rem;
}}

/* ===== Hero ===== */
.hero {{
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
  color: #fff;
  padding: var(--space-xl) 0;
  text-align: center;
}}
.hero-inner {{
  max-width: 760px;
  margin: 0 auto;
  padding: 0 1.25rem;
}}
.hero-headline {{
  font-family: var(--font-display);
  font-size: clamp(2rem, 6vw, 3.5rem);
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: var(--space-sm);
  letter-spacing: -0.01em;
}}
.hero-sub {{
  font-size: 1.125rem;
  opacity: .88;
  margin-bottom: var(--space-md);
  max-width: 560px;
  margin-left: auto;
  margin-right: auto;
}}
.hero-phone {{
  display: block;
  font-size: clamp(1.5rem, 4vw, 2.25rem);
  font-weight: 700;
  color: #fff;
  margin-bottom: var(--space-md);
  letter-spacing: 0.02em;
}}
.hero-phone:hover {{ opacity: 0.85; }}
.hero-cta-group {{
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}}
.hero .btn-primary {{
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: #fff;
  font-size: 1.05rem;
  padding: 0.875rem 2rem;
}}
.hero .btn-outline {{
  border-color: rgba(255,255,255,.7);
  color: #fff;
}}
.hero .btn-outline:hover {{ background: rgba(255,255,255,.12); }}

/* ===== Services ===== */
.services {{
  padding: var(--space-xl) 0;
  background: var(--color-surface);
}}
.services .section-title,
.services .section-sub {{ text-align: center; }}
.services-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.5rem;
}}
.service-card {{
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-bottom: 3px solid var(--color-primary);
  border-radius: var(--radius-lg);
  padding: 1.75rem;
  box-shadow: var(--shadow-sm);
  transition: box-shadow .2s, transform .2s;
}}
.service-card:hover {{ box-shadow: var(--shadow-lg); transform: translateY(-5px); }}
.service-icon {{
  width: 56px;
  height: 56px;
  background: var(--color-icon-bg);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}}
.service-icon i {{ font-size: 1.5rem; color: var(--color-primary); }}
.service-title {{ font-size: 1.05rem; font-weight: 600; margin-bottom: 0.5rem; }}
.service-desc  {{ color: var(--color-text-muted); font-size: 0.95rem; line-height: 1.6; }}

/* ===== Trust Bar ===== */
.trust {{
  background: var(--color-primary);
  color: #fff;
  padding: var(--space-lg) 0;
}}
.trust-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.5rem;
  text-align: center;
}}
.trust-item i  {{ font-size: 1.75rem; margin-bottom: 0.5rem; color: var(--color-accent); display: block; }}
.trust-item p  {{ font-weight: 600; font-size: 0.9rem; line-height: 1.4; }}

/* ===== About ===== */
.about {{ padding: var(--space-xl) 0; background: var(--color-bg); }}
.about-inner {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: start;
}}
.about-text p {{
  color: var(--color-text-muted);
  margin-bottom: 1.5rem;
  font-size: 1.025rem;
}}
.about-bullets {{
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}}
.about-bullets li {{
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  font-size: 0.975rem;
  color: var(--color-text);
  font-weight: 500;
}}
.about-bullets li i {{
  color: var(--color-primary);
  margin-top: 0.15rem;
  flex-shrink: 0;
}}
.about-contact {{
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 2rem;
}}
.about-contact-name {{
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 800;
  margin-bottom: 1.25rem;
  color: var(--color-text);
}}
.about-detail {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-weight: 500;
  font-size: 0.975rem;
  color: var(--color-text);
  margin-bottom: 0.75rem;
}}
.about-detail i {{ color: var(--color-primary); width: 16px; text-align: center; flex-shrink: 0; }}
.about-detail a {{ color: var(--color-primary); }}

/* ===== Final CTA ===== */
.final-cta {{
  background: var(--color-primary);
  padding: var(--space-xl) 0;
  text-align: center;
  color: #fff;
}}
.final-cta-inner h2 {{
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 4vw, 2.25rem);
  font-weight: 800;
  margin-bottom: var(--space-sm);
  color: #fff;
}}
.final-cta-inner > p {{
  color: rgba(255,255,255,.85);
  margin-bottom: var(--space-lg);
  font-size: 1.05rem;
}}
.final-cta .btn-primary {{
  background: #fff;
  border-color: #fff;
  color: var(--color-primary);
}}
.final-cta .btn-primary:hover {{ opacity: .92; }}
.contact-form {{
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  max-width: 420px;
  margin: 0 auto;
  text-align: left;
}}
.contact-form input {{
  padding: 0.75rem 1rem;
  border: 1px solid rgba(255,255,255,.4);
  border-radius: var(--radius);
  font-size: 1rem;
  font-family: var(--font-sans);
  color: #fff;
  background: rgba(255,255,255,.15);
  transition: border-color .15s, outline .15s;
}}
.contact-form input::placeholder {{ color: rgba(255,255,255,.55); }}
.contact-form input:focus {{
  outline: 2px solid #fff;
  outline-offset: 0;
  border-color: transparent;
  background: rgba(255,255,255,.22);
}}
.contact-form .btn {{ width: 100%; justify-content: center; margin-top: 0.25rem; }}

/* ===== Footer ===== */
.site-footer {{
  background: #0D1117;
  color: rgba(255,255,255,.65);
  padding: var(--space-lg) 0;
}}
.footer-inner {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  text-align: center;
}}
.footer-brand-name {{ font-size: 1.15rem; font-weight: 700; color: #fff; display: block; }}
.footer-brand-city {{ font-size: 0.875rem; margin-top: 0.2rem; }}
.footer-links {{ display: flex; gap: 1.5rem; flex-wrap: wrap; justify-content: center; }}
.footer-links a {{ font-size: 0.9rem; transition: color .15s; }}
.footer-links a:hover {{ color: #fff; }}
.footer-copy {{ font-size: 0.8rem; opacity: .55; }}

/* ===== Responsive ===== */
@media (min-width: 768px) {{
  .nav-toggle {{ display: none !important; }}
  .nav-menu   {{ display: flex !important; }}
}}

@media (max-width: 767px) {{
  .nav-toggle {{ display: block; }}
  .nav-menu {{
    display: none;
    flex-direction: column;
    position: absolute;
    top: 68px;
    left: 0;
    right: 0;
    background: var(--color-surface);
    box-shadow: var(--shadow-md);
    padding: 1rem 1.25rem;
    gap: 1rem;
    align-items: flex-start;
  }}
  .nav-menu.nav-open {{ display: flex; }}
  .hero {{ padding: 3rem 0; }}
  .hero-cta-group .btn {{ width: 100%; justify-content: center; }}
  .services-grid {{ grid-template-columns: 1fr; }}
  .trust-grid {{ grid-template-columns: 1fr 1fr; }}
  .about-inner {{ grid-template-columns: 1fr; gap: 2rem; }}
}}
"""


# ---------------------------------------------------------------------------
# HTML section helpers
# ---------------------------------------------------------------------------

def _nav_html(ctx: dict) -> str:
    phone_link = (
        f'<a href="tel:{ctx["phone_digits"]}" class="nav-phone">'
        f'<i class="fas fa-phone"></i> {ctx["phone_display"]}</a>'
        if ctx["phone_display"]
        else ""
    )
    return f"""\
  <header class="site-nav">
    <div class="nav-inner container">
      <div class="nav-logo">
        <span class="nav-logo-text">{ctx["business_name"]}</span>
      </div>
      <button class="nav-toggle" id="navToggle" aria-label="Open menu" aria-expanded="false">
        <i class="fas fa-bars"></i>
      </button>
      <nav class="nav-menu" id="navMenu">
        <a href="#services">Services</a>
        <a href="#about">About</a>
        <a href="#contact">Contact</a>
        {phone_link}
      </nav>
    </div>
  </header>"""


def _hero_html(ctx: dict) -> str:
    if ctx["phone_display"]:
        cta_btn = (
            f'<a href="tel:{ctx["phone_digits"]}" class="btn btn-primary btn-lg">'
            f'<i class="fas {ctx["cta_icon"]}"></i> {ctx["cta_primary"]}</a>'
        )
        hero_phone = f'<a href="tel:{ctx["phone_digits"]}" class="hero-phone">{ctx["phone_display"]}</a>'
    else:
        cta_btn = (
            f'<a href="#contact" class="btn btn-primary btn-lg">'
            f'<i class="fas fa-envelope"></i> {ctx["cta_primary"]}</a>'
        )
        hero_phone = ""
    return f"""\
  <section class="hero">
    <div class="hero-inner">
      <h1 class="hero-headline">{ctx["hero_headline"]}</h1>
      <p class="hero-sub">{ctx["trust_tagline"]}</p>
      {hero_phone}
      <div class="hero-cta-group">
        {cta_btn}
        <a href="#services" class="btn btn-outline">Our Services</a>
      </div>
    </div>
  </section>"""


def _services_html(ctx: dict) -> str:
    cards_html = ""
    for card in ctx["service_cards"]:
        cards_html += f"""\
        <div class="service-card">
          <div class="service-icon"><i class="fas {card['icon']}"></i></div>
          <h3 class="service-title">{card['title']}</h3>
          <p class="service-desc">{card['desc']}</p>
        </div>
"""
    return f"""\
  <section class="services" id="services">
    <div class="container">
      <h2 class="section-title">What We Offer</h2>
      <p class="section-sub">Here&rsquo;s how we can help you today.</p>
      <div class="services-grid">
{cards_html}      </div>
    </div>
  </section>"""


def _trust_html(ctx: dict) -> str:
    return f"""\
  <section class="trust">
    <div class="container">
      <div class="trust-grid">
        <div class="trust-item">
          <i class="fas fa-map-marker-alt"></i>
          <p>Locally Owned &amp; Operated</p>
        </div>
        <div class="trust-item">
          <i class="fas fa-shield-halved"></i>
          <p>Licensed &amp; Insured</p>
        </div>
        <div class="trust-item">
          <i class="fas fa-handshake"></i>
          <p>Honest, Upfront Pricing</p>
        </div>
        <div class="trust-item">
          <i class="fas fa-clock"></i>
          <p>Prompt, Reliable Service</p>
        </div>
      </div>
    </div>
  </section>"""


def _highlights_html(ctx: dict) -> str:
    icons = ["fa-bolt", "fa-shield-halved", "fa-medal"]
    items_html = ""
    for i, text in enumerate(ctx["highlights"]):
        icon = icons[i % len(icons)]
        items_html += f"""\
        <div class="highlight-item">
          <i class="fas {icon}"></i>
          <p>{text}</p>
        </div>
"""
    return f"""\
  <section class="highlights">
    <div class="container">
      <div class="highlights-grid">
{items_html}      </div>
    </div>
  </section>"""


def _about_html(ctx: dict) -> str:
    location_line = ""
    if ctx["location"] and ctx["location"].upper() != "N/A":
        location_line = (
            f'<p class="about-detail"><i class="fas fa-map-marker-alt"></i> {ctx["location"]}</p>'
        )
    phone_line = ""
    if ctx["phone_display"]:
        phone_line = (
            f'<p class="about-detail"><i class="fas fa-phone"></i> '
            f'<a href="tel:{ctx["phone_digits"]}">{ctx["phone_display"]}</a></p>'
        )

    bullets_html = ""
    for point in ctx["highlights"]:
        bullets_html += f'            <li><i class="fas fa-check"></i> {point}</li>\n'

    return f"""\
  <section class="about" id="about">
    <div class="container">
      <div class="about-inner">
        <div class="about-text">
          <h2 class="section-title">About {ctx["business_name"]}</h2>
          <p>{ctx["about_intro"]}</p>
          <ul class="about-bullets">
{bullets_html}          </ul>
        </div>
        <div class="about-contact">
          <div class="about-contact-name">{ctx["business_name"]}</div>
          {location_line}
          {phone_line}
        </div>
      </div>
    </div>
  </section>"""


def _final_cta_html(ctx: dict) -> str:
    if ctx["phone_display"]:
        action_block = (
            f'<a href="tel:{ctx["phone_digits"]}" class="btn btn-primary btn-lg">'
            f'<i class="fas fa-phone"></i> {ctx["phone_display"]}</a>'
        )
        sub = "Give us a call. We&rsquo;re ready to help."
    else:
        action_block = """\
        <form class="contact-form" onsubmit="return false;">
          <input type="text"  placeholder="Your Name"  required>
          <input type="tel"   placeholder="Your Phone">
          <input type="email" placeholder="Your Email">
          <button type="submit" class="btn btn-primary">Send Message</button>
        </form>"""
        sub = "Fill out the form and we&rsquo;ll get back to you shortly."

    return f"""\
  <section class="final-cta" id="contact">
    <div class="container final-cta-inner">
      <h2>Ready to Get Started?</h2>
      <p>{sub}</p>
      {action_block}
    </div>
  </section>"""


def _footer_html(ctx: dict) -> str:
    year = datetime.date.today().year
    city_line = (
        f'<span class="footer-brand-city">Serving {ctx["city"]}</span>'
        if ctx["city"] != "Your Area"
        else ""
    )
    return f"""\
  <footer class="site-footer">
    <div class="container footer-inner">
      <div class="footer-brand">
        <span class="footer-brand-name">{ctx["business_name"]}</span>
        {city_line}
      </div>
      <nav class="footer-links">
        <a href="#services">Services</a>
        <a href="#about">About</a>
        <a href="#contact">Contact</a>
      </nav>
      <p class="footer-copy">&copy; {year} {ctx["business_name"]}. All rights reserved.</p>
    </div>
  </footer>"""


def render_html(ctx: dict) -> str:
    canonical_name = ctx["business_name"]
    city = ctx["city"]

    head = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{canonical_name} | {city}</title>
  <meta name="description" content="{ctx['hero_headline']}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@600;700;800;900&family=Inter:wght@400;500;600;700&display=swap">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>"""

    script = """\
  <script>
    var toggle = document.getElementById('navToggle');
    var menu   = document.getElementById('navMenu');
    toggle.addEventListener('click', function() {
      menu.classList.toggle('nav-open');
      this.setAttribute('aria-expanded', menu.classList.contains('nav-open'));
    });
  </script>"""

    sections = "\n".join([
        _nav_html(ctx),
        _hero_html(ctx),
        _services_html(ctx),
        _trust_html(ctx),
        _about_html(ctx),
        _final_cta_html(ctx),
        _footer_html(ctx),
    ])

    return f"{head}\n{sections}\n{script}\n</body>\n</html>\n"


# ---------------------------------------------------------------------------
# Site generator
# ---------------------------------------------------------------------------

def generate_site(row: dict, outputs_dir: str, existing_slugs: set[str], index: int, total: int) -> None:
    canonical = normalize_row(row)
    name = canonical["business_name"] if canonical["business_name"] != "N/A" else "Local Business"

    slug = slugify(name, existing_slugs)
    site_dir = os.path.join(outputs_dir, slug)
    os.makedirs(site_dir, exist_ok=True)

    print(f"  [{index}/{total}] {name}")

    city = parse_city(canonical["location"])
    industry_cfg = resolve_industry(canonical["category"], canonical["services"])
    colors = resolve_colors(canonical["main_colors"], industry_cfg)
    service_cards = parse_services(canonical["services"], industry_cfg)

    phone_display = canonical["phone"] if canonical["phone"] != "N/A" else None
    phone_digits = re.sub(r"\D", "", phone_display) if phone_display else ""

    category_label = canonical["category"] if canonical["category"] != "N/A" else "Professional"
    hero_headline = industry_cfg["hero_headline_template"].format(
        city=city, category=category_label.title()
    )

    ctx = {
        "business_name": name,
        "slug": slug,
        "phone_display": phone_display,
        "phone_digits": phone_digits,
        "city": city,
        "location": canonical["location"],
        "cta_primary": industry_cfg["cta_primary"],
        "cta_icon": industry_cfg["cta_icon"],
        "hero_headline": hero_headline,
        "trust_tagline": industry_cfg["trust_tagline"],
        "about_intro": industry_cfg["about_intro"],
        "service_cards": service_cards,
        "highlights": industry_cfg["highlights"],
        "colors": colors,
    }

    html = render_html(ctx)
    css = render_css(colors)

    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(site_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(css)

    rel = os.path.join(os.path.basename(os.path.dirname(site_dir)), slug)
    print(f"         → outputs/{rel}/")


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_csv(csv_path: str) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 44)
    print("   Website Creation System")
    print("=" * 44)

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = input("Path to leads CSV: ").strip()

    csv_path = os.path.expanduser(csv_path)
    if not os.path.isfile(csv_path):
        sys.exit(f"Error: file not found — {csv_path}")

    base_outputs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs")
    csv_base = os.path.splitext(os.path.basename(csv_path))[0]
    batch_raw = csv_base[len("leads_"):] if csv_base.startswith("leads_") else csv_base
    batch_name = batch_raw.replace("_", " ").title()
    outputs_dir = os.path.join(base_outputs, batch_name)
    os.makedirs(outputs_dir, exist_ok=True)

    rows = load_csv(csv_path)
    total = len(rows)
    print(f"\nLoaded {total} businesses from {os.path.basename(csv_path)}")
    print(f"Output directory: {os.path.abspath(outputs_dir)}\n")

    existing_slugs: set[str] = set()
    success = 0
    for i, row in enumerate(rows, start=1):
        try:
            generate_site(row, outputs_dir, existing_slugs, i, total)
            success += 1
        except Exception as e:
            name = row.get("Business Name") or row.get("Company Name") or f"Row {i}"
            print(f"  [{i}/{total}] WARNING: skipped '{name}' — {e}")

    print(f"\nDone! Generated {success}/{total} sites in: {os.path.abspath(outputs_dir)}")


if __name__ == "__main__":
    main()
