# Curation spec

The brief every curation pass follows. It is written down because "pick good videos" is not
an instruction anyone can check, and because the same judgement has to hold across 449
sections curated by different passes months apart.

## The one rule that cannot be broken

**Only video IDs that appear in a stored candidate pool may be used.**

Pools live in `pools/` and were produced by real `yt-dlp` searches. A curator — human or
agent — reads a shortlist and picks from it. Nobody types an ID from memory, reconstructs one
they think they remember, or "corrects" one that looks wrong. `tools/validate.py` re-checks
every ID against the pools and fails on anything it cannot trace, so this is enforced rather
than trusted.

Copy `id`, `seconds`, `channel` and `title` verbatim out of the candidate object. Durations
are compared against YouTube's own figure and fail on more than 30 seconds of drift, which
catches transcription errors.

## Audience: hematology fellows

This is the decision that shapes everything else. The reader has finished residency and is
studying for boards. Content pitched below that is not merely unhelpful, it is misleading —
it implies the topic is simpler than the book is treating it.

**Reject outright**

- Med-student and exam-prep channels: Osmosis, Ninja Nerd, Medicosis Perfectionalis, Armando
  Hasudungan, Dirty Medicine, Zero To Finals, Dr. Najeeb, Khan Academy, anything branded
  USMLE / NCLEX / NEET / PANCE.
- Patient-facing content: patient journeys, survivor stories, "what is X?" explainers,
  awareness and fundraising videos. Note this is a judgement about *content*, not channel —
  disease foundations (HealthTree, the International Myeloma Foundation, AAMDSIF, Lymphoma
  Research Foundation) post both patient education and genuine clinician-to-clinician
  sessions, and the scientific sessions are welcome.
- Conference teasers under about two minutes that announce a result without explaining it,
  unless the result itself is the whole section.
- Treatment content overtaken by practice change. See below.

**Prefer, roughly in this order**

1. Societies: ASH, EHA, ESH, EBMT, ISTH, AABB, ASTCT.
2. Journals: NEJM, Lancet, JAMA, Blood, JCI, Mayo Clinic Proceedings.
3. VJHemOnc, ecancer, and similar clinician-interview series.
4. Academic centres: MD Anderson, Dana-Farber, Mayo, Hopkins, Stanford, Fred Hutch, and
   university grand rounds generally.
5. Disease-foundation scientific sessions: MDS Foundation, AAMDSIF, WFH, NBDF.
6. CME publishers: OncLive, HMP Global, PeerView, Clinical Care Options, Medscape.

`tools/channels.json` encodes this as data. The `tier` it produces is a crude channel-name
match and is wrong in both directions — "Blood Bank Guy" scores `unknown` and is the best
transfusion-medicine source in the pool; a society channel can still have posted a patient
story. **Judge the video, not the tier.**

## Currency

Treatment recommendations expire; biology does not.

Apply a recency filter to anything that tells the reader what to give. Between ASH-SAP 9e and
now: MDS classification was rewritten twice and IPSS-M replaced IPSS-R; CAR-T moved to second
line in large B-cell lymphoma; quadruplet induction became standard in myeloma; momelotinib,
pirtobrutinib, asciminib and the menin inhibitors arrived. A lecture recorded before those is
not dated, it is wrong.

Apply no recency filter to mechanism, physiology, morphology, classification or
pathophysiology. A 2014 lecture on the complement cascade is still correct.

Where the best available video predates the current standard, say so in the `why` field
rather than quietly shipping it.

## Empty is a legitimate answer

If nothing in the pool clears the bar, set `"url": null` and write a `note` saying what was
searched and why it did not qualify. Do not pad. A related-but-wrong video costs the reader
more time than a blank does, and it hides the finding that the open web does not cover this.

Eleven sections currently ship blank. Many more were blank until a second pass found that the
first search had been defeated by an ambiguous section title — "CAT" returns veterinary
videos, "permeability" returns soil mechanics, "PCT" returns bodybuilding post-cycle therapy,
"APLAs" returns Polish Minecraft. Before accepting a blank, check that the query actually
described the topic: search on drug names, eponyms and gene symbols rather than the book's
section heading.

## Per-unit shape

- `assessment` — required, at least 80 characters. A question the reader can answer to test
  whether the section landed, not a description of the topic. **Write it from scratch.**
  ASH-SAP's KEY POINTS are copyrighted and none of that text may appear here.
- `lesson` — the single best video for the section, with a one-sentence `why` explaining what
  it does for *this* section specifically.
- `drills` — 0 to 4 supplementary videos, each tagged `mechanism`, `clinical` or `trial`.
  Weight by exam yield, not evenly: a high-yield topic earns four, a narrow one earns none.
- Never use the same video twice inside one unit. Reuse across units is allowed and sometimes
  right — one good overview can serve three adjacent sections.

## Gates

```bash
python3 tools/check_picks.py packet.json course/data/ch*.json   # during a curation pass
python3 tools/validate.py pools/*.json                          # whole course, any time
make check                                                      # lint + build + audit + validate
```
