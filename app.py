"""Streamlit UI for the SME prospecting tool."""
import io
import os

import pandas as pd
import streamlit as st

from overpass import TYPE_TO_OSM_FILTERS
from output import COLUMNS
from prospect import run_prospect


st.set_page_config(page_title="SME Prospecting", layout="wide")
st.title("SME Prospecting")
st.caption("Find small businesses with missing or dated websites.")

TYPE_OPTIONS = sorted(TYPE_TO_OSM_FILTERS.keys())

# Country name -> ISO 3166-1 alpha-2 code (what Overpass expects).
# Covers Europe + English-speaking markets where SME web-design outreach is common.
# Add more here if you prospect elsewhere — Overpass accepts any valid ISO code.
COUNTRIES = {
    "Australia":       "AU",
    "Austria":         "AT",
    "Belgium":         "BE",
    "Canada":          "CA",
    "Czech Republic":  "CZ",
    "Denmark":         "DK",
    "Finland":         "FI",
    "France":          "FR",
    "Germany":         "DE",
    "Greece":          "GR",
    "Hungary":         "HU",
    "Iceland":         "IS",
    "Ireland":         "IE",
    "Italy":           "IT",
    "Liechtenstein":   "LI",
    "Luxembourg":      "LU",
    "Netherlands":     "NL",
    "New Zealand":     "NZ",
    "Norway":          "NO",
    "Poland":          "PL",
    "Portugal":        "PT",
    "Slovakia":        "SK",
    "Slovenia":        "SI",
    "Spain":           "ES",
    "Sweden":          "SE",
    "Switzerland":     "CH",
    "United Kingdom":  "GB",
    "United States":   "US",
}
COUNTRY_NAMES = sorted(COUNTRIES.keys())

SCORE_HELP = (
    "Higher score = better prospect (worse-looking website).\n\n"
    "- **0–20** — clean, modern site. Probably not worth pitching.\n"
    "- **20–40** — minor issues (e.g. no viewport tag, stale footer year). Edge case.\n"
    "- **40–60** — meaningful problems (templated site, no HTTPS, stale Wayback).\n"
    "- **60+** — broken, missing, or placeholder site. Top priority.\n\n"
    "**Leads below this threshold are dropped from the table.** "
    "For strict prospect lists use 40+. To explore everything, set it to 0."
)

COUNTRY_HELP = (
    "Country to search within. OSM postcode tagging coverage varies — "
    "best in CH/DE/NL, patchier in the US. Match the postcode format to the country "
    "(e.g. UK: 'SW1A 1AA' with the space; Germany: 5 digits; US: 5 digits)."
)

with st.form("prospect_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        plz = st.text_input("Postcode", value="8032", help="Postal code to search within.")
        country_name = st.selectbox(
            "Country",
            options=COUNTRY_NAMES,
            index=COUNTRY_NAMES.index("Switzerland"),
            help=COUNTRY_HELP,
        )
        country = COUNTRIES[country_name]
    with c2:
        business_type = st.selectbox(
            "Business type",
            options=TYPE_OPTIONS,
            index=TYPE_OPTIONS.index("restaurants"),
            help="Maps to an OpenStreetMap tag (e.g. restaurants → amenity=restaurant).",
        )
        n = st.number_input(
            "Number of leads", min_value=5, max_value=100, value=20, step=5,
            help="Maximum rows to return after filtering and sorting by score.",
        )
    with c3:
        min_score = st.slider(
            "Minimum score", min_value=0, max_value=100, value=40, help=SCORE_HELP,
        )
        st.caption("Higher score = worse-looking site = better prospect. Hover the ℹ️ for the cheat sheet.")

    submitted = st.form_submit_button("Find Leads", type="primary")

with st.expander("How the score works"):
    st.markdown(
        "Each business gets a score from 0–100. **Higher = worse-looking website = better prospect.** "
        "Points are added for each red flag found:"
    )
    st.markdown(
        "| Signal | Points |\n"
        "|---|---:|\n"
        "| No website tagged in OpenStreetMap | +40 (status `missing`) |\n"
        "| Site fails to load / 4xx / 5xx | +35 (status `broken`) |\n"
        "| Page contains 'coming soon' / 'under construction' / 'hier entsteht' | +30 (status `placeholder`) |\n"
        "| No `<meta viewport>` tag (mobile-unfriendly proxy) | +15 |\n"
        "| No HTTPS | +10 |\n"
        "| Copyright year missing or older than 2 years | +10 |\n"
        "| Templated site (`wix.com`, `jimdo`, `squarespace`, `offix.ch`, `localsearch`, `mywebsite`) | +10 |\n"
        "| Last Wayback Machine snapshot > 3 years old | +10 |\n"
        "| No booking/reservation widget detected | +5 |"
    )
    st.markdown(
        "**Rules of thumb for the minimum-score slider:**\n"
        "- `0` — show every business that was scanned.\n"
        "- `20` — filter out clearly-fine websites; good for sanity-checking a neighbourhood.\n"
        "- `40` (default) — real prospects with meaningful issues.\n"
        "- `60+` — only broken, missing, or placeholder sites.\n\n"
        "Scoring is heuristic — always eyeball top prospects before outreach."
    )


def _lead_to_row(lead):
    lat, lon = lead.get("lat"), lead.get("lon")
    maps_url = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else ""
    return {
        "name": lead.get("name", ""),
        "address": lead.get("address", ""),
        "phone": lead.get("phone", ""),
        "website": lead.get("website", ""),
        "website_status": lead.get("website_status", ""),
        "score": lead.get("score", 0),
        "signals": "|".join(lead.get("signals", [])),
        "osm_id": lead.get("osm_id", ""),
        "google_maps_url": maps_url,
    }


if submitted:
    plz = plz.strip()
    country = country.strip().upper() or "CH"
    if not plz:
        st.error("Postcode is required.")
        st.stop()

    progress_bar = st.progress(0.0, text="Querying Overpass...")
    status_box = st.empty()

    def _progress(i, total, b):
        if total <= 0:
            return
        progress_bar.progress(i / total, text=f"Auditing {i}/{total}: {b['name'][:60]}")

    try:
        with st.spinner("Running..."):
            result = run_prospect(
                plz=plz,
                business_type=business_type,
                n=int(n),
                country=country,
                min_score=int(min_score),
                progress_cb=_progress,
                write_csv_file=True,
            )
    except Exception as e:
        progress_bar.empty()
        st.error(f"Query failed: {e}")
        st.info(
            "The public Overpass endpoint occasionally returns 504. "
            "Wait a minute and try again."
        )
        st.stop()

    progress_bar.empty()
    status_box.empty()

    scanned = result["scanned"]
    filtered = result["filtered"]
    final = result["final"]
    csv_path = result["csv_path"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Scanned", len(scanned))
    m2.metric("Above threshold", len(filtered))
    m3.metric("Returned", len(final))

    if not scanned:
        st.warning("No businesses found. Check postcode / country / type.")
        st.stop()

    if not final:
        st.info(
            f"No leads cleared the score threshold of {min_score}. "
            "Try lowering the minimum score."
        )
    else:
        rows = [_lead_to_row(b) for b in final]
        df = pd.DataFrame(rows, columns=COLUMNS)

        st.subheader("Leads")
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "website": st.column_config.LinkColumn("website"),
                "google_maps_url": st.column_config.LinkColumn(
                    "map", display_text="open map"
                ),
                "score": st.column_config.NumberColumn("score", format="%d"),
                "signals": st.column_config.TextColumn("signals", width="large"),
            },
        )

        if csv_path and os.path.exists(csv_path):
            with open(csv_path, "rb") as f:
                csv_bytes = f.read()
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name=os.path.basename(csv_path),
                mime="text/csv",
            )
        else:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button(
                "Download CSV",
                data=buf.getvalue().encode("utf-8"),
                file_name=f"leads_{plz}_{business_type}.csv",
                mime="text/csv",
            )

    with st.expander("All scanned businesses (pre-filter)"):
        all_rows = [_lead_to_row(b) for b in sorted(scanned, key=lambda x: -x.get("score", 0))]
        st.dataframe(
            pd.DataFrame(all_rows, columns=COLUMNS),
            use_container_width=True,
            hide_index=True,
            column_config={
                "website": st.column_config.LinkColumn("website"),
                "google_maps_url": st.column_config.LinkColumn(
                    "map", display_text="open map"
                ),
            },
        )
