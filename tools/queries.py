#!/usr/bin/env python3
"""Turn the ASH-SAP page map into YouTube search queries.

A unit titled "Treatment" or "Diagnosis" is meaningless on its own — roughly a
third of the 450 units are generic like that. Every query therefore carries its
chapter's clinical topic, taken from TOPICS below rather than from the chapter
title (which is often a series label: "Platelet disorders 2: ...").

    uv run python tools/queries.py > queries.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "course" / "data" / "ashsap-map.json"

# What each chapter is actually about, in the words a lecture title would use.
TOPICS = {
    1: "perioperative anticoagulation management",
    2: "outpatient hematology consultation",
    3: "hematology in pregnancy and women's health",
    4: "pediatric hematology",
    5: "hematopoietic growth factors G-CSF erythropoietin",
    6: "iron metabolism iron overload porphyria",
    7: "iron deficiency and megaloblastic anemia",
    8: "anemia of inflammation chronic disease",
    9: "anemia in systemic disease",
    10: "thalassemia and hemoglobinopathies",
    11: "sickle cell disease",
    12: "autoimmune hemolytic anemia",
    13: "red cell membrane disorders and enzymopathies",
    14: "complement PNH and thrombotic microangiopathy",
    15: "venous thromboembolism and anticoagulants",
    16: "unusual site venous thrombosis",
    17: "antiphospholipid syndrome",
    18: "cancer associated thrombosis",
    19: "inherited thrombophilia",
    20: "von Willebrand disease",
    21: "hemophilia A and B",
    22: "hereditary hemorrhagic telangiectasia and rare bleeding disorders",
    23: "immune thrombocytopenia ITP",
    24: "heparin induced thrombocytopenia and anti-PF4 disorders",
    25: "thrombotic thrombocytopenic purpura TTP",
    26: "inherited thrombocytopenia and platelet function disorders",
    27: "laboratory hematology and coagulation testing",
    28: "transfusion medicine",
    29: "therapeutic apheresis",
    30: "hematopoietic cell transplantation",
    31: "autologous stem cell transplantation",
    32: "allogeneic transplantation and graft-versus-host disease",
    33: "CAR T-cell and adoptive cellular therapy",
    34: "neutrophil disorders and histiocytosis",
    35: "inherited bone marrow failure syndromes",
    36: "chronic myeloid leukemia CML",
    37: "myeloproliferative neoplasms polycythemia vera essential thrombocythemia myelofibrosis",
    38: "systemic mastocytosis and eosinophilic neoplasms",
    39: "aplastic anemia and pure red cell aplasia",
    40: "myelodysplastic syndromes MDS and clonal hematopoiesis",
    41: "acute myeloid leukemia AML",
    42: "acute lymphoblastic leukemia ALL",
    43: "Hodgkin lymphoma",
    44: "follicular and marginal zone lymphoma",
    45: "diffuse large B-cell and Burkitt lymphoma",
    46: "T-cell lymphoma",
    47: "chronic lymphocytic leukemia CLL",
    48: "multiple myeloma and MGUS",
    49: "AL amyloidosis Waldenstrom macroglobulinemia POEMS",
}

# Headings the font-based extraction mangled: a dropped Greek glyph, a stray
# word, a truncation, two headings that ran together on one line.
TITLE_FIXES = {
    ("CH10", "-Thalassemia"): "Alpha and beta thalassemia",
    ("CH18", "Management of usual-site CAT Catheter-related thrombosis"): (
        "Management of usual-site CAT and catheter-related thrombosis"
    ),
    ("CH35", "Familial platelet disorder with associated myeloid malignancy ("): (
        "Familial platelet disorder with associated myeloid malignancy"
    ),
}
# Extraction artefacts that are not headings at all.
TITLE_DROP = {("CH4", "Children")}

# Titles too generic to search on their own — the chapter topic has to carry them.
GENERIC = re.compile(
    r"^(introduction|conclusion|treatment|diagnosis|management|prognosis|epidemiology"
    r"|biology|pathogenesis|pathophysiology|pathology|classification|therapy"
    r"|testing|causes|evaluation|clinical features|clinical presentation"
    r"|clinical manifestations|laboratory features|disease course|complications"
    r"|special populations|conclusions|gaps in knowledge|management issues"
    r"|apheresis|children)$",
    re.I,
)


def queries_for(chapter: dict, unit: dict) -> list[str]:
    topic = TOPICS[chapter["n"]]
    title = unit["title"]

    if GENERIC.match(title):
        # "Treatment" in the myelofibrosis chapter → "…myelofibrosis treatment"
        return [f"{topic} {title.lower()}", f"{topic} {title.lower()} lecture hematology"]

    # A title that already names its own disease searches well on its own; the
    # third query adds chapter context for the ones that turn out not to.
    return [title, f"{title} hematology lecture", f"{topic} {title.lower()}"]


def main() -> int:
    blob = json.loads(MAP.read_text())
    out = []
    for c in blob["chapters"]:
        code = f"CH{c['n']}"
        kept = 0
        for u in c["units"]:
            if (code, u["title"]) in TITLE_DROP:
                continue
            u["title"] = TITLE_FIXES.get((code, u["title"]), u["title"])
            kept += 1
            out.append(
                {
                    "unit": f"ch{c['n']}-u{kept}",
                    "title": u["title"],
                    "chapter": code,
                    "page": u["page"],
                    "endPage": u["endPage"],
                    "section": u["section"],
                    "queries": queries_for(c, u),
                }
            )
        c["units"] = [u for u in c["units"] if (code, u["title"]) not in TITLE_DROP]
    MAP.write_text(json.dumps(blob, ensure_ascii=False, indent=1))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print(f"\n· {len(out)} units, {sum(len(o['queries']) for o in out)} queries", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
