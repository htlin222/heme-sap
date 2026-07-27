#!/usr/bin/env python3
"""Derive the course skeleton from the ASH-SAP 9e PDF.

Two independent signals are combined so neither alone has to be trusted:

  1. the PDF's own outline (49 chapters, 313 bookmarked sections) — authoritative
     for chapter/section identity and page numbers;
  2. body headings recovered from font metrics (MyriadPro-BoldCond 13pt and
     HelveticaNeueLTStd-BdCn 15pt — the book is typeset in two batches) — used
     only to subdivide bookmarked sections that run 4+ pages, so no single unit
     ever maps to a slab of the book too big to search through.

Output: course/data/ashsap-map.json — the page map the whole course hangs off.
Nothing here is written by hand; rerunning on the same PDF gives the same file.

    uv run python tools/extract_ashsap.py path/to/ASH-SAP_9e.pdf
"""

from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "course" / "data" / "ashsap-map.json"

# The two fonts the book uses for section headings, at their heading sizes.
HEADING_FONTS = {("MyriadPro-BoldCond", 13.0), ("HelveticaNeueLTStd-BdCn", 15.0)}
# One tier down — used only to rescue units that are still too coarse afterwards
# (Sickle cell disease, say, is one bookmark over sixteen pages).
SUBHEADING_FONTS = {("MyriadPro-Bold", 10.0), ("HelveticaNeueLTStd-Bd", 11.0)}

# A bookmarked section running this many pages or more gets subdivided…
SPLIT_MIN_PAGES = 4
# …but two split points may not land on the same page.
SPLIT_MIN_GAP = 1
# After that pass, anything still this long is split again on subheadings.
RESCUE_MIN_PAGES = 5

RX_PAGE = re.compile(r'<page id="page(\d+)"')
RX_FONT = re.compile(r'<font name="([^"]+)" size="([\d.]+)"')
RX_CHAR = re.compile(r'<char [^>]*?x="([\d.]+)" y="([\d.]+)"[^>]*?c="(.)"')
RX_OUTLINE = re.compile(r'^(-|\|\s+)\t?\s*"(.*)"\t#page=(\d+)')


def clean(s: str) -> str:
    """Strip the soft hyphens and smart quotes pdf text extraction leaves behind."""
    s = s.replace("­", "").replace("‐", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))


def read_outline(pdf: Path, last_page: int) -> list[dict]:
    txt = subprocess.run(
        ["mutool", "show", str(pdf), "outline"], capture_output=True, text=True, check=True
    ).stdout
    chapters: list[dict] = []
    cur: dict | None = None
    for line in txt.splitlines():
        m = RX_OUTLINE.match(line)
        if not m:
            continue
        lead, title, page = m.group(1), clean(m.group(2)), int(m.group(3))
        if lead == "-":
            mm = re.match(r"Chapter (\d+): (.*)", title)
            cur = {
                "n": int(mm.group(1)) if mm else len(chapters) + 1,
                "title": mm.group(2) if mm else title,
                "page": page,
                "sections": [],
            }
            chapters.append(cur)
        elif cur is not None and not title.lower().startswith("bibliograph"):
            cur["sections"].append({"title": title, "page": page})
        elif cur is not None:
            cur["bibliography"] = page
    chapters.sort(key=lambda c: c["page"])
    for i, c in enumerate(chapters):
        c["end"] = chapters[i + 1]["page"] - 1 if i + 1 < len(chapters) else last_page
    return chapters


def read_headings(pdf: Path, tiers: list[set[tuple[str, float]]]) -> list[dict[int, list[dict]]]:
    """Recover body headings from font metrics, merging wrapped lines back together.

    One pass over the (large) structured-text dump serves every heading tier.
    """
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "stext.xml"
        subprocess.run(
            ["mutool", "draw", "-F", "stext", "-o", str(xml), str(pdf)],
            capture_output=True,
            check=True,
        )
        spans: list[dict[int, list[tuple]]] = [collections.defaultdict(list) for _ in tiers]
        page = font = size = None
        buf: list[str] = []
        bx = by = 0.0

        def flush() -> None:
            nonlocal buf
            if buf and size and by > 60:
                face = (font, round(float(size), 1))
                text = "".join(buf).strip()
                if text:
                    for tier, bucket in zip(tiers, spans, strict=True):
                        if face in tier:
                            bucket[page].append((bx, by, text))
            buf = []

        with xml.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if m := RX_PAGE.search(line):
                    flush()
                    page = int(m.group(1))
                    continue
                if m := RX_FONT.search(line):
                    flush()
                    font, size = m.group(1), m.group(2)
                    continue
                if "<line " in line:
                    flush()
                    continue
                if m := RX_CHAR.search(line):
                    if not buf:
                        bx, by = float(m.group(1)), float(m.group(2))
                    buf.append(m.group(3))
        flush()

    # A heading that wraps produces one span per line; rejoin by column and baseline.
    out = []
    for bucket in spans:
        pages: dict[int, list[dict]] = {}
        for page, items in bucket.items():
            items.sort(key=lambda k: (k[0] >= 300, k[1]))  # left column first, then top-down
            merged: list[dict] = []
            cur: dict | None = None
            for x, y, text in items:
                if cur and abs(x - cur["x"]) < 12 and 0 < y - cur["y"] <= 22:
                    cur["title"] += " " + text
                    cur["y"] = y
                else:
                    if cur:
                        merged.append(cur)
                    cur = {"x": x, "y": y, "title": text}
            if cur:
                merged.append(cur)
            pages[page] = [{"title": clean(h["title"]), "x": h["x"], "y": h["y"]} for h in merged]
        out.append(pages)
    return out


def split_points(headings, lo: int, hi: int, taken: set[str], min_gap: int) -> list[dict]:
    """Headings inside [lo, hi] that are worth promoting to units of their own."""
    found, last = [], lo
    for p in range(lo, hi + 1):
        for h in headings.get(p, []):
            t = h["title"]
            if key(t) in taken or t.lower().startswith("bibliog") or len(t) < 4:
                continue
            if p - last >= min_gap:
                found.append({"title": t, "page": p})
                taken.add(key(t))
                last = p
    return found


def build_units(chapters: list[dict], headings, subheadings) -> list[dict]:
    for c in chapters:
        bookmarks = c["sections"]
        taken = {key(b["title"]) for b in bookmarks}
        units: list[dict] = []
        for i, b in enumerate(bookmarks):
            lo = b["page"]
            hi = (bookmarks[i + 1]["page"] if i + 1 < len(bookmarks) else c["end"] + 1) - 1
            units.append({"title": b["title"], "page": lo, "section": b["title"]})
            if hi - lo + 1 >= SPLIT_MIN_PAGES:
                for s in split_points(headings, lo, hi, taken, SPLIT_MIN_GAP):
                    units.append({**s, "section": b["title"]})
        units.sort(key=lambda u: (u["page"], u["title"] != u["section"]))

        # Second pass: whatever is still a slab of pages gets split on subheadings.
        rescued: list[dict] = []
        for i, u in enumerate(units):
            rescued.append(u)
            hi = (units[i + 1]["page"] if i + 1 < len(units) else c["end"] + 1) - 1
            if hi - u["page"] + 1 >= RESCUE_MIN_PAGES:
                for s in split_points(subheadings, u["page"], hi, taken, SPLIT_MIN_GAP):
                    rescued.append({**s, "section": u["section"]})
        rescued.sort(key=lambda u: (u["page"], u["title"] != u["section"]))

        # A unit ends where the next one begins.
        for i, u in enumerate(rescued):
            nxt = rescued[i + 1]["page"] if i + 1 < len(rescued) else c["end"] + 1
            u["endPage"] = max(nxt - 1, u["page"])
        c["units"] = rescued
        del c["sections"]
    return chapters


def main() -> int:
    pdf = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.glob("*.pdf").__next__())
    if not pdf.exists():
        print(f"✗ not found: {pdf}", file=sys.stderr)
        return 1
    tier2, tier3 = read_headings(pdf, [HEADING_FONTS, SUBHEADING_FONTS])
    chapters = build_units(read_outline(pdf, page_count(pdf)), tier2, tier3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": pdf.name, "chapters": chapters}, ensure_ascii=False, indent=1))
    total = sum(len(c["units"]) for c in chapters)
    print(f"→ {OUT.relative_to(ROOT)}")
    print(f"   {len(chapters)} chapters · {total} units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
