"""
Riverside Medical Clinic — Gate Evaluation (Phase 1)

Runs the CI gate on all evaluation flows and computes accuracy metrics.
No LLM calls — purely deterministic.

A False Positive (gate PERMITs an unauthorized flow) is the critical failure:
it represents a direct privacy violation. False Negatives (legitimate access
incorrectly denied) are operationally annoying but not a privacy risk.

Output
------
Prints a full accuracy table and writes gate_accuracy_report.json.
"""

import json
from collections import defaultdict
from pathlib import Path

from world.agents_pool import EXTENDED_ALL_AGENTS, EXTENDED_NAME_REGISTRY
from core.ci_policy import evaluate_document_flow
from evaluation.eval_flows import (
    load_dataset, reconstruct_document, generate_flows,
    FLOW_TYPE_LABELS, EXPECTED_DECISION,
)

GATE_REPORT_PATH = Path("reports/gate_accuracy_report.json")


def compute_metrics(tp: int, fp: int, tn: int, fn: int) -> dict:
    total     = tp + fp + tn + fn
    accuracy  = (tp + tn) / total       if total            else 0.0
    precision = tp / (tp + fp)          if (tp + fp)        else 0.0
    recall    = tp / (tp + fn)          if (tp + fn)        else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0.0)
    fpr       = fp / (fp + tn)          if (fp + tn)        else 0.0
    fnr       = fn / (fn + tp)          if (fn + tp)        else 0.0
    return dict(
        tp=tp, fp=fp, tn=tn, fn=fn,
        accuracy=round(accuracy,  4),
        precision=round(precision, 4),
        recall=round(recall,    4),
        f1=round(f1,        4),
        fpr=round(fpr,      4),
        fnr=round(fnr,      4),
    )


def main():
    records   = load_dataset()
    doc_map   = {r["title"]: (r, reconstruct_document(r)) for r in records}
    agent_map = {a.name: a for a in EXTENDED_ALL_AGENTS}

    flows = generate_flows(records)
    print(f"Gate evaluation: {len(flows)} flows across "
          f"{len(records)} documents and {len(EXTENDED_ALL_AGENTS)} agents\n")

    results        = []
    by_flow_type   = defaultdict(lambda: dict(tp=0, fp=0, tn=0, fn=0))
    by_tier        = defaultdict(lambda: dict(tp=0, fp=0, tn=0, fn=0))
    overall        = dict(tp=0, fp=0, tn=0, fn=0)
    false_positives = []

    for flow in flows:
        receiver = agent_map.get(flow["requester_name"])
        entry    = doc_map.get(flow["document_title"])
        if receiver is None or entry is None:
            continue

        _, doc         = entry
        expected       = flow["expected_permit"]
        flow_type      = flow["flow_type"]
        tier           = flow["sensitivity_tier"]

        gate_permit, reason = evaluate_document_flow(receiver, doc)

        if   expected and     gate_permit:  outcome = "TP"
        elif expected and not gate_permit:  outcome = "FN"
        elif not expected and gate_permit:  outcome = "FP"
        else:                               outcome = "TN"

        key = outcome.lower()
        by_flow_type[flow_type][key] += 1
        by_tier[tier][key]           += 1
        overall[key]                 += 1

        record = {**flow, "gate_permit": gate_permit, "gate_reason": reason, "outcome": outcome}
        results.append(record)

        if outcome == "FP":
            false_positives.append(record)

    # ── Compute metrics ────────────────────────────────────────────
    def metrics(c):
        return compute_metrics(c["tp"], c["fp"], c["tn"], c["fn"])

    flow_type_metrics = {ft: metrics(c) for ft, c in sorted(by_flow_type.items())}
    tier_metrics      = {t:  metrics(c) for t,  c in sorted(by_tier.items())}
    overall_metrics   = metrics(overall)

    # ── Print ──────────────────────────────────────────────────────
    print("=" * 62)
    print("GATE ACCURACY REPORT")
    print("=" * 62)

    m = overall_metrics
    print(f"\nOverall ({len(results)} flows evaluated)")
    print(f"  Accuracy  : {m['accuracy']:.1%}")
    print(f"  FPR       : {m['fpr']:.1%}   (privacy violations / all should-deny)")
    print(f"  FNR       : {m['fnr']:.1%}   (blocked legitimate / all should-permit)")
    print(f"  TP={m['tp']}  FP={m['fp']}  TN={m['tn']}  FN={m['fn']}")

    print(f"\nBy flow type:")
    for ft, fm in flow_type_metrics.items():
        exp = "PERMIT" if EXPECTED_DECISION.get(ft) else "DENY"
        print(f"  {ft}  {FLOW_TYPE_LABELS[ft]:<35} [{exp}]")
        print(f"       acc={fm['accuracy']:.1%}  FPR={fm['fpr']:.1%}  "
              f"TP={fm['tp']} FP={fm['fp']} TN={fm['tn']} FN={fm['fn']}")

    print(f"\nBy sensitivity tier:")
    for tier, tm in tier_metrics.items():
        print(f"  {tier:<25}  acc={tm['accuracy']:.1%}  "
              f"TP={tm['tp']} FP={tm['fp']} TN={tm['tn']} FN={tm['fn']}")

    print()
    if false_positives:
        print(f"{'!' * 62}")
        print(f"  {len(false_positives)} FALSE POSITIVE(S) — GATE FAILURE / PRIVACY VIOLATION")
        print(f"{'!' * 62}")
        for fp in false_positives[:10]:
            print(f"  [{fp['requester_name']}] ({fp['requester_role']}) "
                  f"→ [{fp['document_title'][:50]}]")
            print(f"    Gate reason: {fp['gate_reason']}")
    else:
        print("  No false positives — gate correctly denied all unauthorized flows.")

    # ── Save ───────────────────────────────────────────────────────
    report = {
        "total_flows":      len(results),
        "overall":          overall_metrics,
        "by_flow_type":     flow_type_metrics,
        "by_tier":          tier_metrics,
        "false_positives":  false_positives,
        "all_results":      results,
    }
    with open(GATE_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report written to {GATE_REPORT_PATH}")


if __name__ == "__main__":
    main()
