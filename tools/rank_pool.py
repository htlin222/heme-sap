#!/usr/bin/env python3
"""Rank each unit's candidate pool so curation reads a shortlist, not 11,000 rows.

Nothing here decides what ships — it only orders what a curator sees, and marks
the candidates that are disqualified outright (med-student and patient-education
channels, shorts, conference teasers). The final pick is still a judgement call
made against the ASH-SAP section the unit maps to.

    uv run python tools/rank_pool.py pools.json queries.json shortlists.json [--top 8]
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

CHANNELS = json.loads((Path(__file__).resolve().parent / "channels.json").read_text())
TRUSTED = [c.lower() for c in CHANNELS["trusted"]]
USABLE = [c.lower() for c in CHANNELS["usable"]]
REJECTED = [c.lower() for c in CHANNELS["rejected"]]

# Words that carry no discriminating power in a hematology video title.
STOP = set(
    """a an the of in on for and or to with from at by is are be as this that
    what how why when new update overview introduction video lecture part
    hematology hematologic haematology blood disease disorder patient patients
    clinical management treatment therapy review case dr md phd professor 2019
    2020 2021 2022 2023 2024 2025 2026""".split()
)

# Titles that signal the wrong register even on an otherwise fine channel.
JUNK_TITLE = re.compile(
    r"\b(usmle|step ?[123]|nclex|mnemonic|made easy|in \d+ minutes?|for dummies"
    r"|crash course|quick review|exam prep|shorts?|#shorts|animation|explained simply"
    r"|for (patients|beginners|students)|my story|survivor story|patient story"
    r"|fundrais|gala|awareness month|webinar registration|save the date)\b",
    re.I,
)


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def tier(channel: str) -> str:
    c = channel.lower()
    if any(r in c for r in REJECTED):
        return "rejected"
    if any(t in c for t in TRUSTED):
        return "trusted"
    if any(u in c for u in USABLE):
        return "usable"
    return "unknown"


TIER_SCORE = {"trusted": 6.0, "usable": 2.5, "unknown": 0.0, "rejected": -100.0}


def duration_score(seconds: int) -> float:
    """Fellowship teaching lives between about eight minutes and an hour."""
    if seconds <= 0:
        return -1.0
    m = seconds / 60
    if m < 2:
        return -4.0  # teaser or short
    if m < 5:
        return -0.5
    if m <= 60:
        return 2.0
    if m <= 100:
        return 0.5
    return -2.0  # a whole symposium; too coarse to answer one section


def score(hit: dict, target: set[str]) -> tuple[float, str]:
    t = tier(hit["channel"])
    s = TIER_SCORE[t]
    if JUNK_TITLE.search(hit["title"]):
        s -= 8.0
    overlap = words(hit["title"]) & target
    s += 3.0 * len(overlap) / max(len(target), 1) * 4
    s += duration_score(hit["seconds"])
    s += 0.3 * math.log10(hit["views"] + 10)
    return round(s, 2), t


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=")[0]: a.split("=")[-1] for a in sys.argv[1:] if a.startswith("--")}
    top = int(flags.get("--top", 8))
    pools = json.loads(Path(args[0]).read_text())
    units = {u["unit"]: u for u in json.loads(Path(args[1]).read_text())}

    out, stats = {}, {"trusted": 0, "usable": 0, "unknown": 0, "rejected": 0}
    thin = []
    for uid, hits in pools.items():
        meta = units.get(uid, {})
        target = words(meta.get("title", "")) | words(" ".join(meta.get("queries", [])))
        ranked = []
        for h in hits:
            sc, t = score(h, target)
            stats[t] += 1
            if t == "rejected":
                continue
            ranked.append({**h, "score": sc, "tier": t})
        ranked.sort(key=lambda h: -h["score"])
        keep = [h for h in ranked if h["score"] > 0][:top]
        out[uid] = {
            "title": meta.get("title"),
            "chapter": meta.get("chapter"),
            "page": meta.get("page"),
            "endPage": meta.get("endPage"),
            "section": meta.get("section"),
            "candidates": [
                {k: h[k] for k in ("id", "title", "channel", "seconds", "views", "score", "tier")}
                for h in keep
            ],
        }
        if len(keep) < 3:
            thin.append(uid)

    Path(args[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"→ {args[2]}")
    print(f"   candidates by tier: {stats}")
    print(f"   units with fewer than 3 viable candidates: {len(thin)}")
    if thin:
        print("   " + ", ".join(thin[:25]) + (" …" if len(thin) > 25 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
