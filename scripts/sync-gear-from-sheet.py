#!/usr/bin/env python3
"""Build assets/gear-data.json from a Gear Loadout CSV export (Google Sheet).

Typical flow:
  1. Dennis adds rows in the Google Sheet (Item + Used on is enough to start).
  2. We fill research / affiliate / placement columns.
  3. Export CSV or pull via Composio → run this script → commit + deploy.

Usage:
  python3 scripts/sync-gear-from-sheet.py --csv path/to/dennis-gear-loadout.csv
  python3 scripts/sync-gear-from-sheet.py --csv path/to/export.csv --out assets/gear-data.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SHEET_URL = "https://docs.google.com/spreadsheets/d/1iP9jVPMB6Di0mt2drN-1EEDP0DDAorksRrSqfvfav5I/edit"

BADGE_LABELS = {
    "direct": "Affiliate / Shop",
    "match": "Taobao → Amazon Match",
    "exact-only": "Exact Kit · No Affiliate",
    "partner": "Partner Link",
}

CATEGORIES = [
    {"id": "all", "label": "All Gear"},
    {"id": "camera", "label": "Camera & Audio"},
    {"id": "trail", "label": "Trek & Trail"},
    {"id": "bike", "label": "Bikepacking"},
    {"id": "apparel", "label": "Apparel"},
    {"id": "travel", "label": "eSIM & Travel"},
]


def cell(row: dict, *keys: str) -> str:
    for k in keys:
        if k in row and row[k] is not None:
            return str(row[k]).strip()
    return ""


def row_to_item(row: dict) -> dict | None:
    name = cell(row, "Item")
    if not name:
        return None
    show = cell(row, "Show on Gear page").lower()
    if show and show not in {"yes", "y", "true", "1"}:
        return None
    badge = cell(row, "Badge type") or "exact-only"
    link = cell(row, "Public link URL")
    return {
        "name": name,
        "brand": cell(row, "Brand"),
        "category": (cell(row, "Category") or "other").lower(),
        "badgeType": badge,
        "badgeLabel": BADGE_LABELS.get(badge, badge),
        "usedIn": cell(row, "Used on (project/trip)"),
        "desc": cell(row, "Public description"),
        "exactItem": cell(row, "Exact product"),
        "whereBought": cell(row, "Where bought"),
        "linkLabel": cell(row, "Public link label") or None,
        "linkUrl": link or None,
        "section": cell(row, "Gear page section"),
        "affiliateAvailable": cell(row, "Affiliate available?"),
        "showOnPage": True,
        "status": cell(row, "Status"),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=root / "assets" / "gear-data.json")
    ap.add_argument("--sheet-url", default=SHEET_URL)
    args = ap.parse_args()

    with args.csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    items = []
    for row in rows:
        item = row_to_item(row)
        if item:
            items.append(item)

    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceSheet": args.sheet_url,
        "sheetTab": "Gear",
        "categories": CATEGORIES,
        "items": items,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(items)} items shown on Gear page)")


if __name__ == "__main__":
    main()
