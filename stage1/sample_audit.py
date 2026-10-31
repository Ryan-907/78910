"""
Paper III — Stage 1 Deliverable 4a: Tagger Accuracy Audit Harness

Draws a reproducible stratified sample of the corpus and emits a review packet a
human annotator fills in by hand. The scoring half lives in stage1/score_audit.py
and refuses to run until the packet is complete.

Why this exists
---------------
In Paper I the tagger scored a dataset; its error rate was a property of a
measurement. In Paper III the extracted inventory becomes an ENFORCEMENT INPUT —
the left-hand side of

    every information type in the document  ⊆  types the requester's role may receive

so a tagger error becomes a policy error. The two directions are not symmetric:

  FALSE POSITIVE (tagger reports a type that is not there)
      The future check denies a flow it should have permitted. Visible, annoying,
      and self-correcting: someone complains.

  MISS / FALSE NEGATIVE (a type is present and the tagger does not report it)
      The subset test passes over information it never saw. The gate releases the
      document, the recipient receives an information type they have no business
      holding, and the decision LOOKS CORRECT — no error is raised, no log line is
      unusual, nothing surfaces. This is the dangerous direction, and per-category
      miss rate is the number the paper should lead with.

Sampling procedure (deterministic, seed-fixed)
----------------------------------------------
1. Allocate a quota per sensitivity tier:
     a. every tier gets min(MIN_PER_TIER, tier size) — this censuses the small
        tiers, since `public` holds 1 document and `internal` 9;
     b. the remaining budget is split across tiers in proportion to their
        remaining documents by the largest-remainder method, ties broken by tier
        name so the result does not depend on dict ordering.
2. Within a tier, spread over document types: shuffle the tier's document types
   and the documents within each type using the seeded RNG, then round-robin one
   document per type until the quota is met. This maximizes document-type
   coverage before it takes a second document of any one type.
3. Sort the final selection by doc_id for a stable review order.

Every draw comes from `random.Random(seed)` alone; no global random state is
touched, so the sample is reproducible regardless of what else has run.

Annotation model
----------------
The packet contains one row per (document, vocabulary type) — 25 x 16 = 400 rows.
`tagger_detected` is prefilled; the annotator fills `present_in_document` with
y or n. That yields a full confusion matrix per category with no free-text
parsing:

    TP  detected=yes  present=y        FP  detected=yes  present=n
    FN  detected=no   present=y        TN  detected=no   present=n

Usage
-----
    python -m stage1.sample_audit                # 25 docs, seed 7926
    python -m stage1.sample_audit -n 35
    python -m stage1.sample_audit --seed 1234

Outputs (stage1/artifacts/audit/)
    audit_sample_v1.0.0.json     sampling record: seed, procedure, allocation
    audit_sheet_v1.0.0.csv       THE FILE TO FILL IN — 400 rows
    audit_review_v1.0.0.html     readable sheet with detections highlighted
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from stage1.build_inventory import (
    ARTIFACT_DIR, ARTIFACT_VERSION, JSON_PATH as INVENTORY_PATH, load_corpus, doc_id,
)
from stage1.vocabulary import INFORMATION_TYPES, VOCAB, VOCAB_VERSION

AUDIT_DIR    = ARTIFACT_DIR / "audit"
DEFAULT_N    = 25
# Inherited from PANOPTICON's sample_review.py so the two papers' manual-review
# samples are drawn under the same documented seed.
DEFAULT_SEED = 7926
MIN_PER_TIER = 3

TYPE_NAMES = [t.name for t in INFORMATION_TYPES]


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def allocate_quota(tier_sizes: dict[str, int], n: int,
                   min_per_tier: int = MIN_PER_TIER) -> dict[str, int]:
    """
    Quota per tier: a floor for every tier (censusing the small ones), then the
    remaining budget by largest remainder over each tier's leftover documents.
    """
    tiers = sorted(tier_sizes)
    quota = {t: min(min_per_tier, tier_sizes[t]) for t in tiers}

    budget = n - sum(quota.values())
    if budget <= 0:
        return quota

    leftover = {t: tier_sizes[t] - quota[t] for t in tiers}
    pool = sum(leftover.values())
    if pool == 0:
        return quota

    exact = {t: budget * leftover[t] / pool for t in tiers}
    for t in tiers:
        quota[t] += int(exact[t])

    remaining = n - sum(quota.values())
    # Largest fractional remainder first; ties broken by tier name for determinism.
    order = sorted(tiers, key=lambda t: (-(exact[t] - int(exact[t])), t))
    for t in order:
        if remaining <= 0:
            break
        if quota[t] < tier_sizes[t]:
            quota[t] += 1
            remaining -= 1
    return quota


def pick_in_tier(docs: list[dict], k: int, rng: random.Random) -> list[dict]:
    """Round-robin over shuffled document types, so type coverage comes first."""
    by_dtype: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        by_dtype[d["document_type"]].append(d)

    dtypes = sorted(by_dtype)
    rng.shuffle(dtypes)
    for dt in dtypes:
        by_dtype[dt].sort(key=lambda d: d["doc_id"])
        rng.shuffle(by_dtype[dt])

    picked: list[dict] = []
    while len(picked) < k:
        progressed = False
        for dt in dtypes:
            if len(picked) >= k:
                break
            if by_dtype[dt]:
                picked.append(by_dtype[dt].pop())
                progressed = True
        if not progressed:
            break
    return picked


def draw_sample(entries: list[dict], n: int, seed: int) -> tuple[list[dict], dict]:
    rng = random.Random(seed)

    by_tier: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_tier[e["sensitivity_tier"]].append(e)

    tier_sizes = {t: len(v) for t, v in by_tier.items()}
    quota = allocate_quota(tier_sizes, n)

    selected: list[dict] = []
    for tier in sorted(by_tier):
        selected += pick_in_tier(by_tier[tier], quota[tier], rng)

    selected.sort(key=lambda e: e["doc_id"])
    record = {
        "seed":          seed,
        "requested_n":   n,
        "actual_n":      len(selected),
        "min_per_tier":  MIN_PER_TIER,
        "tier_sizes":    dict(sorted(tier_sizes.items())),
        "tier_quota":    dict(sorted(quota.items())),
        "tier_realized": dict(sorted(Counter(e["sensitivity_tier"] for e in selected).items())),
        "document_types_covered": len({e["document_type"] for e in selected}),
        "document_type_counts": dict(sorted(
            Counter(e["document_type"] for e in selected).items())),
        "procedure": (
            "min(MIN_PER_TIER, tier size) floor per tier, remainder by largest-remainder "
            "over leftover documents (ties by tier name); within tier, round-robin over "
            "seed-shuffled document types; final order by doc_id. random.Random(seed) only."
        ),
    }
    return selected, record


# ---------------------------------------------------------------------------
# Review packet
# ---------------------------------------------------------------------------

def write_sheet(selected: list[dict], path: Path) -> int:
    """One row per (document, vocabulary type). Returns the row count."""
    rows = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "doc_id", "title", "document_type", "sensitivity_tier",
            "information_type", "tagger_detected",
            "tagger_evidence",        # what the tagger matched, for the detected rows
            "present_in_document",    # <-- ANNOTATOR FILLS THIS: y / n
            "notes",
        ])
        for e in selected:
            for t in TYPE_NAMES:
                dets = e["detections"].get(t, [])
                evidence = " | ".join(
                    f"{d['value']}" for d in dets[:6]
                )
                if len(dets) > 6:
                    evidence += f" | (+{len(dets) - 6} more)"
                w.writerow([
                    e["doc_id"], e["title"], e["document_type"], e["sensitivity_tier"],
                    t, "yes" if dets else "no", evidence, "", "",
                ])
                rows += 1
    return rows


HTML_HEAD = """<meta charset="utf-8">
<title>Paper III Stage 1 — tagger audit sheet</title><style>
:root{color-scheme:light dark}
body{font:15px/1.55 -apple-system,Segoe UI,sans-serif;max-width:64rem;margin:2rem auto;
     padding:0 1rem;color:#111;background:#fff}
h1{font-size:1.45rem;margin-bottom:.2rem}
.meta{color:#555;font-size:.85rem;margin-bottom:1.2rem}
.warn{border-left:4px solid #b34;background:#fff5f5;padding:.7rem 1rem;margin:1rem 0;
      font-size:.9rem}
.doc{border:1px solid #ddd;border-radius:7px;padding:1rem 1.2rem;margin-bottom:1.4rem}
.hdr{font-size:.82rem;color:#555;font-family:ui-monospace,Consolas,monospace;
     margin-bottom:.7rem}
.hdr b{color:#111;font-size:1rem}
pre.content{background:#fafafa;border:1px solid #eee;border-radius:5px;padding:.7rem;
     font:12px/1.45 ui-monospace,Consolas,monospace;white-space:pre-wrap;
     max-height:26rem;overflow:auto}
table{border-collapse:collapse;width:100%;font-size:.84rem;margin-top:.8rem}
th,td{border:1px solid #ddd;padding:.32rem .5rem;text-align:left;vertical-align:top}
th{background:#f4f4f4;font-weight:600}
td.yes{background:#eef7ee} td.no{background:#fbfbfb;color:#777}
td.ev{font-family:ui-monospace,Consolas,monospace;font-size:.78rem;color:#333}
td.box{width:3.2rem;text-align:center;color:#bbb}
mark{background:#ffe9a8;padding:0 .1em;border-radius:2px}
@media (prefers-color-scheme:dark){
  body{background:#141414;color:#e8e8e8}
  pre.content{background:#1c1c1c;border-color:#333}
  th{background:#222} th,td{border-color:#333}
  td.yes{background:#16301b} td.no{background:#1a1a1a;color:#888}
  .warn{background:#2a1618;border-color:#c55}
  mark{background:#6a5410;color:#fff}
}
</style>
"""


def highlight(text: str, detections: dict[str, list[dict]]) -> str:
    """Wrap every detected span in <mark>, merging overlaps (first label wins)."""
    spans = sorted(
        ((d["start"], d["end"], t)
         for t, dets in detections.items() for d in dets
         if d["end"] > d["start"]),
        key=lambda s: (s[0], -s[1]),
    )
    merged: list[list] = []
    for start, end, label in spans:
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
            continue
        merged.append([start, end, label])

    out, cursor = [], 0
    for start, end, label in merged:
        out.append(html.escape(text[cursor:start]))
        out.append(f'<mark title="{html.escape(label)}">'
                   f'{html.escape(text[start:end])}</mark>')
        cursor = end
    out.append(html.escape(text[cursor:]))
    return "".join(out)


def write_html(selected: list[dict], contents: dict[str, str],
               record: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(HTML_HEAD)
        f.write("<h1>Paper III Stage 1 — tagger audit sheet</h1>\n")
        f.write(f'<div class="meta">vocabulary v{VOCAB_VERSION} &nbsp;·&nbsp; '
                f'{record["actual_n"]} documents &nbsp;·&nbsp; seed {record["seed"]} '
                f'&nbsp;·&nbsp; {record["document_types_covered"]}/21 document types '
                f'&nbsp;·&nbsp; tiers '
                f'{", ".join(f"{k} {v}" for k, v in record["tier_realized"].items())}'
                f'</div>\n')
        f.write(
            '<div class="warn"><b>Misses are the dangerous direction.</b> A false '
            'positive (tagger reports a type that is absent) causes the future gate '
            'check to deny a flow it should permit — visible and self-correcting. A '
            'miss (type present, tagger silent) lets the subset test pass over '
            'information it never saw: the document is released, the recipient holds '
            'an information type they should not, and the decision looks correct. '
            'Please read for what is <i>present and unmarked</i>, not only for '
            'whether the highlighted spans are right.</div>\n'
        )
        f.write(
            '<div class="warn">Record your verdicts in '
            f'<code>audit_sheet_v{ARTIFACT_VERSION}.csv</code>, one row per '
            '(document, information type): put <code>y</code> or <code>n</code> in '
            '<code>present_in_document</code>. This page is the evidence view; the '
            'CSV is the answer sheet. Then run '
            '<code>python -m stage1.score_audit</code>.</div>\n'
        )

        for e in selected:
            f.write('<div class="doc">')
            f.write(f'<div class="hdr"><b>{html.escape(e["doc_id"])}</b> &nbsp; '
                    f'{html.escape(e["title"])}<br>'
                    f'{html.escape(e["document_type"])} &nbsp;·&nbsp; '
                    f'{html.escape(e["sensitivity_tier"])} &nbsp;·&nbsp; '
                    f'subject {html.escape(str(e.get("subject_name")))}</div>')
            f.write(f'<pre class="content">'
                    f'{highlight(contents[e["doc_id"]], e["detections"])}</pre>')

            f.write('<table><tr><th>information type</th><th>tagger</th>'
                    '<th>evidence</th><th>present?</th></tr>')
            for t in TYPE_NAMES:
                dets = e["detections"].get(t, [])
                cls = "yes" if dets else "no"
                ev = html.escape(" | ".join(d["value"][:44] for d in dets[:5]))
                if len(dets) > 5:
                    ev += f" <i>(+{len(dets) - 5})</i>"
                f.write(f'<tr><td>{t}</td><td class="{cls}">'
                        f'{"detected" if dets else "—"}</td>'
                        f'<td class="ev">{ev}</td><td class="box">☐</td></tr>')
            f.write('</table></div>\n')


# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", "--num", type=int, default=DEFAULT_N,
                   help=f"sample size (default {DEFAULT_N})")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED,
                   help=f"RNG seed (default {DEFAULT_SEED})")
    args = p.parse_args()

    if not INVENTORY_PATH.exists():
        raise SystemExit("Run `python -m stage1.build_inventory` first.")
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    entries = inventory["documents"]

    records, corpus_hash = load_corpus()
    if corpus_hash != inventory["source"]["sha256"]:
        raise SystemExit("Corpus changed since the inventory was built — rebuild it.")
    contents = {doc_id(i): (r.get("content") or "") for i, r in enumerate(records)}

    selected, record = draw_sample(entries, args.num, args.seed)
    record["vocab_version"] = VOCAB_VERSION
    record["corpus_sha256"] = corpus_hash
    record["doc_ids"] = [e["doc_id"] for e in selected]

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path  = AUDIT_DIR / f"audit_sheet_v{ARTIFACT_VERSION}.csv"
    html_path   = AUDIT_DIR / f"audit_review_v{ARTIFACT_VERSION}.html"
    record_path = AUDIT_DIR / f"audit_sample_v{ARTIFACT_VERSION}.json"

    # Never clobber a human pass. Parsed as CSV rather than string-matched, so a
    # comma inside a quoted evidence field cannot be mistaken for a verdict.
    if sheet_path.exists():
        with open(sheet_path, encoding="utf-8-sig", newline="") as f:
            filled = sum(
                1 for row in csv.DictReader(f)
                if (row.get("present_in_document") or "").strip()
            )
        if filled:
            raise SystemExit(
                f"{sheet_path} already carries {filled} annotation(s). Refusing to "
                f"overwrite a human pass — move or rename it first."
            )

    n_rows = write_sheet(selected, sheet_path)
    write_html(selected, contents, record, html_path)
    record["sheet_rows"] = n_rows
    record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    print(f"Audit sample — seed {record['seed']}, "
          f"{record['actual_n']} documents, {n_rows} annotation rows\n")
    print(f"{'tier':<22} {'corpus':>7} {'quota':>6} {'drawn':>6}")
    print("-" * 44)
    for tier in sorted(record["tier_sizes"]):
        print(f"  {tier:<20} {record['tier_sizes'][tier]:>7} "
              f"{record['tier_quota'][tier]:>6} "
              f"{record['tier_realized'].get(tier, 0):>6}")
    print("-" * 44)
    print(f"  document types covered: {record['document_types_covered']} / 21")
    detected = sum(1 for e in selected for t in TYPE_NAMES if e["detections"].get(t))
    print(f"  rows the tagger marked detected: {detected} / {n_rows}")

    print(f"\nWrote:\n  {record_path}\n  {sheet_path}   <-- fill in "
          f"'present_in_document' (y/n)\n  {html_path}")
    print("\nThen: python -m stage1.score_audit")


if __name__ == "__main__":
    main()
