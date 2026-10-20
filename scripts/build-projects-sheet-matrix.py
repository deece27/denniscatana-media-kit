#!/usr/bin/env python3
"""Build the Sheet Projects tab as an active posting tracker from All Posts.

Matches Dennis's mock on the Projects tab:
  - Columns = episode clips (Instagram chronology; IG/TT/YT share a column)
  - Rows = Instagram · YouTube · TikTok
  - Cell = posted date (green) or blank (red = still to post)

Instagram is the master chronology. TikTok / YouTube attach by Day/Prep label
or title overlap; leftovers fill empty columns in upload order.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Display order matches Dennis's mock (Instagram → YouTube → TikTok)
PLATFORMS = ["Instagram", "YouTube", "TikTok"]
# Matching still considers all three
MATCH_PLATFORMS = ["Instagram", "TikTok", "YouTube"]

DAY_RE = re.compile(r"Day\s*(\d+)", re.I)
PRIMARY_DAY_RE = re.compile(
    r"📍\s*Day\s*(\d+)|(?:^|\A)Day\s*(\d+)\s*(?:[-–—:]|\s+of\s+Cycling\b)",
    re.I | re.M,
)
PREP_RE = re.compile(
    r"gear|prep|inspiration|flight to taipei|waiting to pick", re.I
)

# Dennis mock colors (sampled from his filled cells)
GREEN = {"red": 0.7137255, "green": 0.84313726, "blue": 0.65882355}
RED = {"red": 0.95686275, "green": 0.8, "blue": 0.8}
GREEN_HEX = "#B6D7A8"
RED_HEX = "#F4CCCC"


def short_label(title: str, fallback: str, n: int = 40) -> str:
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
    "taiwan",
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


def is_landscape_film(post: dict) -> bool:
    """Wide 16:9 YouTube films pinned to the far-right end (not Shorts day slots)."""
    if (post.get("Platform") or post.get("platform")) != "YouTube":
        return False
    t = post.get("Title/Caption snippet") or post.get("title") or ""
    if re.search(r"urge to cycle|so you have the urge", t, re.I):
        return True
    return False


def episode_header(slot: dict) -> str:
    """Column title — prefer the IG caption (Dennis mock used clip titles)."""
    if slot.get("is_film"):
        yt = slot["by_platform"].get("YouTube") or {}
        return short_label(
            yt.get("Title/Caption snippet") or yt.get("title") or "",
            "Film",
            48,
        )
    ig = slot["by_platform"].get("Instagram") or {}
    return short_label(
        ig.get("Title/Caption snippet") or ig.get("title") or "",
        slot.get("label") or "Post",
        48,
    )


def is_taroko(post: dict | None) -> bool:
    if not post:
        return False
    t = (post.get("Title/Caption snippet") or post.get("title") or "").lower()
    return "taroko" in t or "earthquake in 2024" in t


def build_project_matrix(posts: list[dict]) -> dict:
    films = [p for p in posts if is_landscape_film(p)]
    matrix_posts = [p for p in posts if not is_landscape_film(p)]

    ig_posts = sorted(
        [p for p in matrix_posts if p.get("Platform") == "Instagram"],
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

    for post in matrix_posts:
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
                slot = (
                    next((s for s in slots if s["is_prep"]), None)
                    if info["label"] == "Prep"
                    else None
                )
        if not slot and info["day_num"] is not None:
            n = info["day_num"]
            plat = post["Platform"]
            primary = primary_day_slot(n)

            def empty_same_day():
                return next(
                    (
                        s
                        for s in slots
                        if s["day_num"] == n and plat not in s["by_platform"]
                    ),
                    None,
                )

            if primary and plat not in primary["by_platform"]:
                slot = primary
            elif info.get("primary_day"):
                slot = next(
                    (
                        s
                        for s in slots
                        if s["day_num"] == n
                        and s.get("primary_day")
                        and plat not in s["by_platform"]
                    ),
                    None,
                ) or empty_same_day()
            else:
                slot = empty_same_day()
        if not slot:
            slot = best_title_match(post)
        if slot:
            put(slot, post)

    # Leftover TT/YT keep relative upload order → fill empty IG columns
    for plat in ("TikTok", "YouTube"):
        peers = sorted(
            [p for p in matrix_posts if p.get("Platform") == plat],
            key=lambda p: (p.get("Date") or "", p.get("URL") or ""),
        )
        used = {
            (
                s["by_platform"][plat].get("URL")
                or s["by_platform"][plat].get("Permalink ID")
            )
            for s in slots
            if plat in s["by_platform"]
        }
        leftover = [
            p for p in peers if (p.get("URL") or p.get("Permalink ID")) not in used
        ]
        empties = [s for s in slots if plat not in s["by_platform"]]
        for post, slot in zip(leftover, empties):
            put(slot, post)

    # Slide last day-column YT Short into the final day column before Film
    if slots and "YouTube" not in slots[-1]["by_platform"]:
        for i in range(len(slots) - 2, -1, -1):
            if "YouTube" in slots[i]["by_platform"]:
                slots[-1]["by_platform"]["YouTube"] = slots[i]["by_platform"].pop(
                    "YouTube"
                )
                break

    for film in films:
        slots.append(
            {
                "id": f"film-{film.get('Permalink ID') or film.get('URL')}",
                "label": "Film",
                "kind": "film",
                "day_num": None,
                "primary_day": False,
                "is_prep": False,
                "is_film": True,
                "ig_date": film.get("Date") or "",
                "by_platform": {"YouTube": film},
                "expect_missing": False,
            }
        )

    gaps = []
    for s in slots:
        if s.get("is_film"):
            s["expect_missing"] = False
            # Film is YT-only by design — IG/TT blanks are expected, not gaps
            continue
        expect = bool(s["primary_day"] or s["is_prep"])
        s["expect_missing"] = expect
        for plat in MATCH_PLATFORMS:
            if expect and plat not in s["by_platform"]:
                has = [p for p in MATCH_PLATFORMS if p in s["by_platform"]]
                gaps.append(
                    {
                        "episode": s["label"],
                        "missing": plat,
                        "has": has,
                        "ig_date": s["ig_date"],
                    }
                )

    return {"slots": slots, "gaps": gaps, "platforms": PLATFORMS}


def col_letter(n: int) -> str:
    """1-based column index → A1 letter(s)."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def render_tracker(project_name: str, matrix: dict, *, start_row: int = 1) -> dict:
    """Build values + format ranges matching Dennis's green/red mock."""
    slots = matrix["slots"]
    platforms = matrix["platforms"]
    ncol = 1 + len(slots)

    def pad(row):
        return (row + [""] * ncol)[:ncol]

    rows: list[list] = []
    # Row 1 — note (col A) + project name across episode columns (Dennis mock)
    proj_row = [""] + [project_name] * len(slots)
    note = (
        "POSTING TRACKER — auto-built from All Posts. Do not hand-edit. "
        "Green = posted (date). Red = still to post. Tag Project on All Posts, then refresh."
    )
    proj_row[0] = note
    rows.append(pad(proj_row))

    # Row 2 — episode titles
    rows.append(pad([""] + [episode_header(s) for s in slots]))

    # Platform date rows (Instagram → YouTube → TikTok)
    platform_row_offset = {}  # plat -> 0-based index within values
    for plat in platforms:
        row = [plat]
        for s in slots:
            post = s["by_platform"].get(plat)
            row.append((post or {}).get("Date") or "")
        platform_row_offset[plat] = len(rows)
        rows.append(pad(row))

    # Compact still-to-post summary under the matrix
    rows.append(pad([]))
    missing_lines = []
    for s in slots:
        for plat in platforms:
            if plat not in s["by_platform"]:
                # Skip expected film-only blanks for IG/TT
                if s.get("is_film") and plat != "YouTube":
                    continue
                missing_lines.append(
                    f"{episode_header(s)[:32]} → {plat}"
                )
    rows.append(
        pad(
            [
                "STILL TO POST",
                f"{project_name}: {len(missing_lines)} blank cells · "
                f"{len(slots)} episode columns",
            ]
        )
    )
    if missing_lines:
        rows.append(pad(["#", "Episode → platform"]))
        for i, line in enumerate(missing_lines, 1):
            rows.append(pad([i, line]))

    # Format ranges (A1, relative to sheet start_row):
    # paint each platform row red across episode cols, then green runs for posted.
    formats = []
    end_col = col_letter(ncol)
    for plat in platforms:
        r = start_row + platform_row_offset[plat]  # 1-based sheet row
        formats.append(
            {
                "range": f"B{r}:{end_col}{r}",
                "status": "missing",
                "background_color": RED_HEX,
                "rgb": RED,
            }
        )
        i = 0
        while i < len(slots):
            if plat not in slots[i]["by_platform"]:
                i += 1
                continue
            j = i
            while j < len(slots) and plat in slots[j]["by_platform"]:
                j += 1
            c1 = col_letter(2 + i)
            c2 = col_letter(2 + j - 1)
            formats.append(
                {
                    "range": f"{c1}{r}:{c2}{r}",
                    "status": "posted",
                    "background_color": GREEN_HEX,
                    "rgb": GREEN,
                }
            )
            i = j

    # Posted / missing counts per platform
    counts = {}
    for plat in platforms:
        posted = sum(1 for s in slots if plat in s["by_platform"])
        if plat == "YouTube":
            in_scope = len(slots)  # film counts
        else:
            in_scope = sum(1 for s in slots if not s.get("is_film"))
        counts[plat] = {
            "posted": posted,
            "missing": in_scope - posted,
            "in_scope": in_scope,
        }

    last_tt_label = None
    last_tt_date = None
    last_tt_is_taroko = False
    for s in slots:
        tt = s["by_platform"].get("TikTok")
        if tt:
            last_tt_label = episode_header(s)
            last_tt_date = tt.get("Date")
            last_tt_is_taroko = is_taroko(tt)

    return {
        "values": rows,
        "formats": formats,
        "platform_row_offset": platform_row_offset,
        "counts": counts,
        "last_tiktok": {
            "label": last_tt_label,
            "date": last_tt_date,
            "is_taroko": last_tt_is_taroko,
        },
        "missing_lines": missing_lines,
        "ncol": ncol,
        "nrow": len(rows),
    }


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
    all_formats: list[dict] = []
    summary = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "layout": "posting-tracker",
        "platforms": PLATFORMS,
        "colors": {"posted": GREEN_HEX, "missing": RED_HEX},
        "projects": [],
    }

    first = True
    row_cursor = 1  # 1-based sheet row for next block
    for project_name in sorted(by_project.keys()):
        matrix = build_project_matrix(by_project[project_name])
        if not first:
            all_sheet_rows.append([])
            all_sheet_rows.append([])
            row_cursor += 2
        block = render_tracker(project_name, matrix, start_row=row_cursor)
        all_sheet_rows.extend(block["values"])
        all_formats.extend(block["formats"])
        row_cursor += block["nrow"]
        first = False

        summary["projects"].append(
            {
                "name": project_name,
                "posts": len(by_project[project_name]),
                "episode_columns": len(matrix["slots"]),
                "counts": block["counts"],
                "last_tiktok": block["last_tiktok"],
                "still_to_post": len(block["missing_lines"]),
                "column_labels": [episode_header(s) for s in matrix["slots"]],
                "gaps": matrix["gaps"],
            }
        )

    width = max((len(r) for r in all_sheet_rows), default=1)
    values = [
        [("" if c is None else c) for c in (r + [""] * width)[:width]]
        for r in all_sheet_rows
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    values_path = args.out_dir / "projects_tab_matrix_values.json"
    formats_path = args.out_dir / "projects_tab_matrix_formats.json"
    summary_path = args.out_dir / "projects_tab_summary.json"
    csv_path = args.out_dir / "projects_tab_matrix.csv"

    values_path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    formats_path.write_text(
        json.dumps(all_formats, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(values)

    gap_rows = [
        ["Project", "Episode", "Missing platform", "Already on", "IG date"]
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
    with (args.out_dir / "projects_tab_missing.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        csv.writer(f).writerows(gap_rows)

    # Also mirror into workspace media if present
    ws_media = Path("/workspace/media/social-posts-sheet")
    if ws_media.parent.exists():
        ws_media.mkdir(parents=True, exist_ok=True)
        (ws_media / "projects_tab_matrix_values.json").write_text(
            values_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (ws_media / "projects_tab_matrix_formats.json").write_text(
            formats_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (ws_media / "projects_tab_summary.json").write_text(
            summary_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    print(json.dumps(summary, indent=2))
    print(f"Wrote {values_path} ({len(values)} rows × {width} cols)")
    print(f"Wrote {formats_path} ({len(all_formats)} format ranges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
