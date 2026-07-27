#!/usr/bin/env python3
"""Resolve landmark-trial references to real PMIDs via PubMed E-utilities.

The input names trials in prose ("ASPEN trial zanubrutinib Waldenstrom"); the
output carries PMIDs, titles, journals and years that came back from NCBI. A
citation that cannot be resolved is dropped and reported, never guessed — an
invented PMID is worse than a missing one, because it looks checkable.

    uv run python tools/pubmed.py evidence-draft.json course/data/oe-evidence.json
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
UA = {"User-Agent": "heme-sap-companion/1.0 (course build script)"}


def get(url: str, params: dict, attempts: int = 4) -> dict:
    """NCBI rate-limits without warning; a dropped request must not silently
    become a dropped citation."""
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=UA)
    for n in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode())
        except Exception:
            if n == attempts - 1:
                raise
            time.sleep(1.5 * (n + 1))
    raise RuntimeError("unreachable")


STOP = set(
    """a an the of in on for with from at by is are be as and or to versus vs
    randomized randomised trial study phase open label double blind placebo
    controlled multicentre multicenter patients patient treatment therapy""".split()
)


def content(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 2}


# Titles that name the right trial but are not its primary report. Searching for
# "PERSEUS" cheerfully returns the plain-language summary; searching for ZUMA-7
# returns the patient-reported-outcomes paper. Neither is the citation wanted.
DERIVATIVE = re.compile(
    r"\b(plain language summary|patient-reported|quality of life|cost-effectiveness"
    r"|cost effectiveness|sub-?analysis|subgroup analysis|post ?hoc|exploratory analysis"
    r"|long-term (follow-?up|outcomes)|\d+-year follow-?up|final analysis|updated (safety|results)"
    r"|real-?world|indirect comparison|network meta-?analysis|matching-adjusted"
    r"|study (design|protocol)|rationale and design|statistical analysis plan"
    r"|correction to|erratum|commentary|editorial|pharmacokinetic|ethnic sensitivity"
    r"|health-related|budget impact|systematic review)\b",
    re.I,
)

# Where the practice-changing report is most likely to have appeared.
PRIMARY_JOURNALS = {
    "n engl j med": 0.30, "lancet": 0.25, "lancet oncol": 0.25, "lancet haematol": 0.25,
    "jama": 0.22, "jama oncol": 0.22, "jama intern med": 0.22,
    "blood": 0.20, "blood adv": 0.18, "j clin oncol": 0.20, "bmj": 0.18,
    "haematologica": 0.12, "leukemia": 0.12, "arthritis rheumatol": 0.12,
    "circulation": 0.18, "ann intern med": 0.18,
}


def resolve(query: str, min_overlap: float = 0.55) -> dict | None:
    """Find the paper a query names, and refuse to return anything else.

    Relevance ranking alone is not enough: PubMed happily answers "BRIDGE trial
    perioperative bridging" with a 2026 review that merely cites it. So the
    candidate's own title has to account for most of the query's content words,
    otherwise nothing is returned and the citation is dropped.
    """
    # "…title words @N Engl J Med" narrows the search to one journal without the
    # journal name polluting the title-overlap score.
    term, _, journal = query.partition("@")
    term = term.strip()
    # PubMed field tags ("2013[dp]") steer the search but must not count against
    # the title-overlap score, since no title contains them.
    want = content(re.sub(r"\S*\[\w+\]|\bAND\b", " ", term))
    if journal.strip():
        term = f'{term} AND "{journal.strip()}"[ta]'
    try:
        found = get(
            ESEARCH,
            {"db": "pubmed", "term": term, "retmode": "json", "retmax": "10", "sort": "relevance"},
        )
        ids = found["esearchresult"].get("idlist") or []
        if not ids:
            return None
        time.sleep(0.36)  # NCBI asks for <= 3 requests/second without a key
        summary = get(ESUMMARY, {"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
    except Exception as e:  # network, rate limit, unexpected shape
        print(f"  ✗ {query[:60]}: {type(e).__name__}", file=sys.stderr)
        return None

    best, best_score = None, 0.0
    for pmid in ids:
        rec = summary["result"].get(pmid) or {}
        title = (rec.get("title") or "").rstrip(".")
        if not title:
            continue
        score = len(want & content(title)) / max(len(want), 1)
        # An exact trial acronym in the title is evidence this is the right trial —
        # but not evidence that this is the trial's primary report.
        acronyms = {w for w in re.findall(r"\b[A-Z][A-Z0-9-]{3,}\b", query)}
        if acronyms and any(a.lower() in title.lower() for a in acronyms):
            score += 0.15
        score += PRIMARY_JOURNALS.get((rec.get("source") or "").lower(), 0.0)
        if DERIVATIVE.search(title):
            score -= 0.60
        if score > best_score:
            best, best_score = (pmid, rec, title), score

    if best is None or best_score < min_overlap:
        return None
    pmid, rec, title = best
    return {
        "pmid": pmid,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
        "title": title,
        "journal": rec.get("source", ""),
        "year": (rec.get("pubdate", "") or "")[:4],
        "match": round(best_score, 2),
    }


def main() -> int:
    draft = json.loads(Path(sys.argv[1]).read_text())
    out, dropped = [], []
    for cond in draft["conditions"]:
        cites = []
        for q in cond.pop("queries", []):
            hit = resolve(q)
            time.sleep(0.36)
            if hit is None:
                dropped.append((cond["unit"], q))
                continue
            print(
                f"  {cond['unit']:<12} {hit['pmid']:>9} m={hit['match']}  "
                f"{hit['journal']} {hit['year']} · {hit['title'][:64]}"
            )
            cites.append({k: v for k, v in hit.items() if k != "match"})
        cond["citations"] = cites
        out.append(cond)

    Path(sys.argv[2]).write_text(json.dumps({"conditions": out}, ensure_ascii=False, indent=1))
    total = sum(len(c["citations"]) for c in out)
    print(f"\n→ {sys.argv[2]}  ·  {len(out)} units · {total} verified citations")
    if dropped:
        print(f"✗ {len(dropped)} queries resolved to nothing and were dropped:")
        for unit, q in dropped:
            print(f"   · {unit}: {q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
