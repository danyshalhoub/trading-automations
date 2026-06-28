# Lead Generation System

Finds businesses on Google Maps (via Apify) that have no website, then exports a CSV ready for Google Sheets.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your Apify API token
```bash
cp .env.example .env
# Open .env and paste your token from https://console.apify.com/account/integrations
```

### 3. Run
```bash
python lead_gen_apify.py
```

You will be prompted for:
- **Business niche** — e.g. `plumbers`, `hair salons`, `auto repair shops`
- **Location** — e.g. `Houston TX`, `Chicago`, `Miami FL`
- **Max results** — how many Google Maps listings to scrape (e.g. `50`)

### 4. Import CSV into Google Sheets
1. Open Google Sheets → **File → Import → Upload**
2. Select the generated `leads_<niche>_<location>.csv`
3. Choose **Replace current sheet** → **Import data**

## Output columns
| Column | Source |
|---|---|
| Business Name | Google Maps listing title |
| Phone | Google Maps listing |
| Category | Primary business category from Google Maps |
| Location | Full address from Google Maps |
| Services | All business categories joined (shows full scope of services offered) |

## Notes
- Only businesses **without a website** are included in the output.
- The Apify actor used is `compass/crawler-google-places`.
- If Apify credits run out, switch to `lead_gen_outscraper.py` (requires `OUTSCRAPER_API_KEY` in `.env`).
