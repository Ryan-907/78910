"""
Paper III — Stage 1c: Linkage Audit Sheet

Extends the existing 25-document tagger audit with a subject-linkage judgement,
so one human pass measures both pipelines. Additive: the tagger sheet
(`audit_sheet_v1.0.0.csv`), its seed (7926), and its 25-document sample are
untouched, and this module never writes to them.

The error direction that governs the design
-------------------------------------------
Stage 1b's caveat had the asymmetry backwards. The two directions are not
symmetric, and the safe one is the one it named:

  FALSE `subject`  (classifier says subject, truth is third_party/organizational)
      An extra type stays in the inventory. The gate governs something it need
      not, and the result is an OVER-BLOCK: a flow denied that should have been
      permitted. Visible, traceable, someone complains, it gets fixed.

  FALSE `third_party` / `organizational`  (the classifier filters out something
  that was genuinely the subject's)
      The type leaves the inventory entirely. The fifth check can never govern
      it — not incorrectly, but *at all*. The document is released, the recipient
      holds an information type they should not, the decision looks perfectly
      correct, and nothing anywhere records that it happened. The subject's own
      home address absorbed by a letterhead rule, their phone caught by a
      switchboard pattern, a staff member's own attribute on an employment-tier
      document misfiled as organizational.

So the priority quantity is PRECISION ON THE FILTERED CLASSES. Recall on
`subject` is the secondary number. This mirrors the Stage 1 tagger-miss
asymmetry one layer up.

Sheet structure — two blocks, both censuses
-------------------------------------------
BLOCK A  every detection in the 25 audit documents (311 rows).
         Gives recall on `subject`, the full four-way confusion matrix, and
         alignment with the tagger pass on the same documents.

BLOCK B  every remaining `third_party` / `organizational` detection in the
         corpus (176 rows).
         Block A alone contains only 50 of the 226 filtered detections, which
         would make the priority number an estimate on thin support. Together
         the two blocks CENSUS all 226, so precision on `third_party` and on
         `organizational` is exact — no sampling error, no interval.

Neither block is drawn at random, so this module needs no seed and no RNG. Row
order is deterministic: (block, doc_id, start, information_type).

The classifier's call is NOT in the sheet
-----------------------------------------
`true_class` is blank and the reviewer fills it cold. The classifier's decision
and its signal go to a separate key file that only the scorer reads. A sheet that
shows its own answer collects confirmation, not judgement.

No language model is involved at any point — not for classification, not to
generate candidate answers, not as a pre-fill. A pre-filled sheet produces
agreement rather than ground truth.

Usage
-----
    python -m stage1.sample_linkage_audit

Outputs (stage1/artifacts/audit/)
    linkage_sheet_v1.1.0.csv           THE FILE TO FILL IN
    linkage_review_v1.1.0.html         evidence view, grouped by document
    linkage_key_v1.1.0.json            classifier calls + signals (scorer only)
    linkage_audit_record_v1.1.0.json   construction record
"""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from pathlib import Path

from stage1.build_inventory import ARTIFACT_VERSION, load_corpus, doc_id
from stage1.sample_audit import AUDIT_DIR
from stage1.subject_linkage import (
    LINKAGE_VERSION, OUT_JSON as LINKAGE_PATH,
    SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS,
)
from stage1.vocabulary import VOCAB_VERSION

TAGGER_SAMPLE_PATH = AUDIT_DIR / f"audit_sample_v{ARTIFACT_VERSION}.json"

SHEET_PATH  = AUDIT_DIR / f"linkage_sheet_v{LINKAGE_VERSION}.csv"
HTML_PATH   = AUDIT_DIR / f"linkage_review_v{LINKAGE_VERSION}.html"
KEY_PATH    = AUDIT_DIR / f"linkage_key_v{LINKAGE_VERSION}.json"
RECORD_PATH = AUDIT_DIR / f"linkage_audit_record_v{LINKAGE_VERSION}.json"

FILTERED_CLASSES = (THIRD_PARTY, ORGANIZATIONAL)
CONTEXT_CHARS = 170


def context_span(text: str, start: int, end: int) -> tuple[str, str, str]:
    """(before, matched, after) with newlines flattened, for one-line display."""
    def flat(s: str) -> str:
        return " / ".join(s.splitlines())
    return (flat(text[max(0, start - CONTEXT_CHARS):start]),
            flat(text[start:end]),
            flat(text[end:end + CONTEXT_CHARS]))


def build_rows() -> tuple[list[dict], dict]:
    link = json.loads(LINKAGE_PATH.read_text(encoding="utf-8"))
    records, corpus_hash = load_corpus()
    if link["corpus_sha256"] != corpus_hash:
        raise SystemExit(
            "Corpus changed since linkage was built — re-run stage1.subject_linkage.")
    dets = link["detections"]

    sample = json.loads(TAGGER_SAMPLE_PATH.read_text(encoding="utf-8"))
    sampled_ids = set(sample["doc_ids"])
    contents = {doc_id(i): (r.get("content") or "") for i, r in enumerate(records)}

    block_a = [d for d in dets if d["doc_id"] in sampled_ids]
    block_b = [d for d in dets
               if d["doc_id"] not in sampled_ids
               and d["classification"] in FILTERED_CLASSES]

    rows: list[dict] = []
    for block, source in (("A", block_a), ("B", block_b)):
        for d in sorted(source,
                        key=lambda x: (x["doc_id"], x["start"], x["information_type"])):
            before, _matched, after = context_span(
                contents[d["doc_id"]], d["start"], d["start"] + len(d["value"]))
            rows.append({
                "block":            block,
                "doc_id":           d["doc_id"],
                "document_type":    d["document_type"],
                "sensitivity_tier": d["sensitivity_tier"],
                "subject_type":     d["subject_type"],
                "subject_name":     d["subject_name"] or "(organization - no individual subject)",
                "information_type": d["information_type"],
                "value":            d["value"],
                "start":            d["start"],
                "region":           d["region"],
                "field_label":      d["field_label"] or "",
                "section":          d["section"] or "",
                "context_before":   before,
                "context_after":    after,
                # withheld from the sheet, written to the key instead
                "_classification":  d["classification"],
                "_signal":          d["signal"],
                "_rule":            d["rule"],
            })

    for i, r in enumerate(rows, 1):
        r["row_id"] = f"L{i:04d}"

    record = {
        "artifact":        "stage1c_linkage_audit_record",
        "linkage_version": LINKAGE_VERSION,
        "vocab_version":   VOCAB_VERSION,
        "corpus_sha256":   corpus_hash,
        "rows_total":      len(rows),
        "block_a": {
            "definition": "every detection in the 25 tagger-audit documents",
            "documents":  len(sampled_ids),
            "rows":       len(block_a),
            "inherits_sample_from": str(TAGGER_SAMPLE_PATH).replace("\\", "/"),
            "tagger_sample_seed":   sample["seed"],
        },
        "block_b": {
            "definition": ("every third_party / organizational detection NOT already in "
                           "Block A; together with Block A this censuses every filtered "
                           "detection in the corpus"),
            "documents":  len({d["doc_id"] for d in block_b}),
            "rows":       len(block_b),
        },
        "filtered_census": {
            "filtered_detections_corpus_wide":
                sum(1 for d in dets if d["classification"] in FILTERED_CLASSES),
            "covered_by_sheet":
                sum(1 for r in rows if r["_classification"] in FILTERED_CLASSES),
        },
        "randomness": ("none - both blocks are censuses; row order is "
                       "(block, doc_id, start, information_type)"),
        "classifier_calls_withheld_to": str(KEY_PATH).replace("\\", "/"),
        "documents_touched": len(sampled_ids | {d["doc_id"] for d in block_b}),
    }
    return rows, record


SHEET_COLS = [
    "row_id", "block", "doc_id", "document_type", "sensitivity_tier",
    "subject_type", "subject_name", "information_type", "value", "start",
    "region", "field_label", "section", "context_before", "context_after",
    "true_class",   # <-- ANNOTATOR FILLS THIS
    "notes",
]


def write_sheet(rows: list[dict]) -> None:
    with open(SHEET_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(SHEET_COLS)
        for r in rows:
            w.writerow([r.get(c, "") for c in SHEET_COLS])


def write_key(rows: list[dict]) -> None:
    KEY_PATH.write_text(json.dumps({
        "artifact":        "stage1c_linkage_key",
        "linkage_version": LINKAGE_VERSION,
        "vocab_version":   VOCAB_VERSION,
        "note": ("The classifier's calls, deliberately kept OUT of the review sheet so "
                 "the human judges cold. Read by stage1.score_linkage only. Do not "
                 "consult while annotating."),
        # `value` and `start` are carried here as well as in the sheet because a
        # spreadsheet round-trip is lossy: Excel rewrites anything date-shaped, so
        # a `date_of_birth` of "1960-12-04" comes back as the serial 22254. Scoring
        # joins on row_id and reads only true_class, so numbers are unaffected, but
        # the error report should quote the real value rather than the serial.
        "rows": {r["row_id"]: {
            "classification":   r["_classification"],
            "signal":           r["_signal"],
            "rule":             r["_rule"],
            "information_type": r["information_type"],
            "doc_id":           r["doc_id"],
            "region":           r["region"],
            "block":            r["block"],
            "value":            r["value"],
            "start":            r["start"],
        } for r in rows},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


HTML_HEAD = """<meta charset="utf-8">
<title>Paper III Stage 1c - linkage audit</title><style>
:root{color-scheme:light dark}
body{font:15px/1.55 -apple-system,Segoe UI,sans-serif;max-width:72rem;margin:2rem auto;
     padding:0 1rem;color:#111;background:#fff}
h1{font-size:1.45rem;margin-bottom:.2rem}
.meta{color:#555;font-size:.85rem;margin-bottom:1.1rem}
.warn{border-left:4px solid #b34;background:#fff5f5;padding:.7rem 1rem;margin:1rem 0;font-size:.9rem}
.info{border-left:4px solid #48c;background:#f3f8ff;padding:.7rem 1rem;margin:1rem 0;font-size:.9rem}
.doc{border:1px solid #ddd;border-radius:7px;padding:.9rem 1.1rem;margin-bottom:1.2rem}
.hdr{font-size:.82rem;color:#555;font-family:ui-monospace,Consolas,monospace;margin-bottom:.6rem}
.hdr b{color:#111;font-size:.98rem}
table{border-collapse:collapse;width:100%;font-size:.82rem}
th,td{border:1px solid #ddd;padding:.34rem .5rem;text-align:left;vertical-align:top}
th{background:#f4f4f4;font-weight:600}
td.ctx{font-family:ui-monospace,Consolas,monospace;font-size:.76rem;color:#444}
mark{background:#ffe9a8;padding:0 .15em;border-radius:2px;font-weight:600}
td.ans{width:7rem;background:#fffdf5;color:#bbb;text-align:center}
code{background:#f0f0f0;padding:0 .25em;border-radius:3px}
@media (prefers-color-scheme:dark){
 body{background:#141414;color:#e8e8e8}
 th{background:#222} th,td{border-color:#333} .doc{border-color:#333}
 td.ctx{color:#bbb} td.ans{background:#1e1c14;color:#777}
 .warn{background:#2a1618;border-color:#c55} .info{background:#12202e;border-color:#469}
 mark{background:#6a5410;color:#fff} code{background:#242424}
}
</style>
"""


def write_html(rows: list[dict], record: dict) -> None:
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r["doc_id"], []).append(r)

    esc = html.escape
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(HTML_HEAD)
        f.write("<h1>Paper III Stage 1c - subject-linkage audit</h1>\n")
        f.write(f'<div class="meta">vocabulary v{VOCAB_VERSION} &nbsp;| &nbsp;'
                f'linkage v{LINKAGE_VERSION} &nbsp;| &nbsp;{record["rows_total"]} rows '
                f'across {record["documents_touched"]} documents &nbsp;| &nbsp;'
                f'Block A {record["block_a"]["rows"]} &nbsp;| &nbsp;'
                f'Block B {record["block_b"]["rows"]}</div>\n')
        f.write(
            '<div class="warn"><b>Filtering something out is the dangerous direction.</b> '
            'If you mark a detection <code>third_party</code> or <code>organizational</code>, '
            'that information type leaves the inventory and the future gate check can never '
            'govern it. The document is released, the recipient holds a type they should not, '
            'the decision looks correct, and nothing records that it happened. A wrong '
            '<code>subject</code> call only causes an over-block, which is visible and '
            'correctable. <b>When genuinely torn, prefer <code>subject</code> or '
            '<code>ambiguous</code> over filtering.</b></div>\n')
        f.write(
            '<div class="info"><b>For each highlighted occurrence, whose attribute is it?</b>'
            f'<br><code>{SUBJECT}</code> - about this document’s data subject (named in '
            'the document header below)'
            f'<br><code>{THIRD_PARTY}</code> - about some other individual: a signing '
            'clinician, a relative, a colleague'
            f'<br><code>{ORGANIZATIONAL}</code> - belongs to the institution rather than any '
            'individual: clinic address, facility NPI, main phone, statutory notice'
            f'<br><code>{AMBIGUOUS}</code> - not decidable from what is shown. A real answer; '
            'use it rather than guessing.'
            '<br><br>Remember the <b>employment inversion</b>: where <code>subject_type</code> '
            'is <code>employee</code> or <code>contractor</code>, the subject IS staff, so a '
            'clinician’s name, job title, licence and salary are <code>subject</code>.'
            f'<br><br>Record answers in <code>linkage_sheet_v{LINKAGE_VERSION}.csv</code>, '
            'in the <code>true_class</code> column, matched by <code>row_id</code>. Then run '
            '<code>python -m stage1.score_linkage</code>.</div>\n')

        for did in sorted(by_doc):
            rs = by_doc[did]
            first = rs[0]
            f.write('<div class="doc">')
            f.write(f'<div class="hdr"><b>{esc(did)}</b> &nbsp; '
                    f'{esc(first["document_type"])} &nbsp;| &nbsp;'
                    f'{esc(first["sensitivity_tier"])} &nbsp;| &nbsp;'
                    f'subject_type <b>{esc(first["subject_type"])}</b> &nbsp;| &nbsp;'
                    f'subject <b>{esc(first["subject_name"])}</b> &nbsp;| &nbsp;'
                    f'{len(rs)} rows</div>')
            f.write('<table><tr><th>row</th><th>type</th><th>region</th>'
                    '<th>field label / section</th><th>occurrence in context</th>'
                    '<th>true class</th></tr>')
            for r in rs:
                loc = " / ".join(x for x in (r["field_label"], r["section"]) if x)
                f.write(
                    f'<tr><td><code>{r["row_id"]}</code></td>'
                    f'<td>{esc(r["information_type"])}</td>'
                    f'<td>{esc(r["region"])}</td>'
                    f'<td class="ctx">{esc(loc)}</td>'
                    f'<td class="ctx">...{esc(r["context_before"])}'
                    f'<mark>{esc(r["value"])}</mark>'
                    f'{esc(r["context_after"])}...</td>'
                    f'<td class="ans">[ ]</td></tr>')
            f.write('</table></div>\n')


def main() -> None:
    if not LINKAGE_PATH.exists():
        raise SystemExit("Run `python -m stage1.subject_linkage` first.")
    if not TAGGER_SAMPLE_PATH.exists():
        raise SystemExit("Run `python -m stage1.sample_audit` first.")

    # Never clobber a human pass.
    if SHEET_PATH.exists():
        with open(SHEET_PATH, encoding="utf-8-sig", newline="") as f:
            filled = sum(1 for row in csv.DictReader(f)
                         if (row.get("true_class") or "").strip())
        if filled:
            raise SystemExit(
                f"{SHEET_PATH} already carries {filled} annotation(s). Refusing to "
                f"overwrite a human pass - move or rename it first.")

    rows, record = build_rows()
    write_sheet(rows)
    write_key(rows)
    write_html(rows, record)
    RECORD_PATH.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    fc = record["filtered_census"]
    print(f"Linkage audit sheet - vocab v{VOCAB_VERSION}, linkage v{LINKAGE_VERSION}\n")
    print(f"  Block A  every detection in the 25 audit documents : "
          f"{record['block_a']['rows']:>4} rows")
    print(f"  Block B  remaining filtered detections (census)    : "
          f"{record['block_b']['rows']:>4} rows")
    print(f"  {'TOTAL':<50}: {record['rows_total']:>4} rows")
    print(f"\n  documents touched               : {record['documents_touched']}")
    print(f"  filtered detections corpus-wide : {fc['filtered_detections_corpus_wide']}")
    print(f"  covered by the sheet            : {fc['covered_by_sheet']}"
          f"  {'(complete census)' if fc['covered_by_sheet'] == fc['filtered_detections_corpus_wide'] else '(INCOMPLETE)'}")
    print(f"\n  by classifier call (withheld from the sheet):")
    for k, v in Counter(r["_classification"] for r in rows).most_common():
        print(f"     {k:<16} {v:>4}")
    print(f"\n  randomness: {record['randomness']}")
    print(f"\nWrote:\n  {SHEET_PATH}   <-- fill in 'true_class'\n  {HTML_PATH}"
          f"\n  {KEY_PATH}\n  {RECORD_PATH}")
    print("\nThen: python -m stage1.score_linkage")


if __name__ == "__main__":
    main()
