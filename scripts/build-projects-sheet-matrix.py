#!/usr/bin/env python3
"""Build the Sheet Projects tab as a platform×episode matrix from All Posts.

Instagram is the master chronology: one column per IG post (plus Day/Prep
alignment for TikTok/YouTube). Missing cells are explicit for Day/Prep beats.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PLATFORMS = ["Instagram", "TikTok", "YouTube"]
DAY_RE = re.compile(r"Day\s*(\d+)", re.I)
# Official series beats only — not mid-caption "from Day 4 of…" asides
PRIMARY_DAY_RE = re.compile(
    r"📍\s*Day\s*(\d+)|(?:^|\A)Day\s*(\d+)\s*(?:[-–—:]|\s+of\s+Cycling\b)",
    re.I | re.M,
)
PREP_RE = re.compile(
    r"gear|prep|inspiration|flight to taipei|waiting to pick", re.I
)


def short_label(title: str, fallback: str, n: int = 28) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    if not t:
        return fallback
    return t if len(t) <= n else t[:n] + "…"


def classify_title(title: str) -> dict:
    t = title or ""
    if PREP_RE.search(t) and not re.search(r"📍\s*Day\s*\d+", t, re.I):
        if not DAY_RE.search(t) or re.search(r"waiting to pick|gear to cycle", t, re.I):
            kind = "prep"
            if re.search(r"gear to cycle|almost all.?ll need|ultra light", t, re.I):
                label = "Prep · Gear"
            elif re.search(r"waiting to pick", t, re.I):
                label = "Prep · Waiting for bike"
            else:
                label = "Prep"
            return {
                "day_num": -1,
                "primary_day": False,
                "is_prep": True,
                "kind": kind,
                "label": label,
            }

    primary = PRIMARY_DAY_RE.search(t)
    if primary:
        n = int(primary.group(1) if primary.group(1) is not None else primary.group(2))
        return {
            "day_num": n,
            "primary_day": True,
            "is_prep": False,
            "kind": "day",
            "label": f"Day {n}",
        }

    mention = DAY_RE.search(t)
    if mention:
        n = int(mention.group(1))
        return {
            "day_num": n,
            "primary_day": False,
            "is_prep": False,
            "kind": "extra",
            "label": short_label(t, f"Day {n}"),
        }

    if PREP_RE.search(t):
        return {
            "day_num": -1,
            "primary_day": False,
            "is_prep": True,
            "kind": "prep",
            "label": "Prep",
        }

    return {
        "day_num": None,
        "primary_day": False,
        "is_prep": False,
        "kind": "extra",
        "label": short_label(t, "Post"),
    }


def norm_title(t: str) -> str:
    s = (t or "").lower()
    s = re.sub(r"#[\w]+", " ", s)
    s = re.sub(r"cycling\s*1,?000\s*km around taiwan", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_STOP = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "your",
    "about",
    "around",
    "just",
    "when",
    "what",
    "they",
    "them",
    "then",
    "than",
    "into",
    "over",
    "after",
    "before",
    "taiwan",  # too common in this project
    "cycling",
    "cycle",
    "bike",
}


def title_overlap(a: str, b: str) -> int:
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0
    if na == nb:
        return 10
    if len(na) >= 16 and (na in nb or nb in na or na[:24] in nb or nb[:24] in na):
        return 6
    ta = {w for w in na.split() if len(w) > 3 and w not in _STOP}
    tb = {w for w in nb.split() if len(w) > 3 and w not in _STOP}
    return len(ta & tb)


def fmt_views(v) -> str:
    try:
        n = int(float(v or 0))
    except (TypeError, ValueError):
        n = 0
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        s = f"{n / 1_000:.1f}K"
        return s.replace(".0K", "K")
    return str(n)


def cell_value(post: dict | None, *, expect_missing: bool) -> str:
    if post:
        views = fmt_views(post.get("Views") or post.get("views") or 0)
        return f"Posted · {views}"
    # Primary Day/Prep gaps stay labeled Missing; side blanks are empty cells
    return "Missing" if expect_missing else ""


def build_project_matrix(posts: list[dict]) -> dict:
    ig_posts = sorted(
        [p for p in posts if p.get("Platform") == "Instagram"],
        key=lambda p: (p.get("Date") or "", p.get("URL") or ""),
    )

    slots = []
    for ig in ig_posts:
        info = classify_title(ig.get("Title/Caption snippet") or ig.get("title") or "")
        slots.append(
            {
                "id": f"ig-{ig.get('Permalink ID') or ig.get('URL')}",
                "label": info["label"],
                "kind": info["kind"],
                "day_num": info["day_num"],
                "primary_day": info["primary_day"],
                "is_prep": info["is_prep"],
                "ig_date": ig.get("Date") or "",
                "by_platform": {"Instagram": ig},
            }
        )

    def put(slot, post):
        plat = post["Platform"]
        prev = slot["by_platform"].get(plat)
        if not prev:
            slot["by_platform"][plat] = post
            return
        try:
            pv = int(float(prev.get("Views") or 0))
            nv = int(float(post.get("Views") or 0))
        except (TypeError, ValueError):
            pv, nv = 0, 0
        if nv > pv:
            slot["by_platform"][plat] = post

    def primary_day_slot(n):
        for s in slots:
            if s["day_num"] == n and s["primary_day"]:
                return s
        for s in slots:
            if s["day_num"] == n:
                return s
        return None

    def best_title_match(post):
        best, score = None, 0
        plat = post["Platform"]
        for s in slots:
            if plat in s["by_platform"]:
                continue
            ig = s["by_platform"]["Instagram"]
            sc = title_overlap(
                post.get("Title/Caption snippet") or "",
                ig.get("Title/Caption snippet") or "",
            )
            if sc > score:
                score, best = sc, s
        return best if score >= 3 else None

    peers_by_plat = defaultdict(list)
    for p in posts:
        if p.get("Platform") != "Instagram":
            peers_by_plat[p["Platform"]].append(p)
    for plat in peers_by_plat:
        peers_by_plat[plat].sort(key=lambda p: (p.get("Date") or "", p.get("URL") or ""))

    for post in posts:
        if post.get("Platform") == "Instagram":
            continue
        info = classify_title(post.get("Title/Caption snippet") or "")
        slot = None
        if info["is_prep"]:
            slot = next(
                (s for s in slots if s["is_prep"] and info["label"] == s["label"]),
                None,
            )
            if not slot and info["label"] == "Prep · Gear":
                # IG gear post is often titled “ultra light / all I’ll need”, not “Gear”
                slot = next(
                    (
                        s
                        for s in slots
                        if re.search(
                            r"ultra light|almost all|all i.?ll need|gear",
                            s["by_platform"]["Instagram"].get("Title/Caption snippet")
                            or "",
                            re.I,
                        )
                    ),
                    None,
                )
            if not slot:
                # Only fall back to another Prep column when labels match intent
                slot = next((s for s in slots if s["is_prep"]), None) if info["label"] == "Prep" else None
        if not slot and info["day_num"] is not None:
            n = info["day_num"]
            # Prefer primary Day N column; only use a non-primary same-day
            # column when the primary already has this platform.
            primary = primary_day_slot(n)
            if primary and post["Platform"] not in primary["by_platform"]:
                slot = primary
            elif primary and info.get("primary_day"):
                # Second official beat for same day (e.g. Day 13 part 2)
                slot = next(
                    (
                        s
                        for s in slots
                        if s["day_num"] == n
                        and s.get("primary_day")
                        and post["Platform"] not in s["by_platform"]
                    ),
                    primary,
                )
            else:
                slot = primary or next(
                    (
                        s
                        for s in slots
                        if s["day_num"] == n and post["Platform"] not in s["by_platform"]
                    ),
                    None,
                )
        if not slot:
            slot = best_title_match(post)
        if slot:
            put(slot, post)

    # Second pass: leftover TT/YT keep relative upload order → fill empty IG columns
    for plat in ("TikTok", "YouTube"):
        peers = sorted(
            [p for p in posts if p.get("Platform") == plat],
            key=lambda p: (p.get("Date") or "", p.get("URL") or ""),
        )
        used = {
            (s["by_platform"][plat].get("URL") or s["by_platform"][plat].get("Permalink ID"))
            for s in slots
            if plat in s["by_platform"]
        }
        leftover = [
            p for p in peers if (p.get("URL") or p.get("Permalink ID")) not in used
        ]
        empties = [s for s in slots if plat not in s["by_platform"]]
        for post, slot in zip(leftover, empties):
            put(slot, post)

    # Missing only for primary Day N / Prep beats (not side posts that mention a day)
    gaps = []
    for s in slots:
        expect = bool(s["primary_day"] or s["is_prep"])
        s["expect_missing"] = expect
        for plat in PLATFORMS:
            if expect and plat not in s["by_platform"]:
                has = [p for p in PLATFORMS if p in s["by_platform"]]
                gaps.append(
                    {
                        "episode": s["label"],
                        "missing": plat,
                        "has": has,
                        "ig_date": s["ig_date"],
                    }
                )

    return {"slots": slots, "gaps": gaps, "platforms": PLATFORMS}


def render_sheet_rows(project_name: str, matrix: dict) -> list[list]:
    slots = matrix["slots"]
    gaps = matrix["gaps"]
    platforms = matrix["platforms"]
    ncol = 1 + len(slots)

    def pad(row):
        return (row + [""] * ncol)[:ncol]

    rows: list[list] = []
    rows.append(
        pad(
            [
                "PROJECTS MATRIX — auto-built from All Posts. Do not hand-edit. "
                "Tag Project on All Posts, then refresh this tab."
            ]
        )
    )
    rows.append(pad([]))
    rows.append(
        pad(
            [
                "MISSING SUMMARY",
                f"{project_name}: {len(gaps)} Missing · {len(slots)} episode columns · "
                f"{sum(1 for s in slots if s.get('expect_missing'))} primary Day/Prep beats",
            ]
        )
    )
    if gaps:
        rows.append(pad(["#", "Episode", "Missing platform", "Already on", "IG date"]))
        for i, g in enumerate(gaps, 1):
            rows.append(
                pad(
                    [
                        i,
                        g["episode"],
                        g["missing"],
                        ", ".join(g["has"]) or "—",
                        g["ig_date"],
                    ]
                )
            )
    else:
        rows.append(pad(["(no missing Day/Prep deliverables)"]))

    rows.append(pad([]))
    rows.append(pad([f"PROJECT · {project_name}"]))
    rows.append(
        pad(
            [
                "Platforms ↓  ·  Episodes → (Instagram chronological order). "
                "Cell = Posted · views, Missing (Day/Prep gap), or — (side beat, no post)."
            ]
        )
    )

    header = ["Platform"] + [s["label"] for s in slots]
    rows.append(pad(header))
    # Helper row: episode kind + IG date for scanning
    rows.append(pad(["(kind / IG date)"] + [f"{s['kind']} · {s['ig_date']}" for s in slots]))

    for plat in platforms:
        row = [plat]
        for s in slots:
            expect = bool(s.get("expect_missing"))
            row.append(cell_value(s["by_platform"].get(plat), expect_missing=expect))
        rows.append(pad(row))

    # Compact URL row block (optional lookup under the status matrix)
    rows.append(pad([]))
    rows.append(pad(["URL LOOKUP (same columns)"]))
    rows.append(pad(["Platform"] + [s["label"] for s in slots]))
    for plat in platforms:
        row = [plat]
        for s in slots:
            post = s["by_platform"].get(plat)
            row.append((post or {}).get("URL") or "")
        rows.append(pad(row))

    return rows


def load_posts(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        type=Path,
        default=Path(
            "/cursor/stores/bc-fef0428a-847c-4d0d-827b-cf3c4a0db826/media/social-posts-sheet/all-social-posts.csv"
        ),
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path(
            "/cursor/stores/bc-fef0428a-847c-4d0d-827b-cf3c4a0db826/media/social-posts-sheet"
        ),
    )
    args = ap.parse_args()

    posts = load_posts(args.csv)
    by_project: dict[str, list] = defaultdict(list)
    for p in posts:
        proj = (p.get("Project") or "").strip()
        if not proj or proj.lower() == "unassigned":
            continue
        by_project[proj].append(p)

    all_sheet_rows: list[list] = []
    summary = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "layout": "matrix",
        "platforms": PLATFORMS,
        "projects": [],
    }

    # Stack matrices per project
    first = True
    for project_name in sorted(by_project.keys()):
        matrix = build_project_matrix(by_project[project_name])
        block = render_sheet_rows(project_name, matrix)
        if not first:
            all_sheet_rows.append([""] * max(len(r) for r in block))
            all_sheet_rows.append([""] * max(len(r) for r in block))
        all_sheet_rows.extend(block)
        first = False

        posted_cells = 0
        missing_cells = 0
        dash_cells = 0
        for s in matrix["slots"]:
            expect = bool(s.get("expect_missing"))
            for plat in PLATFORMS:
                if plat in s["by_platform"]:
                    posted_cells += 1
                elif expect:
                    missing_cells += 1
                else:
                    dash_cells += 1

        summary["projects"].append(
            {
                "name": project_name,
                "posts": len(by_project[project_name]),
                "episode_columns": len(matrix["slots"]),
                "day_prep_beats": sum(
                    1 for s in matrix["slots"] if s.get("expect_missing")
                ),
                "posted_cells": posted_cells,
                "missing": missing_cells,
                "side_blank_cells": dash_cells,
                "column_labels": [s["label"] for s in matrix["slots"]],
                "gaps": matrix["gaps"],
            }
        )

    # Normalize rectangular
    width = max((len(r) for r in all_sheet_rows), default=1)
    values = [[("" if c is None else c) for c in (r + [""] * width)[:width]] for r in all_sheet_rows]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    values_path = args.out_dir / "projects_tab_matrix_values.json"
    summary_path = args.out_dir / "projects_tab_summary.json"
    csv_path = args.out_dir / "projects_tab_matrix.csv"

    values_path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(values)

    # Also keep a long-form gap list for tooling
    gap_rows = [
        [
            "Project",
            "Episode",
            "Missing platform",
            "Already on",
            "IG date",
        ]
    ]
    for proj in summary["projects"]:
        for g in proj["gaps"]:
            gap_rows.append(
                [
                    proj["name"],
                    g["episode"],
                    g["missing"],
                    ", ".join(g["has"]),
                    g["ig_date"],
                ]
            )
    (args.out_dir / "projects_tab_missing.csv").write_text(
        "", encoding="utf-8"
    )  # touched
    with (args.out_dir / "projects_tab_missing.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(gap_rows)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {values_path} ({len(values)} rows × {width} cols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
