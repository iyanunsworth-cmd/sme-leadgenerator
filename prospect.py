"""CLI entrypoint + importable pipeline for the SME prospecting tool."""
import argparse
import sys

# Ensure UTF-8 output so business names with umlauts/accents render correctly on
# Windows terminals, whose default code page (cp1252) mangles non-ASCII chars.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from overpass import query_overpass, TYPE_TO_OSM_FILTERS
from audit import score_business
from output import write_csv, print_summary


def run_prospect(plz, business_type, n, country="CH", min_score=40,
                 progress_cb=None, write_csv_file=True):
    """Run the full pipeline. Reusable by CLI and UI.

    progress_cb(index, total, business) is called after each audit (optional).
    Returns dict with: scanned, filtered, final, csv_path.
    """
    businesses = query_overpass(plz, business_type, country)
    total = len(businesses)

    scored = []
    for i, b in enumerate(businesses, 1):
        b = score_business(b)
        scored.append(b)
        if progress_cb:
            progress_cb(i, total, b)

    filtered = [b for b in scored if b["score"] >= min_score]
    filtered.sort(key=lambda x: x["score"], reverse=True)
    final = filtered[:n]

    csv_path = write_csv(final, plz, business_type) if write_csv_file else None
    return {
        "scanned": scored,
        "filtered": filtered,
        "final": final,
        "csv_path": csv_path,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Find SMEs in a postcode with missing or dated websites.",
    )
    parser.add_argument("--plz", required=True, help="Postcode (e.g., 8032)")
    parser.add_argument(
        "--type", required=True,
        choices=sorted(TYPE_TO_OSM_FILTERS.keys()),
        help="Business type",
    )
    parser.add_argument("--n", required=True, type=int, help="Max leads to return")
    parser.add_argument("--country", default="CH", help="ISO country code (default: CH)")
    parser.add_argument(
        "--min-score", type=int, default=40,
        help="Filter out leads scoring below this (default: 40)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"Querying Overpass: {args.type} in {args.plz}, {args.country}...")

    def _cli_progress(i, total, b):
        label = b["name"][:50]
        print(f"  [{i}/{total}] {label}... score={b['score']} ({b['website_status']})")

    try:
        result = run_prospect(
            plz=args.plz,
            business_type=args.type,
            n=args.n,
            country=args.country,
            min_score=args.min_score,
            progress_cb=_cli_progress,
        )
    except Exception as e:
        print(f"Overpass query failed: {e}", file=sys.stderr)
        sys.exit(1)

    scanned = result["scanned"]
    if not scanned:
        print("Nothing to audit. Check the postcode / country / type.")
        sys.exit(0)

    print(f"Audited {len(scanned)} businesses.")
    print_summary(len(scanned), len(result["filtered"]), result["final"], result["csv_path"])


if __name__ == "__main__":
    main()
