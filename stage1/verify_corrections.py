"""
Paper III — Stage 1c: Verification Sheet for the Stage 1b Corrections

REPORT_1B.md §1.4 records two implementation gaps found during validation, and
the tables that were extended as a consequence. Fixing them moved structural
resolution of third-party detections from 29.2% to 67.1% — and that flip is what
changed the recommendation from "report a limitation" to "build the filter".

Nothing independently verifies the corrected number. Everything downstream of it
rests on my own re-implementation being right. This module draws a small
stratified sample of the affected occurrences so a human can confirm the
corrections were correct before Stage 2 builds on them.

The four correction mechanisms
------------------------------
1. `field_label_self`  A detection whose span IS the field label rather than the
                       value ("ATTENDING PHYSICIAN" in `ATTENDING PHYSICIAN: Dr.
                       Nguyen`). Previously treated as unlabeled.
2. `provider_block`    A credential field inheriting the clinician its block is
                       about (`NPI:`, `Medical License:` under `Physician:`).
                       Previously had no owner and no inheritance.
3. `added_label`       Resolved by a field label added to FIELD_LABEL_OWNER
                       during the correction rounds.
4. `added_section`     Resolved by a section header added to SECTION_OWNER
                       during the correction rounds.

Mechanisms 3 and 4 are included because the §1.4 figure of 130 counted only what
one diagnostic probe surfaced. Enumerating the correction rounds properly gives
203 affected occurrences, and scoping the verification to mechanisms 1 and 2
alone would leave two thirds of the movement unchecked. The 203 is reported in
the sampling record.

The sample carries no classifier call and no expected answer — the reviewer
decides whose attribute each occurrence is, cold, exactly as in the main linkage
sheet. No language model is involved.

Usage
-----
    python -m stage1.verify_corrections            # 20 rows, seed 7926
    python -m stage1.verify_corrections -n 30

Outputs (stage1/artifacts/audit/)
    correction_check_v1.1.0.csv      THE FILE TO FILL IN
    correction_check_v1.1.0.html     evidence view
    correction_check_key_v1.1.0.json classifier calls (scorer/reader only)
    correction_check_record_v1.1.0.json  sampling record
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from stage1.build_inventory import load_corpus, doc_id
from stage1.sample_audit import AUDIT_DIR, DEFAULT_SEED
from stage1.sample_linkage_audit import context_span
from stage1.subject_linkage import (
    LINKAGE_VERSION, OUT_JSON as LINKAGE_PATH,
    SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS,
)
from stage1.vocabulary import VOCAB_VERSION

DEFAULT_N = 20

SHEET_PATH  = AUDIT_DIR / f"correction_check_v{LINKAGE_VERSION}.csv"
HTML_PATH   = AUDIT_DIR / f"correction_check_v{LINKAGE_VERSION}.html"
KEY_PATH    = AUDIT_DIR / f"correction_check_key_v{LINKAGE_VERSION}.json"
RECORD_PATH = AUDIT_DIR / f"correction_check_record_v{LINKAGE_VERSION}.json"

# ---------------------------------------------------------------------------
# What the correction rounds added
# ---------------------------------------------------------------------------
# Recorded explicitly so "affected by the corrections" is a reproducible
# predicate rather than a recollection. These are the exact entries added to
# FIELD_LABEL_OWNER and SECTION_OWNER after the first classification run.

CORRECTION_ADDED_LABELS: frozenset[str] = frozenset({
    # staff attribution labels
    "discharging physician", "prescribing provider", "physician signature",
    "provider signature", "clinician signature", "verification completed by",
    "attending clinician", "treating physician", "consulting physician",
    "physician on duty", "performed by", "dictated by", "transcribed by",
    "evaluator", "reviewer", "supervisor", "nurse", "nurse/ma", "nurse / ma",
    "medical assistant", "rendering provider npi", "billing provider",
    # institutional labels
    "facility name", "facility npi", "facility tax id", "group npi",
})

CORRECTION_ADDED_SECTIONS: frozenset[str] = frozenset({
    # subject-owned
    "relevant medical history", "relevant history", "clinical indication",
    "medical / psychiatric history", "medical/psychiatric history",
    "mental health assessment", "psychiatric assessment", "rx",
    "pertinent obstetric history", "clinical correlation", "claim details",
    "insurance claim form", "justification", "indication",
    "prescription on file", "current medication on file", "prescription noted",
    "current medications noted", "clinical note", "insurance plan", "diagnoses",
    "active diagnoses", "diagnosis codes", "active medications",
    "current medication", "medication requested", "charge summary",
    # staff-owned
    "physician attestation", "prescriber information", "ordering physician",
    "attending physician", "attending provider", "discharging physician",
    "prescribing physician", "referring physician", "interpreting radiologist",
    "provider details",
    # other-person
    "family history", "family medical history",
})


def mechanism(d: dict) -> str | None:
    """Which correction mechanism decided this detection, if any."""
    sig = d["signal"]
    if sig == "field_label_self":
        return "field_label_self"
    if sig == "provider_block":
        return "provider_block"
    if sig == "field_label" and (d.get("field_label") or "") in CORRECTION_ADDED_LABELS:
        return "added_label"
    if sig == "section" and (d.get("section") or "") in CORRECTION_ADDED_SECTIONS:
        return "added_section"
    return None


def allocate(total: int, buckets: list[str], sizes: dict[str, int]) -> dict[str, int]:
    """
    Equal share per mechanism, capped at availability, surplus redistributed to
    whichever mechanisms can still absorb it (largest remaining first, ties by
    name).

    Equal rather than proportional on purpose. `added_section` holds 140 of the
    203 affected occurrences, so a proportional draw would spend most of the
    sample on it and leave the two mechanisms this check exists to verify --
    `field_label_self` and `provider_block` -- with a couple of rows each.
    """
    quota = {b: 0 for b in buckets}
    remaining = total
    # Repeated equal passes, so surplus from a small bucket flows to the others.
    while remaining > 0:
        eligible = [b for b in buckets if quota[b] < sizes[b]]
        if not eligible:
            break
        share, extra = divmod(remaining, len(eligible))
        if share == 0:
            for b in sorted(eligible, key=lambda x: (-(sizes[x] - quota[x]), x))[:extra]:
                quota[b] += 1
                remaining -= 1
            break
        for b in eligible:
            take = min(share, sizes[b] - quota[b])
            quota[b] += take
            remaining -= take
    return quota


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", "--num", type=int, default=DEFAULT_N)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = p.parse_args()

    if SHEET_PATH.exists():
        with open(SHEET_PATH, encoding="utf-8-sig", newline="") as f:
            filled = sum(1 for r in csv.DictReader(f) if (r.get("true_class") or "").strip())
        if filled:
            raise SystemExit(f"{SHEET_PATH} already carries {filled} annotation(s). "
                             f"Refusing to overwrite a human pass.")

    link = json.loads(LINKAGE_PATH.read_text(encoding="utf-8"))
    records, corpus_hash = load_corpus()
    if link["corpus_sha256"] != corpus_hash:
        raise SystemExit("Corpus changed — re-run stage1.subject_linkage.")
    contents = {doc_id(i): (r.get("content") or "") for i, r in enumerate(records)}

    affected: dict[str, list[dict]] = defaultdict(list)
    for d in link["detections"]:
        m = mechanism(d)
        if m:
            affected[m].append(d)

    buckets = sorted(affected)
    sizes = {b: len(affected[b]) for b in buckets}
    quota = allocate(args.num, buckets, sizes)

    rng = random.Random(args.seed)
    picked: list[dict] = []
    for b in buckets:
        pool = sorted(affected[b], key=lambda x: (x["doc_id"], x["start"], x["information_type"]))
        rng.shuffle(pool)
        for d in pool[:quota[b]]:
            picked.append({**d, "_mechanism": b})

    picked.sort(key=lambda x: (x["_mechanism"], x["doc_id"], x["start"]))
    for i, d in enumerate(picked, 1):
        d["_row_id"] = f"C{i:03d}"

    record = {
        "artifact":        "stage1c_correction_check_record",
        "linkage_version": LINKAGE_VERSION,
        "vocab_version":   VOCAB_VERSION,
        "corpus_sha256":   corpus_hash,
        "seed":            args.seed,
        "requested_n":     args.num,
        "actual_n":        len(picked),
        "purpose": ("Independent verification of the two implementation corrections "
                    "recorded in REPORT_1B.md 1.4, which moved structural resolution "
                    "from 29.2% to 67.1% and changed the Stage 2 recommendation."),
        "affected_population": sizes,
        "affected_total":      sum(sizes.values()),
        "quota":               quota,
        "procedure": ("floor of 2 per mechanism, remainder by largest share of the "
                      "remaining affected occurrences (ties by mechanism name); within "
                      "a mechanism, occurrences sorted by (doc_id, start, type) then "
                      "shuffled with random.Random(seed); final order by "
                      "(mechanism, doc_id, start)"),
        "mechanisms": {
            "field_label_self": "detection span IS the field label, not the value",
            "provider_block":   "credential field inheriting the clinician its block is about",
            "added_label":      "field label added to FIELD_LABEL_OWNER during the corrections",
            "added_section":    "section header added to SECTION_OWNER during the corrections",
        },
    }

    cols = ["row_id", "mechanism", "doc_id", "document_type", "sensitivity_tier",
            "subject_type", "subject_name", "information_type", "value", "start",
            "region", "field_label", "section", "context_before", "context_after",
            "true_class", "notes"]
    with open(SHEET_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for d in picked:
            before, _m, after = context_span(
                contents[d["doc_id"]], d["start"], d["start"] + len(d["value"]))
            w.writerow([
                d["_row_id"], d["_mechanism"], d["doc_id"], d["document_type"],
                d["sensitivity_tier"], d["subject_type"],
                d["subject_name"] or "(organization - no individual subject)",
                d["information_type"], d["value"], d["start"], d["region"],
                d["field_label"] or "", d["section"] or "", before, after, "", "",
            ])

    KEY_PATH.write_text(json.dumps({
        "artifact": "stage1c_correction_check_key",
        "note": ("Classifier calls for the correction-check rows, kept OUT of the sheet "
                 "so the reviewer judges cold. Compare only after the pass is complete."),
        "rows": {d["_row_id"]: {"classification": d["classification"],
                                "signal": d["signal"],
                                "mechanism": d["_mechanism"],
                                "rule": d["rule"],
                                "doc_id": d["doc_id"],
                                "information_type": d["information_type"]}
                 for d in picked},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    RECORD_PATH.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    esc = html.escape
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write('<meta charset="utf-8"><title>Stage 1c - correction check</title>'
                '<style>:root{color-scheme:light dark}'
                'body{font:15px/1.55 -apple-system,Segoe UI,sans-serif;max-width:70rem;'
                'margin:2rem auto;padding:0 1rem;color:#111;background:#fff}'
                'table{border-collapse:collapse;width:100%;font-size:.83rem;margin-top:1rem}'
                'th,td{border:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}'
                'th{background:#f4f4f4} td.ctx{font-family:ui-monospace,Consolas,monospace;'
                'font-size:.76rem;color:#444} mark{background:#ffe9a8;font-weight:600}'
                '.info{border-left:4px solid #48c;background:#f3f8ff;padding:.7rem 1rem;'
                'margin:1rem 0;font-size:.9rem} code{background:#f0f0f0;padding:0 .25em}'
                'td.ans{width:7rem;background:#fffdf5;color:#bbb;text-align:center}'
                '@media (prefers-color-scheme:dark){body{background:#141414;color:#e8e8e8}'
                'th{background:#222} th,td{border-color:#333} td.ctx{color:#bbb}'
                '.info{background:#12202e;border-color:#469} code{background:#242424}'
                'td.ans{background:#1e1c14;color:#777} mark{background:#6a5410;color:#fff}}'
                '</style>\n')
        f.write("<h1>Stage 1c - correction check</h1>\n")
        f.write(f'<div class="info">These {len(picked)} occurrences were reclassified by '
                'the two implementation corrections in REPORT_1B.md 1.4 (and the label / '
                'section tables extended alongside them). Those corrections moved '
                'structural resolution from 29.2% to 67.1%, which is what changed the '
                'Stage 2 recommendation from "report a limitation" to "build the filter". '
                'Nothing has independently checked them.<br><br>'
                f'For each row, decide whose attribute the highlighted occurrence is: '
                f'<code>{SUBJECT}</code>, <code>{THIRD_PARTY}</code>, '
                f'<code>{ORGANIZATIONAL}</code>, or <code>{AMBIGUOUS}</code>. '
                'The classifier\'s own answer is deliberately not shown.<br><br>'
                f'Seed {args.seed}. Drawn from {sum(sizes.values())} affected occurrences.'
                '</div>\n')
        f.write('<table><tr><th>row</th><th>mechanism</th><th>doc</th><th>subject</th>'
                '<th>type</th><th>field label / section</th><th>occurrence in context</th>'
                '<th>true class</th></tr>')
        for d in picked:
            before, _m, after = context_span(
                contents[d["doc_id"]], d["start"], d["start"] + len(d["value"]))
            loc = " / ".join(x for x in (d["field_label"] or "", d["section"] or "") if x)
            f.write(f'<tr><td><code>{d["_row_id"]}</code></td>'
                    f'<td>{esc(d["_mechanism"])}</td>'
                    f'<td>{esc(d["doc_id"])}<br><small>{esc(d["subject_type"])}</small></td>'
                    f'<td><small>{esc(d["subject_name"] or "(org)")}</small></td>'
                    f'<td>{esc(d["information_type"])}</td>'
                    f'<td class="ctx">{esc(loc)}</td>'
                    f'<td class="ctx">...{esc(before)}<mark>{esc(d["value"])}</mark>'
                    f'{esc(after)}...</td><td class="ans">[ ]</td></tr>')
        f.write("</table>\n")

    print(f"Correction check - seed {args.seed}, {len(picked)} rows\n")
    print(f"  affected population: {sum(sizes.values())} occurrences")
    print(f"  {'mechanism':<22}{'affected':>10}{'drawn':>7}")
    print("  " + "-" * 39)
    for b in buckets:
        print(f"  {b:<22}{sizes[b]:>10}{quota[b]:>7}")
    print(f"\n  documents covered: {len({d['doc_id'] for d in picked})}")
    print(f"  types covered    : {len({d['information_type'] for d in picked})}")
    print(f"\nWrote:\n  {SHEET_PATH}   <-- fill in 'true_class'\n  {HTML_PATH}"
          f"\n  {KEY_PATH}\n  {RECORD_PATH}")


if __name__ == "__main__":
    main()
