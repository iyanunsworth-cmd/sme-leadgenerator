"""Overpass API query + OSM tag mapping."""
import time
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# To extend: add a new key here mapped to a list of (osm_key, osm_value) tuples.
# Use osm_value=None to match any value for that key (e.g., any shop=*).
TYPE_TO_OSM_FILTERS = {
    "restaurants":   [("amenity", "restaurant")],
    "cafes":         [("amenity", "cafe")],
    "bars":          [("amenity", "bar"), ("amenity", "pub")],
    "hair_salons":   [("shop", "hairdresser")],
    "beauty_salons": [("shop", "beauty")],
    "clothing":      [("shop", "clothes")],
    "shops":         [("shop", None)],
    "contractors":   [
        ("craft", "roofer"),
        ("craft", "plumber"),
        ("craft", "electrician"),
        ("craft", "gardener"),
        ("craft", "painter"),
    ],
}


def build_query(plz, business_type, country="CH"):
    filters = TYPE_TO_OSM_FILTERS.get(business_type)
    if not filters:
        valid = ", ".join(sorted(TYPE_TO_OSM_FILTERS))
        raise ValueError(f"Unknown --type '{business_type}'. Valid: {valid}")

    lines = []
    for k, v in filters:
        tag = f'["{k}"]' if v is None else f'["{k}"="{v}"]'
        lines.append(f'  node{tag}["addr:postcode"="{plz}"](area.c);')
        lines.append(f'  way{tag}["addr:postcode"="{plz}"](area.c);')

    body = "\n".join(lines)
    return (
        f'[out:json][timeout:25];\n'
        f'area["ISO3166-1"="{country}"]->.c;\n'
        f'(\n{body}\n);\n'
        f'out center tags;\n'
    )


def query_overpass(plz, business_type, country="CH"):
    query = build_query(plz, business_type, country)

    last_exc = None
    for attempt in range(2):
        try:
            r = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=60,
                headers={"User-Agent": "sme-prospecting/1.0"},
            )
            if r.status_code in (429, 504):
                if attempt == 0:
                    time.sleep(5)
                    continue
                r.raise_for_status()
            r.raise_for_status()
            return _parse_elements(r.json())
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt == 0:
                time.sleep(5)
                continue
            raise
    raise RuntimeError(f"Overpass failed: {last_exc}")


def _parse_elements(data):
    businesses = []
    for el in data.get("elements", []):
        tags = el.get("tags", {}) or {}
        name = tags.get("name")
        if not name:
            continue

        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center") or {}
            lat = center.get("lat")
            lon = center.get("lon")

        street = tags.get("addr:street", "").strip()
        housenumber = tags.get("addr:housenumber", "").strip()
        city = tags.get("addr:city", "").strip()
        line1 = f"{street} {housenumber}".strip()
        address = ", ".join(p for p in [line1, city] if p)

        businesses.append({
            "osm_id": f"{el.get('type')}/{el.get('id')}",
            "name": name,
            "address": address,
            "phone": tags.get("phone") or tags.get("contact:phone", "") or "",
            "website": tags.get("website") or tags.get("contact:website", "") or "",
            "opening_hours": tags.get("opening_hours", "") or "",
            "lat": lat,
            "lon": lon,
        })
    return businesses
