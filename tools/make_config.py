#!/usr/bin/env python3
"""Generate course/course.config.json from the ASH-SAP page map.

The chapter list is 49 entries long and every one of them needs a code, an icon,
a data-file name and two quota numbers — typing that by hand invites exactly the
kind of silent mismatch the build is supposed to catch. So it is generated, then
edited by hand for anything the generator cannot know.

Quotas are written as whatever the curated data currently holds (0 on first run).
Re-run with --sync after curation to freeze the real numbers; from then on the
build's quota check works as a regression guard.

    uv run python tools/make_config.py [--sync]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "course" / "data" / "ashsap-map.json"
CFG = ROOT / "course" / "course.config.json"

# Which nav group each chapter belongs to, and the Lucide icon for it.
# (group title, [(chapter number, icon), ...])
PARTS = [
    ("Consultative hematology", [(1, "syringe"), (2, "stethoscope"), (3, "user-round"), (4, "baby")]),
    (
        "Red cells and anemia",
        [
            (5, "sprout"), (6, "magnet"), (7, "apple"), (8, "flame"), (9, "heart-pulse"),
            (10, "dna"), (11, "circle-dot"), (12, "shield-alert"), (13, "hexagon"),
            (14, "waves"),
        ],
    ),
    (
        "Thrombosis",
        [(15, "git-merge"), (16, "waypoints"), (17, "spline"), (18, "crosshair"), (19, "git-fork")],
    ),
    ("Bleeding disorders", [(20, "droplet"), (21, "droplets"), (22, "network")]),
    ("Platelet disorders", [(23, "circle"), (24, "link"), (25, "filter"), (26, "grip")]),
    ("Laboratory and transfusion", [(27, "microscope"), (28, "package"), (29, "recycle")]),
    (
        "Transplantation and cellular therapy",
        [(30, "layers"), (31, "repeat"), (32, "users"), (33, "target")],
    ),
    (
        "Myeloid disorders",
        [
            (34, "shield"), (35, "git-branch"), (36, "shuffle"), (37, "trending-up"),
            (38, "star"), (39, "battery-low"), (40, "grid-3x3"), (41, "zap"),
        ],
    ),
    (
        "Lymphoid and plasma cell disorders",
        [
            (42, "bolt"), (43, "ribbon"), (44, "leaf"), (45, "flame-kindling"),
            (46, "shell"), (47, "snowflake"), (48, "boxes"), (49, "atom"),
        ],
    ),
]

KINDS = [
    {"id": "mechanism", "label": "Mechanism", "tone": "accent"},
    {"id": "clinical", "label": "Clinical decision", "tone": "success"},
    {"id": "trial", "label": "Trial & guideline", "tone": "danger"},
]

GRADES = [
    {"id": "guideline", "label": "Guideline-backed", "tone": "success"},
    {"id": "trial", "label": "Randomized evidence", "tone": "accent"},
    {"id": "evolving", "label": "Evolving", "tone": "attention"},
    {"id": "contested", "label": "Contested", "tone": "danger"},
]

SITE = {
    "project": "heme-sap",
    "name": "Heme SAP Companion",
    "url": "https://heme-sap.pages.dev",
    "locale": "en",
    "ogLocale": "en_US",
    "brandIcon": "droplet",
    "title": "Heme SAP Companion — a video lecture for every section of ASH-SAP 9e",
    "description": (
        "Every one of the 449 sections of the ASH-SAP 9th edition mapped to the lecture that "
        "explains it. Built for hematology fellows: society and journal sources, no "
        "med-student review videos. Search a section you did not follow, get the video."
    ),
    "ogDescription": (
        "449 ASH-SAP sections, each with the page number and the lecture that explains it. "
        "Fellowship level only — ASH, EHA, ESH, EBMT, VJHemOnc, journal and academic sources."
    ),
    "keywords": [
        "hematology board review", "ASH-SAP", "hematology fellowship",
        "hematology self-assessment", "benign hematology", "hematologic malignancy",
        "hematology lectures",
    ],
    "audience": "Hematology fellows and hematologists preparing for board certification",
    "educationalLevel": "Postgraduate medical training (hematology fellowship)",
    "about": ["Hematology", "Board review", "Graduate medical education", "Hematologic malignancy"],
    "learningResourceType": ["Video lecture index", "Board review companion", "Self-assessment"],
}


def main() -> int:
    blob = json.loads(MAP.read_text())
    by_n = {c["n"]: c for c in blob["chapters"]}

    existing = json.loads(CFG.read_text()) if CFG.exists() else {}
    old_quota = {c["code"]: c for c in existing.get("chapters", [])}

    chapters, nav = [], []
    for title, members in PARTS:
        codes = []
        for n, icon in members:
            code = f"CH{n}"
            codes.append(code)
            src = f"ch{n}"
            data = ROOT / "course" / "data" / f"{src}.json"
            units = drills = 0
            if "--sync" in sys.argv and data.exists():
                node = json.loads(data.read_text())
                units = len(node.get("units", []))
                drills = sum(len(u.get("drills") or []) for u in node.get("units", []))
            elif code in old_quota:
                units, drills = old_quota[code]["units"], old_quota[code].get("drills", 0)
            chapters.append(
                {
                    "code": code,
                    "title": by_n[n]["title"],
                    "icon": icon,
                    "source": src,
                    "units": units,
                    "drills": drills,
                }
            )
        nav.append({"title": title, "chapters": codes})

    missing = {c["n"] for c in blob["chapters"]} - {n for _, m in PARTS for n, _ in m}
    if missing:
        print(f"✗ chapters missing from PARTS: {sorted(missing)}", file=sys.stderr)
        return 1

    cfg = dict(existing)
    cfg["$schema"] = "../src/build/course.schema.json"
    cfg["site"] = SITE
    cfg["kinds"] = KINDS
    cfg["grades"] = GRADES
    cfg["nav"] = nav
    cfg["chapters"] = chapters
    cfg.setdefault("languages", {"en": "English"})

    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    total_u = sum(c["units"] for c in chapters)
    total_d = sum(c["drills"] for c in chapters)
    print(f"→ course/course.config.json  ·  {len(chapters)} chapters · {total_u} units · {total_d} videos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
