"""
Paper III — Stage 1 Deliverable 2: Attribute Inventory

Runs stage1/tagger.py over all 105 corpus documents and emits, per document, the
set of controlled-vocabulary information types present in its content.

This is kept strictly separate from the authored labels. The corpus is opened
read-only; nothing here writes to data/dataset.json, and `label.pii_attributes`
is never consulted — the tagger sees content only, so that the Stage 3
reconciliation compares two independent sources rather than one source with
itself.

Reproducibility
---------------
Output is deterministic and contains no wall-clock timestamp, so re-running over
an unchanged corpus reproduces the artifacts byte-for-byte. The corpus is
fingerprinted by SHA-256; if data/dataset.json changes, the fingerprint in the
artifact no longer matches and downstream stages will say so.

Document identity
-----------------
The corpus has no id field — records are keyed by `title` (unique across all 105).
This module mints `doc_000`..`doc_104` from list position and also records a
content SHA-256, so a reordering or an edit is detectable rather than silent.

Usage
-----
    python -m stage1.build_inventory

Outputs (stage1/artifacts/)
    inventory_v1.0.0.json             full inventory with per-detection evidence
    inventory_v1.0.0.csv              one row per document
    inventory_detections_v1.0.0.csv   one row per detection
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from stage1 import tagger
from stage1.vocabulary import (
    INFORMATION_TYPES, VOCAB_VERSION, vocabulary_manifest,
)

DATASET_PATH  = Path("data/dataset.json")
ARTIFACT_DIR  = Path("stage1/artifacts")
ARTIFACT_VERSION = "1.0.0"

JSON_PATH        = ARTIFACT_DIR / f"inventory_v{ARTIFACT_VERSION}.json"
CSV_PATH         = ARTIFACT_DIR / f"inventory_v{ARTIFACT_VERSION}.csv"
DETECTIONS_PATH  = ARTIFACT_DIR / f"inventory_detections_v{ARTIFACT_VERSION}.csv"


def sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def doc_id(index: int) -> str:
    return f"doc_{index:03d}"


def load_corpus() -> tuple[list[dict], str]:
    """Return (records, corpus_sha256). Read-only."""
    raw = DATASET_PATH.read_bytes()
    return json.loads(raw.decode("utf-8")), sha256(raw)


def build(records: list[dict]) -> list[dict]:
    """Tag every record. Returns one inventory entry per document."""
    entries = []
    for i, r in enumerate(records):
        content = r.get("content") or ""
        found = tagger.tag(content)
        entries.append({
            "doc_id":           doc_id(i),
            "title":            r["title"],
            "document_type":    r["document_type"],
            "sensitivity_tier": r["sensitivity_tier"],
            "subject_type":     r["subject_type"],
            "subject_name":     r.get("subject_name"),
            "content_sha256":   sha256(content),
            "content_chars":    len(content),
            "extracted_types":  sorted(found),
            "detections": {
                t: [d.as_dict() for d in dets] for t, dets in sorted(found.items())
            },
        })
    return entries


def write_json(entries: list[dict], corpus_hash: str) -> None:
    artifact = {
        "artifact":         "stage1_attribute_inventory",
        "artifact_version": ARTIFACT_VERSION,
        "vocab_version":    VOCAB_VERSION,
        "tagger_version":   tagger.TAGGER_VERSION,
        "source": {
            "path":          str(DATASET_PATH).replace("\\", "/"),
            "sha256":        corpus_hash,
            "n_documents":   len(entries),
        },
        "note": (
            "Extracted from document content only. Independent of label.pii_attributes; "
            "see stage1/reconcile.py for the comparison. Deterministic: no timestamp, "
            "no sampling, no model calls."
        ),
        "vocabulary": vocabulary_manifest(),
        "documents":  entries,
    }
    JSON_PATH.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_csv(entries: list[dict]) -> None:
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "title", "document_type", "sensitivity_tier",
                    "subject_type", "n_types", "extracted_types"])
        for e in entries:
            w.writerow([e["doc_id"], e["title"], e["document_type"],
                        e["sensitivity_tier"], e["subject_type"],
                        len(e["extracted_types"]), ";".join(e["extracted_types"])])

    with open(DETECTIONS_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "information_type", "rule", "value", "start", "end"])
        for e in entries:
            for t, dets in e["detections"].items():
                for d in dets:
                    w.writerow([e["doc_id"], t, d["rule"], d["value"],
                                d["start"], d["end"]])


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    records, corpus_hash = load_corpus()
    entries = build(records)

    write_json(entries, corpus_hash)
    write_csv(entries)

    # ---- summary ----
    per_type = Counter()
    per_rule = Counter()
    for e in entries:
        per_type.update(e["extracted_types"])
        for dets in e["detections"].values():
            per_rule.update(d["rule"] for d in dets)

    n = len(entries)
    total_pairs = sum(len(e["extracted_types"]) for e in entries)
    print(f"Attribute inventory — vocab v{VOCAB_VERSION}, tagger v{tagger.TAGGER_VERSION}")
    print(f"corpus {DATASET_PATH} sha256 {corpus_hash[:16]}…  {n} documents\n")

    print(f"{'information type':<22} {'docs':>5} {'%':>6}")
    print("-" * 36)
    for t in INFORMATION_TYPES:
        c = per_type.get(t.name, 0)
        print(f"  {t.name:<20} {c:>5} {c / n:>6.1%}")
    print("-" * 36)
    print(f"  {'(doc, type) pairs':<20} {total_pairs:>5}")
    print(f"  {'mean types/doc':<20} {total_pairs / n:>5.2f}")
    zero = [e["doc_id"] for e in entries if not e["extracted_types"]]
    print(f"  {'docs with no types':<20} {len(zero):>5}"
          + (f"  {zero}" if zero else ""))

    silent = [t.name for t in INFORMATION_TYPES if not per_type.get(t.name)]
    if silent:
        print(f"\nVocabulary entries never detected: {silent}")
    dead = [r for r in tagger.RULE_IDS if r not in per_rule]
    if dead:
        print(f"Rules that never fired: {dead}")

    print(f"\nWrote:\n  {JSON_PATH}\n  {CSV_PATH}\n  {DETECTIONS_PATH}")


if __name__ == "__main__":
    main()
