"""
Experiment 3: LLM labels -> the deterministic gate -> downstream leaks.

The gate is fixed and proven (100% / 0-FP on human labels). Here we swap the
human labels for each LLM's labels and re-run the SAME gate over all
(requester, document) flows. Because only the label changed, every new leak or
over-block is attributable to the label — and we attribute each leak to the
specific field (permitted_receiver_roles vs sensitivity_tier) via counterfactual
flip-back.

Reports, per model:
  * label-field agreement vs human ground truth (tier, permitted roles, extra_sensitive)
  * induced PRIVACY VIOLATIONS: flows the gate denies under human labels but
    PERMITS under LLM labels (baseline is 0)
  * induced over-blocking: flows permitted under human labels but denied under LLM labels
  * per-violation attribution: which label field caused the leak

Run:  python -m evaluation.run_labeler_eval   [--limit N]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.Agent import Document, DocumentLabel, Attribute
from core.ci_policy import evaluate_document_flow
from world.agents_pool import EXTENDED_ALL_AGENTS, EXTENDED_NAME_REGISTRY
from evaluation.eval_flows import load_dataset
from evaluation.llm_labeler import run_labeler, DEFAULT_MODELS

REPORT_PATH = Path("reports/labeler_eval_report.json")


def build_doc(record: dict, tier: str, roles: list[str], extra: bool) -> Document:
    """Reconstruct a Document with an overridden (tier, roles, extra_sensitive) label."""
    label = DocumentLabel(
        document_type=record["document_type"],
        originating_context=record["originating_context"],
        sensitivity_tier=tier,
        subject_type=record["subject_type"],
        pii_attributes=record.get("pii_attributes", []),
        implied_attributes=record.get("implied_attributes", []),
        extra_sensitive=extra,
        extra_sensitive_reason=record.get("extra_sensitive_reason"),
        permitted_receiver_roles=roles,
        assignment_required=record.get("assignment_required", True),
        governing_principle=record.get("governing_principle"),
    )
    subject = EXTENDED_NAME_REGISTRY.get(record.get("subject_name")) if record.get("subject_name") else None
    attrs = [Attribute(information_type=a["information_type"], attribute=a.get("attribute", ""))
             for a in record.get("attributes", []) if a.get("information_type")]
    return Document(title=record["title"], label=label, agent=subject, attributes=attrs,
                    content=record.get("content", ""))


def decide(agent, record, tier, roles, extra) -> bool:
    permit, _ = evaluate_document_flow(agent, build_doc(record, tier, roles, extra))
    return permit


def score_model(records: list[dict], labels: dict[str, dict]) -> dict:
    agents = EXTENDED_ALL_AGENTS

    # label-field agreement
    tier_hits = role_exact = extra_hits = n_labeled = 0
    role_over = role_under = 0     # extra roles granted / roles missing vs human
    n_docs = 0

    # flow-level diff
    new_fp = []     # base deny, llm permit  (privacy violation)
    new_fn = 0      # base permit, llm deny  (over-block)
    total_flows = 0
    attribution = Counter()

    for record in records:
        title = record["title"]
        lab = labels.get(title)
        n_docs += 1
        if lab is None or not lab.get("ok", True):
            continue  # unlabeled doc — skip (counted as error separately)
        n_labeled += 1

        h_tier = record["sensitivity_tier"]
        h_roles = set(record.get("permitted_receiver_roles", []))
        h_extra = record.get("extra_sensitive", False)
        l_tier = lab["sensitivity_tier"]
        l_roles = set(lab["permitted_receiver_roles"])
        l_extra = lab["extra_sensitive"]

        tier_hits += (l_tier == h_tier)
        role_exact += (l_roles == h_roles)
        extra_hits += (l_extra == h_extra)
        role_over += len(l_roles - h_roles)
        role_under += len(h_roles - l_roles)

        h_roles_l = record.get("permitted_receiver_roles", [])
        l_roles_l = lab["permitted_receiver_roles"]
        for agent in agents:
            total_flows += 1
            base = decide(agent, record, h_tier, h_roles_l, h_extra)
            llm  = decide(agent, record, l_tier, l_roles_l, l_extra)
            if base and not llm:
                new_fn += 1
            elif (not base) and llm:
                # induced privacy violation — attribute it
                deny_if_roles_fixed = not decide(agent, record, l_tier, h_roles_l, l_extra)
                deny_if_tier_fixed  = not decide(agent, record, h_tier, l_roles_l, l_extra)
                if deny_if_roles_fixed and deny_if_tier_fixed:
                    cause = "roles+tier"
                elif deny_if_roles_fixed:
                    cause = "permitted_roles too broad"
                elif deny_if_tier_fixed:
                    cause = "tier under-rated"
                else:
                    cause = "other"
                attribution[cause] += 1
                new_fp.append({"requester": agent.name, "doc": title,
                               "human_tier": h_tier, "llm_tier": l_tier,
                               "human_roles": sorted(h_roles), "llm_roles": sorted(l_roles),
                               "cause": cause})

    return {
        "n_docs": n_docs,
        "n_labeled": n_labeled,
        "label_agreement": {
            "tier_exact":  round(tier_hits / n_labeled, 4) if n_labeled else 0.0,
            "roles_exact": round(role_exact / n_labeled, 4) if n_labeled else 0.0,
            "extra_sensitive_acc": round(extra_hits / n_labeled, 4) if n_labeled else 0.0,
            "roles_over_granted_total": role_over,
            "roles_under_granted_total": role_under,
        },
        "flows": {
            "total": total_flows,
            "induced_privacy_violations": len(new_fp),
            "privacy_violation_rate": round(len(new_fp) / total_flows, 5) if total_flows else 0.0,
            "induced_overblocks": new_fn,
            "overblock_rate": round(new_fn / total_flows, 5) if total_flows else 0.0,
        },
        "attribution": dict(attribution),
        "violations": new_fp[:40],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    records = load_dataset()
    if args.limit:
        records = records[:args.limit]
    print(f"Loaded {len(records)} clinic documents. Labelers: {', '.join(models)}\n")

    report = {"n_docs": len(records), "baseline": "gate + human labels = 0 violations (proven)",
              "models": {}}

    for model in models:
        print(f"--- labeling with {model} ---")
        labels = run_labeler(model, records, limit=args.limit)
        report["models"][model] = score_model(records, labels)

    # ── print ──────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("LLM-AS-LABELER -> DETERMINISTIC GATE   (baseline: human labels = 0 violations)")
    print("=" * 78)
    print(f"\n{'model':<20} {'tier-ok':>7} {'roles-ok':>8} {'LEAKS (induced)':>18} {'over-block':>12}")
    print("-" * 70)
    for model in models:
        m = report["models"][model]
        la = m["label_agreement"]; fl = m["flows"]
        leaks = f"{fl['induced_privacy_violations']} ({fl['privacy_violation_rate']:.2%})"
        ob = f"{fl['induced_overblocks']}"
        print(f"{model:<20} {la['tier_exact']:>6.0%} {la['roles_exact']:>7.0%} {leaks:>18} {ob:>12}")

    print("\nWhat caused the induced privacy violations (per field):")
    for model in models:
        att = report["models"][model]["attribution"]
        print(f"  {model}: {att if att else 'none'}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
