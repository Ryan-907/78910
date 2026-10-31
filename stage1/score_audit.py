"""
Paper III — Stage 1 Deliverable 4b: Score the Manual Audit

Reads the completed audit sheet and computes precision, recall, F1 and
per-category miss rate for the Stage 1 tagger.

This module contains NO ground truth. It refuses to run on an unfilled sheet and
will not infer, impute, or model a missing verdict — the annotator's y/n is the
only source of truth, by design. Substituting an LLM for the annotator here would
mean scoring one extractor against another and reporting it as accuracy.

Confusion matrix, per (document, information type) cell
-------------------------------------------------------
    TP  tagger_detected=yes  present_in_document=y
    FP  tagger_detected=yes  present_in_document=n
    FN  tagger_detected=no   present_in_document=y     <-- the dangerous direction
    TN  tagger_detected=no   present_in_document=n

    precision = TP / (TP + FP)     recall = TP / (TP + FN)
    miss rate = FN / (TP + FN) = 1 - recall

Why miss rate is reported per category and led with: the future gate check is

    every information type in the document  ⊆  types the requester's role may receive

A false positive makes that test fail closed — a flow is denied that should have
been permitted, which someone notices. A miss makes it pass over information it
never saw: the document is released, the recipient holds a type they should not,
and no error is raised. Aggregate recall hides this, because a category the
tagger never finds contributes a handful of cells to a mostly-correct total. The
per-category table is where a silently unenforceable type shows up.

Interval estimates are Wilson score 95% intervals — appropriate here because
several per-category cells are small and the normal approximation would produce
intervals running past 0 or 1.

Usage
-----
    python -m stage1.score_audit
    python -m stage1.score_audit --sheet path/to/other_sheet.csv

Outputs (stage1/artifacts/audit/)
    audit_scores_v1.0.0.json
    audit_scores_by_type_v1.0.0.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from stage1.build_inventory import ARTIFACT_VERSION, JSON_PATH as INVENTORY_PATH
from stage1.sample_audit import AUDIT_DIR
from stage1.vocabulary import INFORMATION_TYPES, VOCAB, VOCAB_VERSION

SHEET_PATH  = AUDIT_DIR / f"audit_sheet_v{ARTIFACT_VERSION}.csv"
RECORD_PATH = AUDIT_DIR / f"audit_sample_v{ARTIFACT_VERSION}.json"
OUT_JSON    = AUDIT_DIR / f"audit_scores_v{ARTIFACT_VERSION}.json"
OUT_CSV     = AUDIT_DIR / f"audit_scores_by_type_v{ARTIFACT_VERSION}.csv"

TYPE_NAMES = [t.name for t in INFORMATION_TYPES]
TRUE_VALUES  = {"y", "yes", "true", "1"}
FALSE_VALUES = {"n", "no", "false", "0"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall    = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "support_present":  tp + fn,
        "support_detected": tp + fp,
        "precision":  round(precision, 4) if precision is not None else None,
        "recall":     round(recall, 4)    if recall    is not None else None,
        "f1":         round(f1, 4)        if f1        is not None else None,
        "miss_rate":  round(fn / (tp + fn), 4) if (tp + fn) else None,
        "precision_ci95": wilson(tp, tp + fp),
        "recall_ci95":    wilson(tp, tp + fn),
    }


def load_sheet(path: Path) -> list[dict]:
    """
    Read the annotation sheet as CSV or XLSX.

    Excel is the practical tool for a 400-row y/n pass, so an .xlsx saved from it
    is accepted directly. If only one of the CSV/XLSX pair exists, the sibling is
    used; if both exist, whichever carries annotations wins, so saving from Excel
    under the generated name does not silently score the blank original.

    The reader is standard-library only (stage1/xlsx_reader.py); no spreadsheet
    dependency is added.
    """
    def _read(p: Path) -> list[dict]:
        if p.suffix.lower() == ".xlsx":
            from stage1.xlsx_reader import read_dicts
            return read_dicts(p)
        with open(p, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def _filled(rows: list[dict]) -> int:
        return sum(1 for r in rows if (r.get("present_in_document") or "").strip())

    candidates = [path] if path.exists() else []
    for alt in (path.with_suffix(".xlsx"), path.with_suffix(".csv")):
        # Excel lock files (~$name.xlsx) are not annotation sheets.
        if alt.exists() and alt != path and not alt.name.startswith("~$"):
            candidates.append(alt)
    if not candidates:
        raise SystemExit(
            f"{path} not found. Run `python -m stage1.sample_audit` to generate it."
        )

    best, best_rows, best_filled = None, None, -1
    for cand in candidates:
        rows = _read(cand)
        n = _filled(rows)
        if n > best_filled:
            best, best_rows, best_filled = cand, rows, n
    if best != path:
        print(f"Reading {best.name} ({best_filled} annotated rows) "
              f"in preference to {path.name}.\n")
    return best_rows


def parse(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split into (annotated, unfilled). Raises on an unparseable verdict."""
    annotated, unfilled = [], []
    bad = []
    for i, r in enumerate(rows, start=2):   # +2: header is line 1
        raw = (r.get("present_in_document") or "").strip().lower()
        if not raw:
            unfilled.append(r)
            continue
        if raw in TRUE_VALUES:
            r["_present"] = True
        elif raw in FALSE_VALUES:
            r["_present"] = False
        else:
            bad.append((i, r.get("doc_id"), r.get("information_type"), raw))
            continue
        r["_detected"] = (r.get("tagger_detected", "").strip().lower() == "yes")
        annotated.append(r)

    if bad:
        lines = "\n".join(f"    line {ln}: {d} / {t} -> {v!r}" for ln, d, t, v in bad[:15])
        raise SystemExit(
            f"{len(bad)} row(s) have an unrecognized verdict. Use y or n.\n{lines}"
        )
    return annotated, unfilled


def fp_rules(annotated: list[dict]) -> dict[str, dict[str, int]]:
    """Attribute false positives to the tagger rule that produced them."""
    if not INVENTORY_PATH.exists():
        return {}
    inv = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    det = {d["doc_id"]: d["detections"] for d in inv["documents"]}

    out: dict[str, Counter] = defaultdict(Counter)
    for r in annotated:
        if not (r["_detected"] and not r["_present"]):
            continue
        for d in det.get(r["doc_id"], {}).get(r["information_type"], []):
            out[r["information_type"]][d["rule"]] += 1
    return {k: dict(v.most_common()) for k, v in sorted(out.items())}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", type=Path, default=SHEET_PATH)
    p.add_argument("--allow-partial", action="store_true",
                   help="score the annotated subset instead of refusing")
    args = p.parse_args()

    # Scoring a sheet other than the canonical one writes its results beside that
    # sheet, so a trial run cannot overwrite the real audit's artifacts.
    if args.sheet.resolve() == SHEET_PATH.resolve():
        out_json, out_csv = OUT_JSON, OUT_CSV
    else:
        stem = args.sheet.with_suffix("")
        out_json = stem.with_name(stem.name + "_scores.json")
        out_csv = stem.with_name(stem.name + "_scores_by_type.csv")

    rows = load_sheet(args.sheet)
    annotated, unfilled = parse(rows)

    if unfilled and not args.allow_partial:
        by_doc = Counter(r["doc_id"] for r in unfilled)
        print(f"Audit sheet is incomplete: {len(unfilled)} of {len(rows)} rows have no "
              f"verdict in 'present_in_document'.\n")
        print("Fill in y or n for every (document, information type) row, then re-run.")
        print("Rows outstanding, by document:")
        for d, c in sorted(by_doc.items()):
            print(f"    {d}  {c}")
        print("\nNo scores computed. This tool will not infer a missing verdict, and "
              "an LLM must not be substituted for the annotator — that would score one "
              "extractor against another and report it as accuracy.")
        print("\nTo score a partial pass anyway: python -m stage1.score_audit --allow-partial")
        raise SystemExit(1)

    # ---- confusion matrices ----
    overall = Counter()
    per_type: dict[str, Counter] = defaultdict(Counter)
    per_tier: dict[str, Counter] = defaultdict(Counter)

    for r in annotated:
        cell = ("tp" if r["_detected"] and r["_present"] else
                "fp" if r["_detected"] else
                "fn" if r["_present"] else "tn")
        overall[cell] += 1
        per_type[r["information_type"]][cell] += 1
        per_tier[r["sensitivity_tier"]][cell] += 1

    def m(c: Counter) -> dict:
        return metrics(c["tp"], c["fp"], c["fn"], c["tn"])

    scores = {
        "artifact":         "stage1_audit_scores",
        "artifact_version": ARTIFACT_VERSION,
        "vocab_version":    VOCAB_VERSION,
        "sheet":            str(args.sheet).replace("\\", "/"),
        "rows_total":       len(rows),
        "rows_annotated":   len(annotated),
        "rows_unfilled":    len(unfilled),
        "partial":          bool(unfilled),
        "sampling":         json.loads(RECORD_PATH.read_text(encoding="utf-8"))
                            if RECORD_PATH.exists() else None,
        "interval":         "Wilson score, 95%",
        "direction_note": (
            "Misses (FN) are the dangerous direction: an undetected information type "
            "means the future subset check passes over information it never saw, the "
            "document is released, and the decision looks correct. False positives "
            "fail closed and are self-correcting."
        ),
        "overall":              m(overall),
        "by_information_type":  {t: m(per_type[t]) for t in TYPE_NAMES},
        "by_sensitivity_tier":  {k: m(v) for k, v in sorted(per_tier.items())},
        "false_positive_rules": fp_rules(annotated),
    }
    out_json.write_text(json.dumps(scores, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    cols = ["tp", "fp", "fn", "tn", "support_present", "support_detected",
            "precision", "recall", "f1", "miss_rate"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["information_type"] + cols + ["recall_ci95_low", "recall_ci95_high"])
        for t in TYPE_NAMES:
            d = scores["by_information_type"][t]
            ci = d["recall_ci95"] or ("", "")
            w.writerow([t] + [d[c] for c in cols] + list(ci))

    # ---- report ----
    o = scores["overall"]
    print(f"Tagger accuracy audit — vocab v{VOCAB_VERSION}, "
          f"{len(annotated)} annotated cells"
          + (f" ({len(unfilled)} unfilled, PARTIAL)" if unfilled else ""))
    print()
    print(f"  TP {o['tp']:>4}   FP {o['fp']:>4}   FN {o['fn']:>4}   TN {o['tn']:>4}")
    print(f"  precision {o['precision']}  recall {o['recall']}  "
          f"F1 {o['f1']}  miss rate {o['miss_rate']}")

    print(f"\n{'information type':<22} {'TP':>4} {'FP':>4} {'FN':>4} "
          f"{'prec':>6} {'rec':>6} {'miss':>6}  recall 95% CI")
    print("-" * 76)
    for t in sorted(TYPE_NAMES,
                    key=lambda x: -(scores["by_information_type"][x]["miss_rate"] or -1)):
        d = scores["by_information_type"][t]
        ci = d["recall_ci95"]
        ci_s = f"[{ci[0]:.2f}, {ci[1]:.2f}]" if ci else "—"
        fmt = lambda v: f"{v:.3f}" if v is not None else "  —  "
        print(f"  {t:<20} {d['tp']:>4} {d['fp']:>4} {d['fn']:>4} "
              f"{fmt(d['precision']):>6} {fmt(d['recall']):>6} "
              f"{fmt(d['miss_rate']):>6}  {ci_s}")

    worst = [(t, d["miss_rate"]) for t, d in scores["by_information_type"].items()
             if d["miss_rate"] is not None and d["miss_rate"] > 0]
    if worst:
        worst.sort(key=lambda x: -x[1])
        print("\nCategories with a non-zero miss rate — the dangerous direction:")
        for t, mr in worst:
            d = scores["by_information_type"][t]
            print(f"    {t:<22} {mr:.1%}  ({d['fn']} of {d['support_present']} present "
                  f"cells undetected)")

    if scores["false_positive_rules"]:
        print("\nFalse positives attributed to tagger rules:")
        for t, rules in scores["false_positive_rules"].items():
            print(f"    {t:<22} " + ", ".join(f"{r} x{c}" for r, c in rules.items()))

    print(f"\nWrote:\n  {out_json}\n  {out_csv}")


if __name__ == "__main__":
    main()
