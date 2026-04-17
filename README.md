# SME Prospecting Tool

Find small businesses in a given postcode that either have no website, or have an obviously dated one. Built for web-design outreach — higher score = better prospect.

## What it does

1. Queries OpenStreetMap (via the free Overpass API) for businesses of a given type in a postcode.
2. For each business, fetches the tagged website and runs a heuristic audit (HTTPS, viewport tag, copyright year, template markers, placeholder pages, booking widgets, Wayback freshness).
3. Outputs a scored, sorted CSV and prints a short summary.

No API keys, no accounts — Overpass and Wayback are both free.

## Setup (Windows)

### 1. Install Python

Install Python 3.10 or newer from [python.org/downloads](https://www.python.org/downloads/).

During the installer, **check the box "Add python.exe to PATH"**. This is important — otherwise `python` won't be found in the terminal.

Verify in a new terminal (close and reopen the terminal first so PATH refreshes):

```
python --version
```

If `python` still isn't found, your PATH wasn't updated. Either rerun the installer and tick the PATH checkbox, or add Python manually: Start → "Edit the system environment variables" → Environment Variables → select `Path` under User variables → Edit → add the install folder (e.g. `C:\Users\<you>\AppData\Local\Programs\Python\Python312\` and its `Scripts` subfolder).

### 2. Install dependencies

From this folder:

```
pip install -r requirements.txt
```

That installs `requests`, `beautifulsoup4`, and `python-dateutil`.

### 3. Run it

**CLI:**
```
python prospect.py --plz 8032 --type restaurants --n 20
```

The CSV lands in `./output/leads_<plz>_<type>_<timestamp>.csv`.

**UI:**
```
streamlit run app.py
```

It opens automatically in your browser at <http://localhost:8501>. On Windows you can also just double-click `run-ui.bat` in this folder.

## Usage

```
python prospect.py --plz <postcode> --type <type> --n <max> [--country <ISO>] [--min-score <N>]
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--plz` | yes | — | Postcode (works for any country). |
| `--type` | yes | — | `restaurants`, `cafes`, `bars`, `hair_salons`, `beauty_salons`, `clothing`, `shops`, `contractors` |
| `--n` | yes | — | Max leads to return (after filter + sort). |
| `--country` | no | `CH` | ISO 3166-1 alpha-2 country code used for Overpass area. |
| `--min-score` | no | `40` | Filter out leads scoring below this. |

### Example commands

```
# Zurich restaurants (Switzerland)
python prospect.py --plz 8032 --type restaurants --n 20

# Bern hair salons
python prospect.py --plz 3011 --type hair_salons --n 15 --country CH

# London shops (general retail)
python prospect.py --plz "SW1A 1AA" --type shops --n 20 --country GB

# Berlin cafes, only strong prospects
python prospect.py --plz 10115 --type cafes --n 10 --country DE --min-score 50

# Zurich contractors (roofers, plumbers, electricians, gardeners, painters)
python prospect.py --plz 8048 --type contractors --n 20
```

## Scoring

| Signal | Points |
|---|---|
| No `website` tag in OSM | 40 (status = `missing`; other checks skipped) |
| Site fails to load / 4xx / 5xx | 35 (status = `broken`; other checks skipped) |
| "Coming soon" / "Under construction" / "Hier entsteht" | +30 (status overridden to `placeholder`) |
| No `<meta name="viewport">` | +15 |
| No HTTPS | +10 |
| Copyright year missing or older than current − 2 | +10 |
| Template marker (`wix.com`, `jimdo`, `squarespace`, `/offix.ch`, `localsearch`, `mywebsite`) | +10 |
| Last Wayback snapshot > 3 years old | +10 |
| No booking/reservation widget | +5 |

Score is capped at 100. Higher = worse-looking site = better prospect.

## Extending `--type`

To add a new business type, edit the `TYPE_TO_OSM_FILTERS` dict at the top of `overpass.py`:

```python
"florists": [("shop", "florist")],
```

Use `None` as the value to match any value for that key (e.g. `("shop", None)` matches every shop). Also add the new key to `--type` examples in the README — argparse picks it up automatically.

Browse OSM tag reference at <https://wiki.openstreetmap.org/wiki/Map_features>.

## Known limitations

- **OSM coverage is ~85–90 %.** Some real businesses aren't mapped, or are mapped without a postcode. You will miss them. Cross-check Google Maps for Tier-1 leads before outreach.
- **Scoring is heuristic.** A site can score high for silly reasons (e.g. missing viewport on a perfectly good static page) or low despite being awful. Always eyeball the top prospects before contacting.
- **Language-specific cues.** Placeholder detection currently covers English and German ("hier entsteht"). Add your own phrases per-market if you expand.
- **One-pass fetch only.** We only hit the homepage. A dated site with a modern homepage will fool the audit.
- **No JS rendering.** Sites that render content client-side look empty to `requests`. This is usually a bad sign for a small-business site anyway, so it often cooperates with the scoring.
- **Rate limits.** Overpass and Wayback are free — please be respectful. The tool has one retry on 429/504; if you query the same city many times in succession, slow down.

## Project layout

```
prospect/
├── prospect.py        # CLI entrypoint + importable run_prospect()
├── app.py             # Streamlit UI
├── overpass.py        # Overpass query + OSM tag mapping
├── audit.py           # Website fetching + scoring
├── output.py          # CSV writer + stdout summary
├── run-ui.bat         # double-click launcher for the UI on Windows
├── requirements.txt
├── README.md
├── .gitignore
└── output/            # created at runtime
```

## v2 ideas

- **PageSpeed Insights API** — Google's free (keyed) endpoint gives real mobile-friendly and performance scores. Much stronger signal than the viewport-tag proxy.
- **Screenshot capture via Playwright** — a thumbnail per lead makes the CSV dramatically easier to triage in Airtable/Notion.
- **Email enrichment via Hunter.io free tier** — pull likely `info@` / owner email addresses for each domain.
- **Zefix UID lookup for Swiss businesses** — Swiss commercial register has the legal name, address, and sometimes director names. Useful for personalised outreach in CH.
- **Caching the Overpass response** so you can re-run audits without re-hitting Overpass.
- **Google Business Profile signal** — presence + photo freshness is a strong proxy for owner engagement.
