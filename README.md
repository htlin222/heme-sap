# heme-sap

A video lecture for every section of the **ASH-SAP 9th edition** — 49 chapters, 449 sections,
each mapped to its page number and to the best freely available lecture that teaches it.

Built for **hematology fellows**. Not for medical students, and deliberately hostile to the
review-video tier that dominates hematology on YouTube.

**Live**: <https://heme-sap.pages.dev>

---

## Why this exists

ASH-SAP is dense, and it is a book. When a section does not land, there is no obvious next
move — YouTube search for "myelodysplastic syndrome" returns a 12-minute USMLE mnemonic
video before it returns anything a fellow can use.

This is the index that closes that gap. You read a section, it does not land, you look it up
here by its page number, and you get a lecture pitched at the right level. Then you go back
to the book.

## What is in it

| | |
|---|---|
| Chapters | 49 |
| Sections (units) | 449 |
| Core lectures | 438 |
| Sections honestly left empty | 11 |
| Supplementary videos | 959 |
| Video slots / distinct videos | 1,408 / 1,291 |
| Total runtime | 675 h 47 min |
| Sections with cited landmark evidence | 33 (57 PubMed-verified references, 57/57 re-checked live) |

Every unit carries the ASH-SAP page it maps to, a self-check question, one core lecture, and
up to four supplementary videos tagged **mechanism**, **clinical decision**, or
**trial & guideline**.

## The three claims this repo makes, and how each is enforced

**1. No video ID was ever invented.** Curation could only select from candidate pools
produced by real `yt-dlp` searches. `tools/check_picks.py` re-validates every chosen ID
against the pool it came from and fails on anything it cannot trace — so a plausible-looking
eleven-character string has no path into the course.

**2. Every link is confirmed live and embeddable.** `tools/yt_meta.py` asks YouTube's oEmbed
endpoint about each chosen video; 401/403/404 means pulled, private, or embed-disabled, and
since the site embeds its player an embed-disabled video counts as broken here even though it
still plays on YouTube. Seventeen videos failed that check on the first run and were replaced.

Runtimes, view counts and channel names come from the search results that found each video,
not from a second per-video extraction — YouTube now demands browser cookies for that at any
volume, and borrowing a human's session to refresh a view count is a bad trade. Every record
is stamped `"source": "search"` so nobody mistakes those for live figures. What this buys is
that runtimes are YouTube's own numbers rather than a curator's transcription, which is what
the 30-second drift check in `make audit` is actually guarding.

**3. Every PMID came from the PubMed API.** `tools/pubmed.py` resolves trials named in prose
and then *checks the returned title actually matches* — relevance ranking alone happily
answers "BRIDGE trial" with a 2026 review that merely cites it, and answers "PERSEUS" with
the plain-language summary. References it cannot resolve are dropped and reported, never
guessed. `make verify` re-checks all of them against the live API.

## The empty slots are the point

11 sections have no core lecture. Each says what was searched and why nothing qualified.
That is a finding, not a gap to be papered over — YouTube genuinely has nothing at fellowship
level on nonsecretory myeloma, cation permeability defects, the TFH immunophenotype, or
salvage chemotherapy for germ cell tumours.

The first pass left 38 blank. Most of those turned out to be artefacts of search rather than
of the world: "CAT" returns veterinary videos, "permeability" returns soil mechanics, "PCT"
returns bodybuilding post-cycle therapy, and "APLAs" returns Polish Minecraft. A second pass
re-searched those 54 units on drug names and eponyms instead of section titles and filled 27
of them — including all six blank sections of the iron-deficiency chapter.

One unit moved the other way: a first-pass pick for the treatment of porphyria cutanea tarda
was withdrawn on review because it was exam-prep dermatology, below the bar this course sets.

## Build

Needs [uv](https://docs.astral.sh/uv/), `yt-dlp`, and `mupdf-tools` + `poppler` for the
structure extraction. The build scripts themselves use only the standard library.

```bash
make build     # course/ → dist/, enforcing per-chapter quotas
make audit     # offline: config, quotas, runtimes, evidence depth — no network, deterministic
make validate  # offline: every video traces to a real search result, is live, correctly timed
make meta      # re-check embeddability of every linked video (oEmbed)
make verify    # online: re-checks every YouTube link and every PMID
make serve     # http://localhost:8899
make check     # lint + build + audit + validate — run before committing
make deploy    # Cloudflare Pages
```

Current state: `make check` passes with **zero errors** and four warnings, each deliberate —
11 honest blanks, 3 videos outside the nominal runtime band, 21 below 25 views (fellowship
content is low-view by nature), and evidence citations on 33 of 449 sections by design.

## Regenerating the course from scratch

The structure is derived from the book, not typed by hand. With the ASH-SAP 9e PDF present:

```bash
python3 tools/extract_ashsap.py "ASH-SAP_9e.pdf"      # → course/data/ashsap-map.json, 449 units
python3 tools/queries.py > queries.json               # 3 search queries per unit
python3 tools/yt_pool.py queries.json pools/pools.json --per=10 --jobs=8
python3 tools/rank_pool.py pools/pools.json queries.json shortlists.json --top=12
#   … curate: pick from shortlists into course/data/ch<N>.json …
python3 tools/check_picks.py packet.json course/data/ch*.json     # per-packet gate
python3 tools/yt_meta.py --pools=pools/pools.json,pools/repools.json
python3 tools/make_config.py --sync                   # freeze quotas into course.config.json
python3 tools/validate.py pools/*.json                # whole-course gate
```

`pools/` is committed on purpose: it is the evidence for claim 1. Anyone can re-run
`tools/validate.py` and confirm that every one of the 1,291 video IDs on the site appears in a
stored search result, and that none was typed from memory.

`tools/extract_ashsap.py` combines two independent signals so neither has to be trusted
alone: the PDF's own outline (authoritative for chapter and section identity) and body
headings recovered from font metrics (used only to subdivide bookmarked sections running
four or more pages, so no unit ever points at a slab of the book too big to search). 305 of
the 449 units resolve to a single page.

`tools/channels.json` holds the channel policy — the fellowship-level bar as data, not code.

## Copyright

**The ASH-SAP text is not reproduced anywhere in this repository or on the site.** What is
stored is a page map: chapter titles, section titles and page numbers. Self-check questions
are written from scratch, not lifted from the book's KEY POINTS boxes.

ASH-SAP is published by the American Society of Hematology. This project is not affiliated
with, endorsed by, or sponsored by ASH, and is not a substitute for the book.

**Videos remain the copyright of their YouTube channels.** This project stores links and
public metadata only; it neither rehosts nor mirrors any video.

Framework code is MIT (see [LICENSE](LICENSE)), forked from
[curate-course](https://github.com/htlin222/curate-course). Lucide icons are ISC.

## Not medical advice

A study aid for trainees. It does not establish standard of care. Videos are third-party
recordings of varying age, and hematology moves faster than YouTube does — verify anything
that affects patient care against the current ASH, NCCN or ESMO guideline and the primary
literature.
