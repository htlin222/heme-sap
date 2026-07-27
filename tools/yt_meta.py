#!/usr/bin/env python3
"""Build course/data/video-meta.json — the metadata the site and the audit trust.

Two sources, deliberately separated so the provenance of every number is visible:

  liveness   YouTube's oEmbed endpoint, asked once per video. It answers 200 for a
             public embeddable video and 401/403/404 for one that has been pulled,
             made private, or blocked. It is unauthenticated and does not rate-limit
             the way the full extractor does.

  runtime,   the search results in pools.json. These are YouTube's own figures,
  views,     captured when the candidate pool was built. Per-video extraction would
  channel    give fresher view counts, but YouTube now demands cookies for it at any
             volume, and borrowing a human's session to shave a few hundred views off
             a number is a bad trade. Each record says `"source": "search"` so nobody
             later mistakes these for live counts.

Run with --enrich to additionally try the full extractor at low concurrency, which
adds upload dates and refreshes view counts for whatever it manages to reach.

    uv run python tools/yt_meta.py [--pools pools.json] [--jobs 12] [--enrich]
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "course" / "data"
OUT = DATA / "video-meta.json"

OEMBED = "https://www.youtube.com/oembed"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) heme-sap-build/1.0"}
VID = re.compile(r"(?:v=|youtu\.be/)([\w-]{11})")

GONE = {
    401: "not embeddable or made private",
    403: "restricted",
    404: "deleted, or the id is wrong",
}


def collect_ids() -> dict[str, str]:
    """Every video id the curated chapters reference, mapped to a unit that uses it."""
    found: dict[str, str] = {}
    for path in sorted(DATA.glob("ch*.json")):
        if not re.fullmatch(r"ch\d+", path.stem):
            continue
        blob = json.loads(path.read_text())
        for u in blob.get("units", []):
            for v in [u.get("lesson"), *(u.get("drills") or [])]:
                if v and v.get("url") and (m := VID.search(v["url"])):
                    found.setdefault(m.group(1), u.get("id", path.stem))
    return found


def load_pool_facts(pools: list[Path]) -> dict[str, dict]:
    """id → the figures YouTube returned when this video was found."""
    facts: dict[str, dict] = {}
    for path in pools:
        if not path.exists():
            continue
        for hits in json.loads(path.read_text()).values():
            for h in hits:
                facts.setdefault(
                    h["id"],
                    {
                        "seconds": h.get("seconds", 0),
                        "views": h.get("views", 0),
                        "channel": h.get("channel", ""),
                        "title": h.get("title", ""),
                    },
                )
    return facts


def alive(vid: str, attempts: int = 3) -> tuple[str, str | None]:
    """(status, reason) from oEmbed. OK means public and embeddable right now."""
    url = f"{OEMBED}?{urllib.parse.urlencode({'url': f'https://www.youtube.com/watch?v={vid}', 'format': 'json'})}"
    for n in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as res:
                if res.status == 200:
                    return "OK", None
                return "GONE", f"HTTP {res.status}"
        except urllib.error.HTTPError as e:
            if e.code in GONE:
                return "GONE", GONE[e.code]
            if n == attempts - 1:
                return "UNKNOWN", f"HTTP {e.code}"
            time.sleep(1.5 * (n + 1))
        except Exception as e:
            if n == attempts - 1:
                return "UNKNOWN", type(e).__name__
            time.sleep(1.5 * (n + 1))
    return "UNKNOWN", "exhausted"


ENRICH_FIELDS = ("duration", "view_count", "channel", "title", "upload_date")
ENRICH_PRINT = "|~|".join(f"%({f})s" for f in ENRICH_FIELDS)


def enrich(vid: str) -> tuple[str, dict | None]:
    """Best-effort full extraction. Returns None when YouTube declines to answer."""
    try:
        proc = subprocess.run(
            ["yt-dlp", f"https://www.youtube.com/watch?v={vid}", "--skip-download",
             "--no-warnings", "--print", ENRICH_PRINT],
            capture_output=True, text=True, timeout=90,
        )
    except subprocess.TimeoutExpired:
        return vid, None
    line = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not line:
        return vid, None
    parts = line[0].split("|~|")
    if len(parts) != len(ENRICH_FIELDS):
        return vid, None
    duration, views, channel, title, upload = parts
    time.sleep(random.uniform(0.5, 1.5))
    return vid, {
        "seconds": int(float(duration)) if duration not in ("NA", "") else 0,
        "views": int(views) if views.isdigit() else 0,
        "channel": channel,
        "title": title,
        "uploaded": upload if upload != "NA" else "",
        "source": "extractor",
    }


def main() -> int:
    flags = {a.split("=")[0]: a.split("=")[-1] for a in sys.argv[1:] if a.startswith("--")}
    jobs = int(flags.get("--jobs", 12))
    pools = [Path(p) for p in flags.get("--pools", str(ROOT / "pools/pools.json")).split(",")]

    ids = collect_ids()
    facts = load_pool_facts(pools)
    missing = [v for v in ids if v not in facts]
    print(f"· {len(ids)} distinct videos · {len(ids) - len(missing)} have search-time figures")
    if missing:
        print(f"  ⚠ {len(missing)} not found in the pool file: {', '.join(missing[:8])}")

    print(f"· checking liveness via oEmbed ({jobs} at a time)")
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for n, (vid, (status, reason)) in enumerate(
            zip(ids, pool.map(alive, ids), strict=True), 1
        ):
            rec = {"status": status, "source": "search", **facts.get(vid, {})}
            if reason:
                rec["reason"] = reason
            out[vid] = rec
            if status != "OK":
                print(f"  ✗ {vid} ({ids[vid]}): {status} — {reason}")
            if n % 200 == 0:
                print(f"  … {n}/{len(ids)}")

    if "--enrich" in sys.argv:
        live = [v for v, r in out.items() if r["status"] == "OK"]
        print(f"· enriching {len(live)} videos with the full extractor (slow, best effort)")
        got = 0
        with ThreadPoolExecutor(max_workers=2) as pool:
            for vid, info in pool.map(enrich, live):
                if info:
                    out[vid].update(info)
                    got += 1
        print(f"  {got}/{len(live)} enriched; the rest keep their search-time figures")

    OUT.write_text(json.dumps(dict(sorted(out.items())), ensure_ascii=False, indent=1))
    ok = sum(1 for r in out.values() if r["status"] == "OK")
    gone = [v for v, r in out.items() if r["status"] == "GONE"]
    unknown = [v for v, r in out.items() if r["status"] == "UNKNOWN"]
    print(f"→ {OUT.relative_to(ROOT)}  ·  {ok}/{len(out)} live")
    if gone:
        print(f"✗ {len(gone)} no longer available — replace these: {', '.join(gone)}")
    if unknown:
        print(f"⚠ {len(unknown)} could not be checked: {', '.join(unknown[:10])}")
    return 1 if gone else 0


if __name__ == "__main__":
    sys.exit(main())
