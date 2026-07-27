#!/usr/bin/env python3
"""Whole-course gate: every linked video must be traceable, live, and correctly timed.

`check_picks.py` validates one curation packet in isolation. This validates the
finished course against the union of every candidate pool ever built plus the
liveness data, which is what you want after patches, replacements and re-searches
have moved things around.

    uv run python tools/validate.py pools.json repools.json [...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "course" / "data"
CFG = json.loads((ROOT / "course" / "course.config.json").read_text())

VID = re.compile(r"^https://www\.youtube\.com/watch\?v=([\w-]{11})$")
KINDS = {k["id"] for k in CFG["kinds"]}
MIN_ASSESSMENT = (CFG.get("audit") or {}).get("minAssessmentChars", 80)
DRIFT = (CFG.get("audit") or {}).get("driftSeconds", 30)


def clock(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def load_pools(paths: list[str]) -> dict[str, dict]:
    known: dict[str, dict] = {}
    for p in paths:
        for hits in json.loads(Path(p).read_text()).values():
            for h in hits:
                known.setdefault(h["id"], h)
    return known


def main() -> int:
    known = load_pools(sys.argv[1:])
    meta = json.loads((DATA / "video-meta.json").read_text())
    expected = {
        f"CH{c['n']}": [u["title"] for u in c["units"]]
        for c in json.loads((DATA / "ashsap-map.json").read_text())["chapters"]
    }

    errors: list[str] = []
    stats = dict(units=0, lessons=0, empty=0, drills=0, videos=set())

    for chapter in CFG["chapters"]:
        path = DATA / f"{chapter['source']}.json"
        if not path.exists():
            errors.append(f"{chapter['code']}: missing {path.name}")
            continue
        units = json.loads(path.read_text()).get("units", [])
        want = expected.get(chapter["code"], [])
        if len(units) != chapter["units"]:
            errors.append(f"{chapter['code']}: {len(units)} units, config says {chapter['units']}")

        for i, u in enumerate(units):
            stats["units"] += 1
            uid = u.get("id")
            if uid != f"{chapter['code'].lower()}-u{i + 1}":
                errors.append(f"{chapter['code']}: unit {i + 1} has id {uid!r}")
            if len(want) > i and u.get("name") != want[i]:
                errors.append(f"{uid}: name drifted from the book's section title")
            if len((u.get("assessment") or "").strip()) < MIN_ASSESSMENT:
                errors.append(f"{uid}: assessment too short")

            seen: set[str] = set()
            for j, v in enumerate([u.get("lesson"), *(u.get("drills") or [])]):
                if not v:
                    continue
                label = "lesson" if j == 0 else f"drill[{j - 1}]"
                if not v.get("url"):
                    if j == 0:
                        stats["empty"] += 1
                    if not (v.get("note") or "").strip():
                        errors.append(f"{uid} {label}: blank slot with no note")
                    continue
                if j == 0:
                    stats["lessons"] += 1
                else:
                    stats["drills"] += 1
                    if v.get("kind") not in KINDS:
                        errors.append(f"{uid} {label}: bad kind {v.get('kind')!r}")
                    if not (v.get("name") or "").strip():
                        errors.append(f"{uid} {label}: missing name")
                if j == 0 and not (v.get("why") or "").strip():
                    errors.append(f"{uid} lesson: missing why")

                m = VID.match(v["url"])
                if not m:
                    errors.append(f"{uid} {label}: malformed url {v['url']}")
                    continue
                vid = m.group(1)
                stats["videos"].add(vid)
                if vid in seen:
                    errors.append(f"{uid} {label}: {vid} used twice in one unit")
                seen.add(vid)

                if vid not in known:
                    errors.append(f"{uid} {label}: {vid} NOT IN ANY CANDIDATE POOL")
                rec = meta.get(vid)
                if rec is None:
                    errors.append(f"{uid} {label}: {vid} missing from video-meta.json")
                elif rec.get("status") != "OK":
                    errors.append(f"{uid} {label}: {vid} is {rec.get('status')} — {rec.get('reason')}")
                elif rec.get("seconds"):
                    want_clock = clock(rec["seconds"])
                    if v.get("duration") != want_clock:
                        errors.append(
                            f"{uid} {label}: duration {v.get('duration')!r}, actual {want_clock!r}"
                        )

    print(
        f"{stats['units']} units · {stats['lessons']} core lectures · {stats['empty']} blank"
        f" · {stats['drills']} supplementary · {len(stats['videos'])} distinct videos"
    )
    if errors:
        print(f"\n✗ {len(errors)} problems:")
        for e in errors[:80]:
            print(f"   · {e}")
        if len(errors) > 80:
            print(f"   … and {len(errors) - 80} more")
        return 1
    print("✓ every video traces to a real search result, is live, and is correctly timed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
