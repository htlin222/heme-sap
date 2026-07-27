#!/usr/bin/env python3
"""Check curated chapter files against the packet they were curated from.

This is the gate that makes "you may only pick from the pool" enforceable rather
than merely instructed: every id in the output must be traceable to a candidate
that a real search returned, and every duration must match the one YouTube gave.

    uv run python tools/check_picks.py packet.json course/data/ch36.json [...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

VID = re.compile(r"^https://www\.youtube\.com/watch\?v=([\w-]{11})$")
KINDS = {"mechanism", "clinical", "trial"}
MIN_ASSESSMENT = 80


def clock(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def main() -> int:
    packet = json.loads(Path(sys.argv[1]).read_text())
    known: dict[str, dict] = {}
    expected: dict[str, list[dict]] = {}
    for ch in packet["chapters"]:
        expected[ch["code"]] = ch["units"]
        for u in ch["units"]:
            for c in u["candidates"]:
                known[c["id"]] = c

    errors: list[str] = []
    stats = {"units": 0, "lessons": 0, "empty": 0, "drills": 0}

    for path in sys.argv[2:]:
        p = Path(path)
        if not p.exists():
            errors.append(f"{path}: missing")
            continue
        blob = json.loads(p.read_text())
        code = blob.get("chapter")
        want = expected.get(code)
        if want is None:
            errors.append(f"{path}: chapter {code!r} is not in this packet")
            continue
        got = blob.get("units", [])
        if len(got) != len(want):
            errors.append(f"{code}: {len(got)} units, packet has {len(want)}")
        for w, g in zip(want, got, strict=False):
            stats["units"] += 1
            if g.get("id") != w["unit"]:
                errors.append(f"{code}: expected unit id {w['unit']}, got {g.get('id')}")
            a = (g.get("assessment") or "").strip()
            if len(a) < MIN_ASSESSMENT:
                errors.append(f"{g.get('id')}: assessment is {len(a)} chars, need {MIN_ASSESSMENT}")

            videos = [g.get("lesson"), *(g.get("drills") or [])]
            seen_in_unit: set[str] = set()
            for i, v in enumerate(videos):
                if not v:
                    continue
                label = "lesson" if i == 0 else f"drill[{i - 1}]"
                url = v.get("url")
                if not url:
                    if i == 0:
                        stats["empty"] += 1
                    if not (v.get("note") or "").strip():
                        errors.append(f"{g.get('id')} {label}: empty slot needs a note")
                    continue
                if i == 0:
                    stats["lessons"] += 1
                else:
                    stats["drills"] += 1
                    if v.get("kind") not in KINDS:
                        errors.append(f"{g.get('id')} {label}: kind {v.get('kind')!r} not in {KINDS}")
                m = VID.match(url)
                if not m:
                    errors.append(f"{g.get('id')} {label}: malformed url {url}")
                    continue
                vid = m.group(1)
                if vid in seen_in_unit:
                    errors.append(f"{g.get('id')} {label}: {vid} used twice in the same unit")
                seen_in_unit.add(vid)
                cand = known.get(vid)
                if cand is None:
                    errors.append(f"{g.get('id')} {label}: {vid} IS NOT IN THE CANDIDATE POOL")
                    continue
                want_clock = clock(cand["seconds"])
                if v.get("duration") != want_clock:
                    errors.append(
                        f"{g.get('id')} {label}: duration {v.get('duration')!r}, "
                        f"search said {want_clock!r}"
                    )

    print(f"units {stats['units']} · core lectures {stats['lessons']} "
          f"· empty {stats['empty']} · supplementary {stats['drills']}")
    if errors:
        print(f"\n✗ {len(errors)} problems:")
        for e in errors[:60]:
            print(f"   · {e}")
        if len(errors) > 60:
            print(f"   … and {len(errors) - 60} more")
        return 1
    print("✓ every id traces to a real search result; durations match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
