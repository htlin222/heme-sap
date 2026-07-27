#!/usr/bin/env python3
"""Build candidate pools of real YouTube results, so curation can only pick, never invent.

Every field here comes back from an actual search. A curator (human or agent) reads
the pool and chooses ids from it; there is no path by which a plausible-looking
eleven-character string can enter the course without having been returned by YouTube.

    uv run python tools/yt_pool.py queries.json pools.json [--per 12] [--jobs 6]

queries.json:  [{"unit": "ch11-u3", "queries": ["acute chest syndrome management", ...]}]
pools.json:    {"ch11-u3": [{"id", "title", "channel", "channelId", "seconds",
                             "views", "url"}, ...]}
"""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FIELDS = ("id", "title", "channel", "channel_id", "duration", "view_count")
PRINT = "|~|".join(f"%({f})s" for f in FIELDS)


def search(query: str, per: int) -> list[dict]:
    """One YouTube search. Failures return nothing rather than raising — a dead
    query must not take the whole run down."""
    try:
        proc = subprocess.run(
            [
                "yt-dlp",
                f"ytsearch{per}:{query}",
                "--flat-playlist",
                "--no-warnings",
                "--ignore-errors",
                "--print",
                PRINT,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return []
    out = []
    for line in proc.stdout.splitlines():
        parts = line.split("|~|")
        if len(parts) != len(FIELDS):
            continue
        vid, title, channel, channel_id, duration, views = parts
        if len(vid) != 11:
            continue
        out.append(
            {
                "id": vid,
                "title": title,
                "channel": channel,
                "channelId": channel_id if channel_id != "NA" else "",
                "seconds": int(float(duration)) if duration not in ("NA", "") else 0,
                "views": int(views) if views.isdigit() else 0,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "query": query,
            }
        )
    return out


def pool_for(item: dict, per: int) -> tuple[str, list[dict]]:
    seen: dict[str, dict] = {}
    for q in item["queries"]:
        for hit in search(q, per):
            seen.setdefault(hit["id"], hit)
    ranked = sorted(seen.values(), key=lambda h: -h["views"])
    return item["unit"], ranked


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a.split("=")[0]: a.split("=")[-1] for a in sys.argv[1:] if a.startswith("--")}
    per = int(flags.get("--per", 12))
    jobs = int(flags.get("--jobs", 6))
    src, dst = Path(args[0]), Path(args[1])

    items = json.loads(src.read_text())
    done = json.loads(dst.read_text()) if dst.exists() else {}
    todo = [i for i in items if i["unit"] not in done]
    print(f"· {len(todo)} units to search ({len(items) - len(todo)} already pooled)")

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for n, (unit, hits) in enumerate(pool.map(lambda i: pool_for(i, per), todo), 1):
            done[unit] = hits
            print(f"  {n:>4}/{len(todo)}  {unit:<14} {len(hits):>3} candidates")
            if n % 20 == 0:
                dst.write_text(json.dumps(done, ensure_ascii=False, indent=1))

    dst.write_text(json.dumps(done, ensure_ascii=False, indent=1))
    total = sum(len(v) for v in done.values())
    empty = [u for u, v in done.items() if not v]
    print(f"→ {dst}  ·  {len(done)} units · {total} candidates · {len(empty)} empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
