# Website Prompt Generation

Converts a CSV of business leads into ready-to-use prompts for a website AI to generate high-converting landing pages — one prompt file per business.

## When to Use

After lead generation has produced a CSV with at least these columns:

| Column | Description |
|---|---|
| Business Name | The name of the business |
| Phone | Contact phone number |
| Category | Primary business category (e.g. Plumber, HVAC, Hair Salon) |
| Location | City, state, or full address |
| Services | Comma-separated list of services offered |

## How to Run

```bash
cd "Website Prompt Generation"
python3 execution/generate_prompts.py
```

You will be prompted to enter the path to your input CSV file. Paste the full path and press Enter.

## Output

One `.txt` file per business, saved to the `outputs/` folder. Each file is named after the business (e.g. `joes_plumbing.txt`). The file contains a fully filled-in prompt — ready to paste directly into the website AI tool with no further editing.

## Edge Cases

- **Missing fields** — any field that is blank or "N/A" is passed through as-is. The prompt AI will handle gracefully.
- **Missing Main Colors** — the script infers colors from the business category automatically. No manual input needed.
- **Duplicate business names** — if two rows share the same name, the second file gets a `_2` suffix, the third gets `_3`, and so on.
- **Unrecognized category** — falls back to a neutral dark/light default palette.
- **Extra columns** — ignored. The script only reads the five required columns.

## Notes

- Do not edit the prompt template inside the script unless the website AI tool's expected format has changed.
- If you need to re-run for a subset of leads, just provide a filtered CSV — output files are never deleted automatically.
- **Hero image recommendations** — for plumbing (7 images), roofing (10 images), and solar panel (10 images) companies, each `.txt` file includes a `HERO IMAGE: <type> <number>` header at the top. The script diversifies image numbers within the same location to avoid repetition, and spreads numbers across different locations via a global counter. Manually upload the indicated image to the hero section of the website.
- **Em dashes** — the prompt explicitly instructs the AI never to use em dashes (—) in website copy.
