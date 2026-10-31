"""
Paper III — Stage 1c: Score the Subject-Linkage Audit

Reads the completed linkage sheet and scores the Stage 1b classifier against the
human's judgements. Contains NO ground truth of its own, refuses to run on an
incomplete sheet, and will not infer, impute, or model a missing verdict. No
language model is involved: substituting one for the annotator would put a model
in the position of authoring an enforcement input, which is the thing this thesis
argues against.

What is scored, and why in this order
-------------------------------------
The two error directions are not symmetric.

  PRECISION ON THE FILTERED CLASSES  (`third_party`, `organizational`)
      THE HEADLINE. A detection the classifier filters out leaves the inventory,
      so the future gate check can never govern that information type — not
      incorrectly, but at all. The document is released, the recipient holds a
      type they should not, the decision looks correct, and nothing records it.
      Every such error is listed individually, by document and by the tagger rule
      that produced the detection, because a rate alone hides which rule is
      leaking.

  RECALL ON `subject`
      Secondary. Its failure mode is a false `subject` call, which leaves an
      extra type in the inventory and causes an OVER-BLOCK — visible, traceable,
      and self-correcting because someone complains.

Because the sheet censuses all 226 filtered detections corpus-wide (Block A +
Block B), precision on `third_party` and on `organizational` is EXACT: no
sampling error and no interval. Recall on `subject` is estimated from Block A
only — the 25 audit documents — so it carries a Wilson 95% interval.

Usage
-----
    python -m stage1.score_linkage
    python -m stage1.score_linkage --sheet path/to/other_sheet.csv

Outputs (stage1/artifacts/audit/)
    linkage_scores_v1.1.0.json
    linkage_errors_v1.1.0.csv          every misclassification, one per row
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from stage1.sample_audit import AUDIT_DIR
from stage1.sample_linkage_audit import KEY_PATH, SHEET_PATH
from stage1.subject_linkage import (
    LINKAGE_VERSION, SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS,
)
from stage1.vocabulary import INFORMATION_TYPES, VOCAB_VERSION

OUT_JSON   = AUDIT_DIR / f"linkage_scores_v{LINKAGE_VERSION}.json"
OUT_ERRORS = AUDIT_DIR / f"linkage_errors_v{LINKAGE_VERSION}.csv"

CLASSES = (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS)
FILTERED_CLASSES = (THIRD_PARTY, ORGANIZATIONAL)
TYPE_NAMES = [t.name for t in INFORMATION_TYPES]

# Accepted spellings for each class in the true_class column.
ALIASES = {
    SUBJECT:        {"subject", "s", "subj"},
    THIRD_PARTY:    {"third_party", "third party", "thirdparty", "t", "3", "3rd"},
    ORGANIZATIONAL: {"organizational", "organisational", "org", "o"},
    AMBIGUOUS:      {"ambiguous", "amb", "a", "?"},
}
LOOKUP = {alias: cls for cls, aliases in ALIASES.items() for alias in aliases}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def load_sheet(path: Path) -> list[dict]:
    """
    Read the annotation sheet as CSV or XLSX.

    Excel is the practical tool for a 487-row four-way judgement, so an .xlsx
    saved from it is accepted directly rather than requiring a re-export. The
    reader is standard-library only (stage1/xlsx_reader.py); no spreadsheet
    dependency is added.
    """
    if not path.exists():
        # Accept a bare stem or the sibling format if only one of the pair exists.
        for alt in (path.with_suffix(".xlsx"), path.with_suffix(".csv")):
            if alt.exists():
                path = alt
                break
        else:
            raise SystemExit(
                f"{path} not found. Run `python -m stage1.sample_linkage_audit` first.")

    if path.suffix.lower() == ".xlsx":
        from stage1.xlsx_reader import read_dicts
        return read_dicts(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    annotated, unfilled, bad = [], [], []
    for i, r in enumerate(rows, start=2):
        raw = (r.get("true_class") or "").strip().casefold()
        if not raw:
            unfilled.append(r)
            continue
        cls = LOOKUP.get(raw)
        if cls is None:
            bad.append((i, r.get("row_id"), raw))
            continue
        r["_true"] = cls
        annotated.append(r)
    if bad:
        lines = "\n".join(f"    line {ln}: {rid} -> {v!r}" for ln, rid, v in bad[:15])
        raise SystemExit(
            f"{len(bad)} row(s) carry an unrecognized true_class. Use one of "
            f"{', '.join(CLASSES)}.\n{lines}")
    return annotated, unfilled


def metrics(tp: int, fp: int, fn: int, exact: bool) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall    = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    out = {
        "tp": tp, "fp": fp, "fn": fn,
        "predicted": tp + fp, "actual": tp + fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall":    round(recall, 4)    if recall    is not None else None,
        "f1":        round(f1, 4)        if f1        is not None else None,
    }
    # A census needs no interval; an estimate does.
    out["precision_ci95"] = None if exact else wilson(tp, tp + fp)
    out["recall_ci95"] = wilson(tp, tp + fn)
    out["precision_is_exact"] = exact
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", type=Path, default=SHEET_PATH)
    p.add_argument("--annotation-key", type=Path, default=KEY_PATH,
                   help="key matching the sheet's row_ids (the version the human annotated)")
    p.add_argument("--classification-key", type=Path, default=None,
                   help="key holding the classifier calls to score. Defaults to the "
                        "annotation key. Pass a different version to re-score the SAME "
                        "human labels against a revised classifier: rows are matched on "
                        "detection identity (doc_id, information_type, start, value), "
                        "not on row_id, because row_ids are positional and a revision "
                        "changes which detections are filtered and therefore sampled.")
    p.add_argument("--label", type=str, default=None,
                   help="suffix for the output filenames")
    p.add_argument("--allow-partial", action="store_true",
                   help="score the annotated subset instead of refusing")
    args = p.parse_args()

    suffix = f"_{args.label}" if args.label else ""
    if args.sheet.resolve() == SHEET_PATH.resolve() and not suffix:
        out_json, out_errors = OUT_JSON, OUT_ERRORS
    else:
        stem = args.sheet.with_suffix("")
        out_json   = stem.with_name(stem.name + suffix + "_scores.json")
        out_errors = stem.with_name(stem.name + suffix + "_errors.csv")

    rows = load_sheet(args.sheet)
    annotated, unfilled = parse(rows)

    if unfilled and not args.allow_partial:
        by_doc = Counter(r["doc_id"] for r in unfilled)
        by_block = Counter(r["block"] for r in unfilled)
        print(f"Linkage sheet is incomplete: {len(unfilled)} of {len(rows)} rows have "
              f"no verdict in 'true_class'.\n")
        print(f"Outstanding by block: "
              + ", ".join(f"{b} {c}" for b, c in sorted(by_block.items())))
        print("\nOutstanding by document:")
        for d, c in sorted(by_doc.items()):
            print(f"    {d}  {c}")
        print(f"\nUse one of: {', '.join(CLASSES)}")
        print("\nNo scores computed. This tool will not infer a missing verdict, and an "
              "LLM must not be substituted for the annotator -- that would score one "
              "classifier against another and report it as accuracy.")
        print("\nTo score a partial pass anyway: "
              "python -m stage1.score_linkage --allow-partial")
        raise SystemExit(1)

    ann_key = json.loads(args.annotation_key.read_text(encoding="utf-8"))["rows"]
    cls_path = args.classification_key or args.annotation_key
    _cls_doc = json.loads(cls_path.read_text(encoding="utf-8"))
    # Accept either an audit key (keyed by row_id) or a full linkage artifact
    # (every detection). The linkage artifact is the right source when re-scoring a
    # revision, because a revision moves detections out of the filtered classes and
    # they then no longer appear in that version's audit sheet at all.
    if "rows" in _cls_doc:
        cls_key = _cls_doc["rows"]
    else:
        cls_key = {f"d{i}": d for i, d in enumerate(_cls_doc["detections"])}

    def identity(e: dict) -> tuple:
        return (e["doc_id"], e["information_type"], str(e["start"]), e["value"])

    if cls_path.resolve() == args.annotation_key.resolve():
        key = ann_key
    else:
        # Re-scoring the same human labels against a revised classifier. Join on
        # detection identity: the human judged a detection, not a row number, and
        # the label is ground truth independent of whatever the classifier said.
        by_identity = {identity(v): v for v in cls_key.values()}
        key, unmatched = {}, []
        for row_id, v in ann_key.items():
            hit = by_identity.get(identity(v))
            if hit is None:
                unmatched.append(row_id)
            else:
                key[row_id] = hit
        if unmatched:
            print(f"note: {len(unmatched)} annotated detection(s) have no counterpart "
                  f"in {cls_path.name} and are excluded from scoring.")

    # ---- confusion matrix -------------------------------------------------
    confusion: dict[str, Counter] = defaultdict(Counter)   # predicted -> true
    errors: list[dict] = []
    for r in annotated:
        k = key.get(r["row_id"])
        if k is None:
            continue
        pred, true = k["classification"], r["_true"]
        confusion[pred][true] += 1
        if pred != true:
            errors.append({
                "row_id": r["row_id"], "block": r["block"], "doc_id": r["doc_id"],
                "document_type": r["document_type"],
                "sensitivity_tier": r["sensitivity_tier"],
                "subject_type": r["subject_type"],
                # Display fields come from the key, not the sheet: a spreadsheet
                # round-trip rewrites date-shaped values into serial numbers.
                "information_type": k.get("information_type", r["information_type"]),
                "value": k.get("value", r["value"]), "region": r["region"],
                "field_label": r["field_label"], "section": r["section"],
                "classifier_said": pred, "human_said": true,
                "linkage_signal": k["signal"], "tagger_rule": k["rule"],
                # The silent-release case: filtered out, but actually the subject's.
                "silent_release": pred in FILTERED_CLASSES and true == SUBJECT,
            })

    # ---- per-class metrics -------------------------------------------------
    per_class = {}
    for cls in CLASSES:
        tp = confusion[cls][cls]
        fp = sum(confusion[cls][t] for t in CLASSES if t != cls)
        fn = sum(confusion[pred][cls] for pred in CLASSES if pred != cls)
        # Filtered-class precision is exact ONLY when the census is complete. On a
        # partial pass the sheet no longer covers every filtered detection, so the
        # figure is an estimate and must carry an interval like any other.
        per_class[cls] = metrics(tp, fp, fn,
                                 exact=(cls in FILTERED_CLASSES and not unfilled))

    silent = [e for e in errors if e["silent_release"]]

    # ---- breakdowns --------------------------------------------------------
    by_type = defaultdict(lambda: {"errors": 0, "silent_release": 0, "n": 0})
    by_region = defaultdict(lambda: {"errors": 0, "silent_release": 0, "n": 0})
    by_signal = defaultdict(lambda: {"errors": 0, "silent_release": 0, "n": 0})
    for r in annotated:
        k = key.get(r["row_id"])
        if k is None:
            continue
        for bucket, name in ((by_type, r["information_type"]),
                             (by_region, r["region"]),
                             (by_signal, k["signal"])):
            bucket[name]["n"] += 1
    for e in errors:
        for bucket, name in ((by_type, e["information_type"]),
                             (by_region, e["region"]),
                             (by_signal, e["linkage_signal"])):
            bucket[name]["errors"] += 1
            if e["silent_release"]:
                bucket[name]["silent_release"] += 1

    def rate(d: dict) -> dict:
        return {**d, "error_rate": round(d["errors"] / d["n"], 4) if d["n"] else None}

    scores = {
        "artifact":        "stage1c_linkage_scores",
        "linkage_version": LINKAGE_VERSION,
        "vocab_version":   VOCAB_VERSION,
        "sheet":           str(args.sheet).replace("\\", "/"),
        "rows_total":      len(rows),
        "rows_annotated":  len(annotated),
        "rows_unfilled":   len(unfilled),
        "partial":         bool(unfilled),
        "direction_note": (
            "Precision on third_party and organizational is the headline: a detection "
            "wrongly filtered out leaves the inventory entirely, so the fifth check can "
            "never govern that type, and the release looks correct. Recall on subject is "
            "secondary; its failure mode is a visible over-block."),
        "census_note": (
            "Block A + Block B census all filtered detections corpus-wide, so precision "
            "on third_party and organizational is exact (no interval). Recall on subject "
            "is estimated from Block A only and carries a Wilson 95% interval."),
        "confusion_matrix": {pred: {t: confusion[pred][t] for t in CLASSES}
                             for pred in CLASSES},
        "per_class":        per_class,
        "errors_total":     len(errors),
        "silent_release_cases": {
            "count": len(silent),
            "note": ("Detections the human called `subject` that the classifier filtered "
                     "out. Each one is an information type that would silently leave the "
                     "inventory."),
            "documents": sorted({e["doc_id"] for e in silent}),
            "by_information_type": dict(Counter(e["information_type"] for e in silent)),
            "by_linkage_signal": dict(Counter(e["linkage_signal"] for e in silent)),
            "cases": silent,
        },
        "by_information_type": {k: rate(v) for k, v in sorted(by_type.items())},
        "by_region":           {k: rate(v) for k, v in sorted(by_region.items())},
        "by_linkage_signal":   {k: rate(v) for k, v in sorted(by_signal.items())},
    }
    out_json.write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    err_cols = ["row_id", "block", "doc_id", "document_type", "sensitivity_tier",
                "subject_type", "information_type", "value", "region", "field_label",
                "section", "classifier_said", "human_said", "linkage_signal",
                "tagger_rule", "silent_release"]
    with open(out_errors, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(err_cols)
        for e in sorted(errors, key=lambda x: (not x["silent_release"], x["row_id"])):
            w.writerow([e[c] for c in err_cols])

    # ---- report ------------------------------------------------------------
    print(f"Subject-linkage audit - vocab v{VOCAB_VERSION}, linkage v{LINKAGE_VERSION}")
    print(f"{len(annotated)} annotated rows"
          + (f" ({len(unfilled)} unfilled, PARTIAL)" if unfilled else "")
          + f", {len(errors)} misclassifications\n")

    print("HEADLINE - precision on the filtered classes")
    print("-" * 66)
    for cls in FILTERED_CLASSES:
        m = per_class[cls]
        tag = ("exact (census)" if m["precision_is_exact"]
               else "ESTIMATE - census incomplete" if unfilled else "estimate")
        pr = f"{m['precision']:.3f}" if m["precision"] is not None else "  -  "
        print(f"  {cls:<16} precision {pr}   "
              f"({m['tp']} of {m['predicted']} correct)   {tag}")
    print(f"\n  SILENT-RELEASE CASES (filtered out, actually subject): {len(silent)}")
    if silent:
        for e in silent:
            print(f"    {e['doc_id']}  {e['information_type']:<20} "
                  f"{e['classifier_said']:<15} value={e['value'][:34]!r}")
            print(f"        linkage signal: {e['linkage_signal']:<20} "
                  f"tagger rule: {e['tagger_rule']}")
        print(f"\n    documents affected: {', '.join(sorted({e['doc_id'] for e in silent}))}")

    print(f"\nSecondary - recall on `subject`")
    print("-" * 66)
    m = per_class[SUBJECT]
    rc = f"{m['recall']:.3f}" if m["recall"] is not None else "  -  "
    ci = m["recall_ci95"]
    print(f"  recall {rc}  ({m['tp']} of {m['actual']} true subject rows found)"
          + (f"   95% CI [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else ""))

    print(f"\nConfusion matrix (rows = classifier, columns = human)")
    print("-" * 66)
    print(f"  {'':<16}" + "".join(f"{c[:12]:>14}" for c in CLASSES))
    for pred in CLASSES:
        print(f"  {pred:<16}" + "".join(f"{confusion[pred][t]:>14}" for t in CLASSES))

    print(f"\nErrors by information type")
    print("-" * 66)
    for k, v in sorted(scores["by_information_type"].items(),
                       key=lambda kv: -kv[1]["errors"]):
        if v["errors"]:
            print(f"  {k:<22} {v['errors']:>3} of {v['n']:>3}  "
                  f"({v['error_rate']:.1%})   silent-release {v['silent_release']}")

    print(f"\nErrors by structural region")
    print("-" * 66)
    for k, v in sorted(scores["by_region"].items(), key=lambda kv: -kv[1]["errors"]):
        if v["errors"]:
            print(f"  {k:<22} {v['errors']:>3} of {v['n']:>3}  "
                  f"({v['error_rate']:.1%})   silent-release {v['silent_release']}")

    print(f"\nErrors by linkage signal (which rule got it wrong)")
    print("-" * 66)
    for k, v in sorted(scores["by_linkage_signal"].items(),
                       key=lambda kv: -kv[1]["errors"]):
        if v["errors"]:
            print(f"  {k:<22} {v['errors']:>3} of {v['n']:>3}  "
                  f"({v['error_rate']:.1%})   silent-release {v['silent_release']}")

    print(f"\nWrote:\n  {out_json}\n  {out_errors}")


if __name__ == "__main__":
    main()
