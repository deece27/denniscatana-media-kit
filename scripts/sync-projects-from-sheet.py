#!/usr/bin/env python3
"""Build assets/projects-data.json from a Sheet export CSV (All Posts tab).

Expected columns match the All Social Posts sheet. Filters rows where Project
is set (not Unassigned) and groups into project blocks with peak + feed.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SKIP = {"", "unassigned"}


def num(v):
    if v is None or str(v).strip() == "":
        return 0
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("assets/projects-data.json"))
    args = ap.parse_args()

    with args.csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_proj: dict[str, list] = defaultdict(list)
    for r in rows:
        proj = (r.get("Project") or "").strip()
        if proj.lower() in SKIP:
            continue
        by_proj[proj].append(r)

    projects = []
    for name, items in sorted(by_proj.items()):
        for r in items:
            for k in ("Views", "Likes", "Comments", "Shares", "Saves", "Reach"):
                r[f"_{k}"] = num(r.get(k))

        by_plat = defaultdict(list)
        for r in items:
            by_plat[r.get("Platform") or "Unknown"].append(r)

        peaks = {}
        for p, plist in by_plat.items():
            peaks[p] = max(plist, key=lambda x: x["_Views"])

        overall = max(items, key=lambda x: x["_Views"])
        totals = {
            "posts": len(items),
            "views": int(sum(r["_Views"] for r in items)),
            "likes": int(sum(r["_Likes"] for r in items)),
            "comments": int(sum(r["_Comments"] for r in items)),
            "shares": int(sum(r["_Shares"] for r in items)),
            "saves": int(sum(r["_Saves"] for r in items)),
            "by_platform": {
                p: {
                    "posts": len(plist),
                    "views": int(sum(x["_Views"] for x in plist)),
                    "likes": int(sum(x["_Likes"] for x in plist)),
                }
                for p, plist in by_plat.items()
            },
        }
        slug = name.lower().replace(" ", "-").replace("/", "-")
        feed = sorted(items, key=lambda r: (r.get("Date") or "", -r["_Views"]))
        projects.append(
            {
                "id": slug,
                "name": name,
                "sheetProject": name,
                "tag": "Project",
                "summary": f"{len(items)} posts tagged “{name}” in the All Social Posts sheet.",
                "totals": totals,
                "peak": {
                    "platform": overall.get("Platform"),
                    "type": overall.get("Type"),
                    "title": overall.get("Title/Caption snippet") or "",
                    "url": overall.get("URL"),
                    "permalinkId": overall.get("Permalink ID"),
                    "date": overall.get("Date"),
                    "views": int(overall["_Views"]),
                    "likes": int(overall["_Likes"]),
                    "comments": int(overall["_Comments"]),
                    "shares": int(overall["_Shares"]),
                    "saves": int(overall["_Saves"]),
                    "reach": int(overall["_Reach"]) if overall.get("Reach") not in ("", None) else None,
                    "thumbnail": overall.get("Thumbnail URL") or "",
                },
                "peaksByPlatform": {
                    p: {
                        "platform": p,
                        "title": t.get("Title/Caption snippet") or "",
                        "url": t.get("URL"),
                        "date": t.get("Date"),
                        "views": int(t["_Views"]),
                        "likes": int(t["_Likes"]),
                        "thumbnail": t.get("Thumbnail URL") or "",
                    }
                    for p, t in peaks.items()
                },
                "posts": [
                    {
                        "platform": r.get("Platform"),
                        "type": r.get("Type"),
                        "title": r.get("Title/Caption snippet") or "",
                        "url": r.get("URL"),
                        "permalinkId": r.get("Permalink ID"),
                        "date": r.get("Date"),
                        "views": int(r["_Views"]),
                        "likes": int(r["_Likes"]),
                        "comments": int(r["_Comments"]),
                        "shares": int(r["_Shares"]),
                        "saves": int(r["_Saves"]),
                        "thumbnail": r.get("Thumbnail URL") or "",
                    }
                    for r in feed
                ],
            }
        )

    # Prefer Cycling Taiwan tag polish
    for p in projects:
        if p["sheetProject"] == "Cycling Taiwan":
            p["tag"] = "Flagship"
            p["summary"] = (
                "1000km around Taiwan — day-by-day across Instagram, TikTok, and YouTube. "
                "Peak post and full feed from the All Social Posts sheet."
            )
            p["id"] = "cycling-taiwan"

    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(args.csv),
        "sheetUrl": "https://docs.google.com/spreadsheets/d/15jVzyTbLt2oeWIgLLqROgmPgZe76EAUDZGIQ3EGCmTM/edit",
        "projects": projects,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} ({len(projects)} projects)")


if __name__ == "__main__":
    main()
