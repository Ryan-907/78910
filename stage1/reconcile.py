"""
Paper III — Stage 1 Deliverable 3: Reconcile Extracted vs. Authored

The Riverside corpus was built specification-first: each document's CI label was
authored in pipeline/doc_specs.py, and content was then generated to satisfy it.
`label.pii_attributes` is therefore a SPECIFICATION of what should be present, not
an INVENTORY of what is. This module measures the distance between the two.

Three sources are compared, not two:

    A  authored    label.pii_attributes          the spec, hand-written in doc_specs.py
    B  extracted   stage1/tagger.py over content the Stage 1 tagger, content only
    C  generation  attributes[].information_type returned by the generating model,
                                                 already value-validated against
                                                 content by pipeline/validate_dataset.py

C is included because it is an independent third reading that already exists in
the corpus and disagrees with A in the same direction the brief predicts. It is
not ground truth — it was produced by the same model that wrote the content — but
where B and C agree against A, the finding is not an artifact of the tagger.

This is a REPORT, not a repair. Nothing is written back to data/dataset.json;
neither side is corrected.

Usage
-----
    python -m stage1.reconcile

Outputs (stage1/artifacts/)
    reconciliation_v1.0.0.json
    reconciliation_v1.0.0.csv          one row per document
    reconciliation_by_type_v1.0.0.csv  one row per information type
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from stage1.build_inventory import (
    ARTIFACT_DIR, ARTIFACT_VERSION, JSON_PATH as INVENTORY_PATH,
    load_corpus, doc_id,
)
from stage1.vocabulary import (
    INFORMATION_TYPES, VOCAB_VERSION, normalize_type,
)

OUT_JSON       = ARTIFACT_DIR / f"reconciliation_v{ARTIFACT_VERSION}.json"
OUT_CSV        = ARTIFACT_DIR / f"reconciliation_v{ARTIFACT_VERSION}.csv"
OUT_BY_TYPE    = ARTIFACT_DIR / f"reconciliation_by_type_v{ARTIFACT_VERSION}.csv"

TYPE_NAMES = [t.name for t in INFORMATION_TYPES]


def normalize_set(raw: list[str] | None) -> tuple[set[str], list[str]]:
    """Map raw type strings onto the vocabulary. Returns (in_vocab, dropped)."""
    keep: set[str] = set()
    dropped: list[str] = []
    for r in raw or []:
        n = normalize_type(r)
        if n:
            keep.add(n)
        else:
            dropped.append(r)
    return keep, dropped


def load_inventory() -> dict[str, dict]:
    if not INVENTORY_PATH.exists():
        raise FileNotFoundError(
            f"{INVENTORY_PATH} not found — run `python -m stage1.build_inventory` first"
        )
    data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return {d["doc_id"]: d for d in data["documents"]}, data["source"]["sha256"]


def reconcile() -> tuple[list[dict], dict]:
    records, corpus_hash = load_corpus()
    inventory, inv_corpus_hash = load_inventory()

    if inv_corpus_hash != corpus_hash:
        raise RuntimeError(
            "Corpus has changed since the inventory was built "
            f"(inventory {inv_corpus_hash[:16]}… vs corpus {corpus_hash[:16]}…). "
            "Re-run stage1.build_inventory."
        )

    rows: list[dict] = []
    dropped_counter: Counter = Counter()

    for i, r in enumerate(records):
        did = doc_id(i)
        inv = inventory[did]

        authored, dropped_a = normalize_set(r.get("pii_attributes"))
        generation, dropped_c = normalize_set(
            [a.get("information_type") for a in r.get("attributes", [])]
        )
        extracted = set(inv["extracted_types"])
        dropped_counter.update(dropped_a + dropped_c)

        union = authored | extracted
        rows.append({
            "doc_id":            did,
            "title":             r["title"],
            "document_type":     r["document_type"],
            "sensitivity_tier":  r["sensitivity_tier"],
            "subject_type":      r["subject_type"],
            "extra_sensitive":   bool(r.get("extra_sensitive")),
            "authored":          sorted(authored),
            "extracted":         sorted(extracted),
            "generation":        sorted(generation),
            "agree_exactly":     authored == extracted,
            # Direction 1: the spec claims it, the tagger cannot find it.
            "authored_not_found": sorted(authored - extracted),
            # Direction 2: the tagger finds it, no label ever claimed it.
            # This is the Paper III surface: information types riding along in a
            # document the gate releases on the strength of a label that is silent
            # about them.
            "found_not_authored": sorted(extracted - authored),
            "jaccard":           round(len(authored & extracted) / len(union), 4) if union else 1.0,
            # Corroboration: does the generating model's own extraction agree with
            # the tagger that this type is present, against the authored spec?
            "found_not_authored_corroborated": sorted(
                (extracted - authored) & generation
            ),
            "generation_not_authored": sorted(generation - authored),
        })

    meta = {"corpus_sha256": corpus_hash, "dropped_raw_types": dict(dropped_counter)}
    return rows, meta


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def by_type(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in TYPE_NAMES:
        authored   = sum(1 for r in rows if t in r["authored"])
        extracted  = sum(1 for r in rows if t in r["extracted"])
        generation = sum(1 for r in rows if t in r["generation"])
        both       = sum(1 for r in rows if t in r["authored"] and t in r["extracted"])
        a_not_e    = sum(1 for r in rows if t in r["authored_not_found"])
        e_not_a    = sum(1 for r in rows if t in r["found_not_authored"])
        corrob     = sum(1 for r in rows if t in r["found_not_authored_corroborated"])
        out[t] = {
            "authored_docs":   authored,
            "extracted_docs":  extracted,
            "generation_docs": generation,
            "both":            both,
            "authored_not_found": a_not_e,
            "found_not_authored": e_not_a,
            "found_not_authored_corroborated": corrob,
            # Of the documents the spec says carry this type, the share the tagger
            # confirms. Not recall against truth — recall against the spec.
            "spec_confirmation_rate": round(both / authored, 4) if authored else None,
        }
    return out


def by_group(rows: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)

    out = {}
    for g, rs in sorted(groups.items()):
        n = len(rs)
        out[g] = {
            "documents":           n,
            "agree_exactly":       sum(1 for r in rs if r["agree_exactly"]),
            "docs_authored_not_found": sum(1 for r in rs if r["authored_not_found"]),
            "docs_found_not_authored": sum(1 for r in rs if r["found_not_authored"]),
            "authored_not_found_pairs": sum(len(r["authored_not_found"]) for r in rs),
            "found_not_authored_pairs": sum(len(r["found_not_authored"]) for r in rs),
            "authored_pairs":      sum(len(r["authored"]) for r in rs),
            "extracted_pairs":     sum(len(r["extracted"]) for r in rs),
            "mean_jaccard":        round(sum(r["jaccard"] for r in rs) / n, 4),
        }
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(rows: list[dict], meta: dict) -> dict:
    types    = by_type(rows)
    by_tier  = by_group(rows, "sensitivity_tier")
    by_dtype = by_group(rows, "document_type")

    n = len(rows)
    summary = {
        "documents":                 n,
        "agree_exactly":             sum(1 for r in rows if r["agree_exactly"]),
        "docs_with_authored_not_found": sum(1 for r in rows if r["authored_not_found"]),
        "docs_with_found_not_authored": sum(1 for r in rows if r["found_not_authored"]),
        "authored_pairs":            sum(len(r["authored"]) for r in rows),
        "extracted_pairs":           sum(len(r["extracted"]) for r in rows),
        "generation_pairs":          sum(len(r["generation"]) for r in rows),
        "authored_not_found_pairs":  sum(len(r["authored_not_found"]) for r in rows),
        "found_not_authored_pairs":  sum(len(r["found_not_authored"]) for r in rows),
        "found_not_authored_corroborated_pairs":
            sum(len(r["found_not_authored_corroborated"]) for r in rows),
        "mean_jaccard":              round(sum(r["jaccard"] for r in rows) / n, 4),
    }

    artifact = {
        "artifact":         "stage1_reconciliation",
        "artifact_version": ARTIFACT_VERSION,
        "vocab_version":    VOCAB_VERSION,
        "corpus_sha256":    meta["corpus_sha256"],
        "sources": {
            "A_authored":   "label.pii_attributes (pipeline/doc_specs.py, spec-first)",
            "B_extracted":  "stage1/tagger.py over document content",
            "C_generation": "attributes[].information_type (generating model)",
        },
        "note": (
            "A report, not a repair. Neither side is corrected and data/dataset.json "
            "is untouched. 'authored_not_found' does not mean the spec is wrong — it "
            "may equally be a tagger miss; see the Stage 4 audit."
        ),
        "raw_types_outside_vocabulary": meta["dropped_raw_types"],
        "summary":            summary,
        "by_information_type": types,
        "by_sensitivity_tier": by_tier,
        "by_document_type":    by_dtype,
        "documents":           rows,
    }
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "title", "document_type", "sensitivity_tier",
                    "agree_exactly", "jaccard", "n_authored", "n_extracted",
                    "authored", "extracted",
                    "authored_not_found", "found_not_authored",
                    "found_not_authored_corroborated"])
        for r in rows:
            w.writerow([
                r["doc_id"], r["title"], r["document_type"], r["sensitivity_tier"],
                "yes" if r["agree_exactly"] else "no", r["jaccard"],
                len(r["authored"]), len(r["extracted"]),
                ";".join(r["authored"]), ";".join(r["extracted"]),
                ";".join(r["authored_not_found"]), ";".join(r["found_not_authored"]),
                ";".join(r["found_not_authored_corroborated"]),
            ])

    with open(OUT_BY_TYPE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = ["authored_docs", "extracted_docs", "generation_docs", "both",
                "authored_not_found", "found_not_authored",
                "found_not_authored_corroborated", "spec_confirmation_rate"]
        w.writerow(["information_type"] + cols)
        for t in TYPE_NAMES:
            w.writerow([t] + [types[t][c] for c in cols])

    return artifact


def main() -> None:
    rows, meta = reconcile()
    art = write_outputs(rows, meta)
    s, types = art["summary"], art["by_information_type"]
    n = s["documents"]

    print(f"Reconciliation — vocab v{VOCAB_VERSION}, {n} documents\n")
    print(f"  agree exactly (authored == extracted) : {s['agree_exactly']:>4} / {n}"
          f"  ({s['agree_exactly'] / n:.1%})")
    print(f"  docs with types authored but not found: {s['docs_with_authored_not_found']:>4} / {n}")
    print(f"  docs with types found but not authored: {s['docs_with_found_not_authored']:>4} / {n}")
    print(f"  mean Jaccard(authored, extracted)     : {s['mean_jaccard']:.3f}")
    print()
    print(f"  (doc, type) pairs — authored          : {s['authored_pairs']:>4}")
    print(f"  (doc, type) pairs — extracted         : {s['extracted_pairs']:>4}")
    print(f"  (doc, type) pairs — generation model  : {s['generation_pairs']:>4}")
    print(f"  authored but not found                : {s['authored_not_found_pairs']:>4}")
    print(f"  found but not authored                : {s['found_not_authored_pairs']:>4}")
    print(f"    of which corroborated by generation : "
          f"{s['found_not_authored_corroborated_pairs']:>4}")

    print(f"\n{'information type':<22} {'auth':>5} {'extr':>5} {'gen':>5} "
          f"{'A\\B':>5} {'B\\A':>5} {'corrob':>7}")
    print("-" * 60)
    for t in TYPE_NAMES:
        d = types[t]
        print(f"  {t:<20} {d['authored_docs']:>5} {d['extracted_docs']:>5} "
              f"{d['generation_docs']:>5} {d['authored_not_found']:>5} "
              f"{d['found_not_authored']:>5} {d['found_not_authored_corroborated']:>7}")

    print(f"\n{'sensitivity tier':<22} {'docs':>5} {'exact':>6} {'A\\B':>6} {'B\\A':>6} {'jacc':>6}")
    print("-" * 55)
    for tier, d in art["by_sensitivity_tier"].items():
        print(f"  {tier:<20} {d['documents']:>5} {d['agree_exactly']:>6} "
              f"{d['authored_not_found_pairs']:>6} {d['found_not_authored_pairs']:>6} "
              f"{d['mean_jaccard']:>6.3f}")

    print(f"\n{'document type':<28} {'docs':>5} {'exact':>6} {'A\\B':>6} {'B\\A':>6}")
    print("-" * 55)
    for dt, d in sorted(art["by_document_type"].items(),
                        key=lambda kv: -kv[1]["found_not_authored_pairs"]):
        print(f"  {dt:<26} {d['documents']:>5} {d['agree_exactly']:>6} "
              f"{d['authored_not_found_pairs']:>6} {d['found_not_authored_pairs']:>6}")

    if art["raw_types_outside_vocabulary"]:
        print(f"\nRaw type strings dropped as outside the vocabulary: "
              f"{art['raw_types_outside_vocabulary']}")

    print(f"\nWrote:\n  {OUT_JSON}\n  {OUT_CSV}\n  {OUT_BY_TYPE}")


if __name__ == "__main__":
    main()
