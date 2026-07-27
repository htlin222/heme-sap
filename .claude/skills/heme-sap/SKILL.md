---
name: heme-sap
description: Use when maintaining the Heme SAP Companion — replacing a video that went dead or embed-disabled, filling or re-searching a section that is blank, adding landmark-trial citations, refreshing metadata, or re-deriving the page map from a new ASH-SAP edition. Enforces that no video ID or PMID may be invented.
---

# Maintaining the Heme SAP Companion

An index mapping all 449 sections of ASH-SAP 9e to fellowship-level video lectures.
The curation standard lives in `docs/VIDEO_SPEC.md` — read it before changing any pick.

## Non-negotiable

1. **Never write a video ID that is not already in `pools/`.** Add candidates by running a
   search, not by remembering one. `tools/validate.py` fails the build otherwise.
2. **Never write a PMID by hand.** `tools/pubmed.py` resolves trials named in prose and
   verifies the returned title matches; unresolvable references are dropped, not guessed.
3. **No ASH-SAP text anywhere.** Section titles and page numbers only. Self-check questions
   are written from scratch.
4. **An empty slot with a note beats a padded one.** Blanks are findings about YouTube's
   coverage, not defects to hide.

## The gates

```bash
make check      # lint + build + audit + validate — everything offline and deterministic
make meta       # re-ask YouTube which links are still live and embeddable
make verify     # re-check every link and every PMID against the live APIs
```

`make check` currently passes with zero errors and four accepted warnings (11 blanks, 3
videos outside the nominal runtime band, 21 under 25 views, evidence on 33 of 449 sections).
If a change adds a fifth warning class, that is a regression worth explaining.

## Task: a video went dead

`make meta` reports them. oEmbed 401/403/404 means pulled, private, or **embed-disabled** —
the last still plays on YouTube but breaks this site, which embeds its player.

```bash
make meta                                          # find them
# put the affected unit ids into a queries file, then:
python3 tools/yt_pool.py requeries.json pools/repools-2.json --per=12 --jobs=6
python3 tools/rank_pool.py pools/repools-2.json requeries.json shortlist.json --top=12
# edit course/data/ch<N>.json, picking only from that shortlist
python3 tools/yt_meta.py --pools=pools/pools.json,pools/repools.json,pools/repools-2.json
python3 tools/make_config.py --sync                # quotas follow the data
make check
```

Keep every pool file. They are the evidence for claim 1 in the README, and `validate` needs
all of them on its command line.

## Task: a section is blank and should not be

Check first whether the original query was defeated by an ambiguous section title — that
accounted for most of the first pass's blanks. Search on drug names, eponyms and gene
symbols instead of the book's heading, then follow the same loop as above.

## Task: add landmark-trial evidence to a section

Write a draft entry keyed by unit id with `summary`, `practice`, `red_flags`, `caveats` and
a `queries` list naming the trials in prose, then:

```bash
python3 tools/pubmed.py evidence-draft.json course/data/oe-evidence.json
```

The resolver prefers primary reports over derivatives — searching "PERSEUS" otherwise returns
the plain-language summary, and "ZUMA-7" returns the patient-reported-outcomes paper. Append
`@N Engl J Med` to a query to pin it to a journal. **Read the printed titles.** Anything that
resolved to the wrong paper must have its query fixed or be dropped.

## Task: a new ASH-SAP edition

```bash
python3 tools/extract_ashsap.py "ASH-SAP_10e.pdf"
```

This re-derives `course/data/ashsap-map.json` from the PDF outline plus font-metric heading
recovery. Unit ids are positional (`ch36-u10`), so a changed section order silently
re-points existing picks — diff the map before trusting any carried-over curation.

## Layout

```
course/course.config.json   site copy, chapters, quotas, audit thresholds
course/data/ch<N>.json      one file per chapter — the curation
course/data/ashsap-map.json the page map, derived from the PDF
course/data/oe-*.json       evidence cards and the three stance cards
course/data/video-meta.json liveness + search-time runtimes
pools/                      every candidate a search ever returned
tools/                      extraction, search, ranking, validation, PubMed
src/                        the framework; topic-agnostic, rarely needs touching
```
