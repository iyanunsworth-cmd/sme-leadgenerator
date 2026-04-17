"""CSV writer and stdout summary."""
import csv
import os
from datetime import datetime

COLUMNS = [
    "name", "address", "phone", "website", "website_status",
    "score", "signals", "osm_id", "google_maps_url",
]


def _maps_url(lead):
    lat, lon = lead.get("lat"), lead.get("lon")
    if lat is None or lon is None:
        return ""
    return f"https://www.google.com/maps?q={lat},{lon}"


def write_csv(leads, plz, business_type, out_dir="output"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"leads_{plz}_{business_type}_{timestamp}.csv")

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow({
                "name": lead.get("name", ""),
                "address": lead.get("address", ""),
                "phone": lead.get("phone", ""),
                "website": lead.get("website", ""),
                "website_status": lead.get("website_status", ""),
                "score": lead.get("score", 0),
                "signals": "|".join(lead.get("signals", [])),
                "osm_id": lead.get("osm_id", ""),
                "google_maps_url": _maps_url(lead),
            })
    return path


def print_summary(scanned, above_threshold, top_leads, csv_path):
    print()
    print(f"Scanned:         {scanned}")
    print(f"Above threshold: {above_threshold}")
    print()
    if top_leads:
        print("Top 5 by score:")
        for i, lead in enumerate(top_leads[:5], 1):
            top_sig = "|".join(lead.get("signals", [])[:3]) or "-"
            print(f"  {i}. [{lead.get('score', 0):3d}] {lead.get('name', '')}  ({top_sig})")
    else:
        print("No leads above threshold.")
    print()
    print(f"CSV: {csv_path}")
