#!/usr/bin/env python3
"""Rebuild assets/library-data.json from the social inventory CSV + project overrides."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

KNOWN_PROJECTS = [
    "Taiwan 1000km",
    "Cruise",
    "Peru",
    "China-HK",
    "Tobermory / Canada",
    "Korea",
]


def num(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except ValueError:
        return None


def load_overrides(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if not str(k).startswith("_") and isinstance(v, str)}


def build(csv_path: Path, overrides: dict) -> dict:
    posts = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = (row.get("id") or "").strip()
            url = row.get("url") or ""
            project = overrides.get(pid) or overrides.get(url) or "Unassigned"
            posts.append(
                {
                    "id": pid,
                    "platform": row["platform"],
                    "type": row["type"],
                    "date": row["date"] or None,
                    "title": (row.get("title_or_caption") or "").strip(),
                    "url": url,
                    "views": num(row.get("views")),
                    "likes": num(row.get("likes")),
                    "comments": num(row.get("comments")),
                    "saves": num(row.get("saves")),
                    "shares": num(row.get("shares")),
                    "reach": num(row.get("reach")),
                    "follows": None,
                    "day": num(row.get("day")),
                    "suggestedBucket": row.get("bucket") or None,
                    "confidence": row.get("confidence") or None,
                    "needsVet": (row.get("needs_vet") or "").strip().lower() == "true",
                    "project": project,
                }
            )

    posts.sort(key=lambda p: (p["date"] or "", p["views"] or -1), reverse=True)
    return {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(csv_path),
        "counts": {
            "total": len(posts),
            "byPlatform": dict(Counter(p["platform"] for p in posts)),
            "byProject": dict(Counter(p["project"] for p in posts)),
        },
        "projectOptions": ["Unassigned"] + KNOWN_PROJECTS,
        "posts": posts,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, required=True, help="Path to social-content-inventory.csv")
    ap.add_argument(
        "--overrides",
        type=Path,
        default=root / "assets" / "library-project-overrides.json",
    )
    ap.add_argument("--out", type=Path, default=root / "assets" / "library-data.json")
    args = ap.parse_args()

    payload = build(args.csv, load_overrides(args.overrides))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {args.out} ({payload['counts']})")


if __name__ == "__main__":
    main()
