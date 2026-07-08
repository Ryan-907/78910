"""
Riverside Medical Clinic — Simulation Report Aggregator

Reads gate_accuracy_report.json and leakage_report.json and prints
a unified summary, then writes simulation_report.json.

Run after both phase evaluations are complete:
    python run_gate_eval.py
    python run_leakage_eval.py
    python simulation_report.py
"""

import json
from pathlib import Path

GATE_REPORT_PATH    = Path("reports/gate_accuracy_report.json")
LEAKAGE_REPORT_PATH = Path("reports/leakage_report.json")
SIM_REPORT_PATH     = Path("reports/simulation_report.json")

FLOW_TYPE_LABELS = {
    "F1": "Authorized access",
    "F2": "Wrong role",
    "F3": "Right role, wrong patient",
    "F4": "Extra-sensitive escalation",
    "F5": "Public access",
    "F6": "Cross-context",
}


def load(path: Path) -> dict | None:
    if not path.exists():
        print(f"  [not found] {path} — skipping")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def bar(value: float, width: int = 20) -> str:
    """ASCII progress bar for a 0–1 float."""
    filled = round(value * width)
    return "[" + "#" * filled + "." * (width - filled) + f"] {value:.1%}"


def main():
    gate = load(GATE_REPORT_PATH)
    leak = load(LEAKAGE_REPORT_PATH)

    print("=" * 64)
    print("  RIVERSIDE MEDICAL CLINIC — CI SIMULATION REPORT")
    print("=" * 64)

    # ── Phase 1: Gate accuracy ─────────────────────────────────────
    if gate:
        m = gate["overall"]
        print(f"\n{'─'*64}")
        print(f"  PHASE 1 — GATE ACCURACY  ({gate['total_flows']} flows evaluated)")
        print(f"{'─'*64}")
        print(f"\n  Accuracy              {bar(m['accuracy'])}")
        print(f"  False positive rate   {bar(m['fpr'])}  ← privacy violations")
        print(f"  False negative rate   {bar(m['fnr'])}  ← over-blocking")
        print(f"\n  TP (correct PERMIT)   : {m['tp']}")
        print(f"  TN (correct DENY)     : {m['tn']}")
        print(f"  FP (wrong PERMIT)     : {m['fp']}  {'*** GATE FAILURE ***' if m['fp'] else 'none'}")
        print(f"  FN (wrong DENY)       : {m['fn']}")

        print(f"\n  Flow type breakdown:")
        print(f"  {'Type':<5} {'Label':<35} {'Expected':<8} {'acc':>6}  {'FPR':>6}  {'FNR':>6}")
        print(f"  {'─'*5} {'─'*35} {'─'*8} {'─'*6}  {'─'*6}  {'─'*6}")
        from evaluation.eval_flows import EXPECTED_DECISION
        for ft, fm in gate["by_flow_type"].items():
            exp = "PERMIT" if EXPECTED_DECISION.get(ft) else "DENY"
            print(f"  {ft:<5} {FLOW_TYPE_LABELS.get(ft,'?'):<35} {exp:<8} "
                  f"{fm['accuracy']:>5.1%}  {fm['fpr']:>5.1%}  {fm['fnr']:>5.1%}")

        print(f"\n  Sensitivity tier breakdown:")
        print(f"  {'Tier':<25} {'acc':>6}  TP    FP    TN    FN")
        print(f"  {'─'*25} {'─'*6}  {'─'*4}  {'─'*4}  {'─'*4}  {'─'*4}")
        for tier, tm in gate["by_tier"].items():
            print(f"  {tier:<25} {tm['accuracy']:>5.1%}  "
                  f"{tm['tp']:>4}  {tm['fp']:>4}  {tm['tn']:>4}  {tm['fn']:>4}")

        fp_list = gate.get("false_positives", [])
        if fp_list:
            print(f"\n  {'!'*60}")
            print(f"  FALSE POSITIVES ({len(fp_list)}) — PRIVACY VIOLATIONS DETECTED")
            print(f"  {'!'*60}")
            for fp in fp_list[:10]:
                print(f"  [{fp['requester_name']}] ({fp['requester_role']}) → "
                      f"{fp['document_title'][:50]}")
                print(f"    {fp['gate_reason']}")
        else:
            print(f"\n  Gate result: ZERO false positives across all {gate['total_flows']} flows.")
            print(f"  All unauthorized access attempts correctly denied.")

    # ── Phase 2: Leakage ───────────────────────────────────────────
    if leak:
        tested = leak["total_tested"]
        lc     = leak["leaked_count"]
        lr     = leak["leakage_rate"]

        print(f"\n{'─'*64}")
        print(f"  PHASE 2 — LLM LEAKAGE  ({tested} denied flows tested)")
        print(f"{'─'*64}")
        print(f"\n  Leakage rate (L1+L2)  {bar(lr)}")
        print(f"  Clean denials         : {tested - lc}")
        print(f"  Leaked responses      : {lc}")

        leaked = [r for r in leak["results"] if r.get("leaked")]
        if leaked:
            print(f"\n  Leaked flows:")
            for r in leaked:
                f = r["flow"]
                print(f"  [{f['requester_name']}] ({f['flow_type']}) → "
                      f"{f['document_title'][:50]}")
                for phrase in r.get("l1_leakage", [])[:2]:
                    print(f"    L1 verbatim  : '{phrase[:60]}'")
                for t, v in r.get("l2_leakage", [])[:2]:
                    print(f"    L2 attribute : [{t}] {v[:50]}")
        else:
            print(f"\n  No verbatim or attribute-level leakage detected.")
            print(f"  Gate denials were respected — LLM did not reproduce denied content.")

    # ── Limitations note ──────────────────────────────────────────
    print(f"\n{'─'*64}")
    print(f"  LIMITATIONS")
    print(f"{'─'*64}")
    print(f"  L1/L2 leakage metrics are a lower bound (verbatim matching only).")
    print(f"  Semantic/paraphrase leakage (L3) is not measured — stated limitation.")
    print(f"  Gate accuracy is tautological given correct labels; labeling error")
    print(f"  is the primary threat surface, requiring human normative judgment.")

    # ── Write combined report ─────────────────────────────────────
    report = {
        "gate_summary":      gate["overall"]          if gate else None,
        "gate_by_flow_type": gate["by_flow_type"]     if gate else None,
        "gate_by_tier":      gate["by_tier"]          if gate else None,
        "false_positives":   gate.get("false_positives", []) if gate else [],
        "leakage_summary": {
            "total_tested":  leak["total_tested"],
            "leaked_count":  leak["leaked_count"],
            "leakage_rate":  leak["leakage_rate"],
        } if leak else None,
    }
    with open(SIM_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Combined report written to {SIM_REPORT_PATH}")
    print("=" * 64)


if __name__ == "__main__":
    main()
