"""
Experiment 4: how stable is an LLM's CI label across identical re-labelings?

The mediator thesis rests on determinism: the gate returns the same decision for
the same (policy, label, requester) every time, and the LLM does not. Experiments
1-3 measure whether the LLM's label is CORRECT. This one measures whether it is
even STABLE — the same document, the same prompt, the same model, N times.

There is no temperature to blame. These models reject sampling parameters
outright, so every disagreement here is the model's own non-determinism on a
fixed input.

Reports, per model:
  * label stability      — % of documents where all N draws agree, per label field
  * tier entropy         — mean Shannon entropy (bits) of the tier distribution
  * DECISION instability — % of the 2,520 (requester, document) flows whose gate
                           decision changes across draws. This is the headline:
                           the gate is deterministic, so every unstable flow is
                           attributable to the label alone.
  * coin-flip breaches   — flows the gate denies under human labels that some
                           draws permit and others deny: a re-roll is the
                           difference between a breach and no breach
  * leak count per draw  — min / median / max / stdev, i.e. error bars on the
                           single-draw headline numbers from experiment 3

Run:  python -m evaluation.run_variance_eval --samples 5   [--limit N]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from world.agents_pool import EXTENDED_ALL_AGENTS
from evaluation.eval_flows import load_dataset
from evaluation.llm_client import DEFAULT_MODELS
from evaluation.llm_labeler import run_labeler, load_all_samples
from evaluation.run_labeler_eval import decide

REPORT_PATH = Path("reports/variance_report.json")


def entropy(values: list) -> float:
    """Shannon entropy in bits of a categorical sample. 0.0 = perfectly stable."""
    n = len(values)
    if n <= 1:
        return 0.0
    counts = Counter(map(str, values))
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def score_model(records: list[dict], draws: dict[str, list[dict]], want: int) -> dict:
    agents = EXTENDED_ALL_AGENTS

    n_docs = n_multi = 0
    tier_stable = roles_stable = extra_stable = all_stable = 0
    tier_entropies: list[float] = []
    role_set_counts: list[int] = []

    total_flows = 0
    unstable_flows = 0
    coin_flip_breaches: list[dict] = []
    leaks_per_draw = [0] * want
    flows_per_draw = [0] * want
    unstable_examples: list[dict] = []

    for record in records:
        title = record["title"]
        ds = [d for d in draws.get(title, []) if d.get("ok", True)][:want]
        n_docs += 1
        if len(ds) < 2:
            continue          # need at least two draws to say anything about stability
        n_multi += 1
        k = len(ds)

        tiers = [d["sensitivity_tier"] for d in ds]
        role_sets = [frozenset(d["permitted_receiver_roles"]) for d in ds]
        extras = [d["extra_sensitive"] for d in ds]

        t_ok = len(set(tiers)) == 1
        r_ok = len(set(role_sets)) == 1
        e_ok = len(set(extras)) == 1
        tier_stable += t_ok
        roles_stable += r_ok
        extra_stable += e_ok
        all_stable += (t_ok and r_ok and e_ok)
        tier_entropies.append(entropy(tiers))
        role_set_counts.append(len(set(role_sets)))

        # ── flow-level: does the gate's decision move when only the label is re-rolled? ──
        h_tier = record["sensitivity_tier"]
        h_roles = record.get("permitted_receiver_roles", [])
        h_extra = record.get("extra_sensitive", False)

        for agent in agents:
            base = decide(agent, record, h_tier, h_roles, h_extra)
            per_draw = [
                decide(agent, record, d["sensitivity_tier"],
                       d["permitted_receiver_roles"], d["extra_sensitive"])
                for d in ds
            ]
            total_flows += 1
            for i, permit in enumerate(per_draw):
                flows_per_draw[i] += 1
                if (not base) and permit:
                    leaks_per_draw[i] += 1

            if len(set(per_draw)) > 1:
                unstable_flows += 1
                # Denied by the human policy, but some draws release it anyway.
                if not base:
                    coin_flip_breaches.append({
                        "requester": agent.name,
                        "doc": title,
                        "permits": sum(per_draw),
                        "of_draws": k,
                        "human_roles": sorted(h_roles),
                        "draw_roles": [sorted(s) for s in {tuple(sorted(s)) for s in role_sets}],
                    })
                if len(unstable_examples) < 25:
                    unstable_examples.append({
                        "requester": agent.name, "doc": title,
                        "decisions": per_draw, "tiers": tiers,
                        "role_sets": [sorted(s) for s in role_sets],
                    })

    # A draw that failed on some documents covers fewer flows, so its raw leak
    # COUNT is not comparable to a complete draw's. Report rates for every draw,
    # and reserve the count range for draws with full coverage.
    max_flows = max(flows_per_draw) if flows_per_draw else 0
    rates = [l / f for l, f in zip(leaks_per_draw, flows_per_draw) if f]
    complete = [l for l, f in zip(leaks_per_draw, flows_per_draw) if f == max_flows]
    partial = [i for i, f in enumerate(flows_per_draw) if f and f != max_flows]
    used = complete or [l for l, f in zip(leaks_per_draw, flows_per_draw) if f]
    return {
        "n_docs": n_docs,
        "n_docs_with_multiple_draws": n_multi,
        "draws_requested": want,
        "label_stability": {
            "tier_all_draws_agree":  round(tier_stable / n_multi, 4) if n_multi else 0.0,
            "roles_all_draws_agree": round(roles_stable / n_multi, 4) if n_multi else 0.0,
            "extra_all_draws_agree": round(extra_stable / n_multi, 4) if n_multi else 0.0,
            "every_field_agrees":    round(all_stable / n_multi, 4) if n_multi else 0.0,
            "mean_tier_entropy_bits": round(statistics.mean(tier_entropies), 4) if tier_entropies else 0.0,
            "mean_distinct_role_sets": round(statistics.mean(role_set_counts), 3) if role_set_counts else 0.0,
            "max_distinct_role_sets": max(role_set_counts) if role_set_counts else 0,
        },
        "decision_stability": {
            "flows_compared": total_flows,
            "unstable_flows": unstable_flows,
            "unstable_rate": round(unstable_flows / total_flows, 5) if total_flows else 0.0,
            "coin_flip_breaches": len(coin_flip_breaches),
        },
        "leaks_per_draw": {
            "counts_all_draws": [l for l, f in zip(leaks_per_draw, flows_per_draw) if f],
            "flows_all_draws": [f for f in flows_per_draw if f],
            "rates_all_draws": [round(r, 5) for r in rates],
            "partial_draw_indices": partial,   # excluded from the count range below
            "counts": used,                    # complete-coverage draws only
            "n_complete_draws": len(complete),
            "min": min(used) if used else 0,
            "median": round(statistics.median(used), 1) if used else 0,
            "max": max(used) if used else 0,
            "stdev": round(statistics.stdev(used), 2) if len(used) > 1 else 0.0,
            "range": (max(used) - min(used)) if used else 0,
        },
        "coin_flip_breach_examples": coin_flip_breaches[:25],
        "unstable_flow_examples": unstable_examples,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--samples", type=int, default=5,
                    help="draws per document (default 5; sample 0 reuses the existing cache)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-run", action="store_true",
                    help="score whatever is already cached; make no API calls")
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    records = load_dataset()
    if args.limit:
        records = records[:args.limit]
    print(f"Loaded {len(records)} clinic documents. "
          f"{args.samples} draws x {len(models)} models\n")

    report = {"n_docs": len(records), "samples": args.samples,
              "gate": "deterministic — identical decision for identical (policy, label, requester)",
              "models": {}}

    for model in models:
        if not args.no_run:
            print(f"--- re-labeling with {model} ({args.samples} draws) ---")
            run_labeler(model, records, limit=args.limit, samples=args.samples)
        report["models"][model] = score_model(records, load_all_samples(model), args.samples)

    # ── print ──────────────────────────────────────────────────────────
    print("\n" + "=" * 84)
    print(f"LABEL VARIANCE ACROSS {args.samples} IDENTICAL RE-LABELINGS "
          "(no temperature — these models reject it)")
    print("=" * 84)
    print(f"\n{'model':<20} {'tier same':>10} {'ACL same':>9} {'all same':>9} "
          f"{'UNSTABLE FLOWS':>16} {'leaks (min-max)':>17}")
    print("-" * 84)
    for model in models:
        m = report["models"][model]
        ls, ds, lp = m["label_stability"], m["decision_stability"], m["leaks_per_draw"]
        unst = f"{ds['unstable_flows']} ({ds['unstable_rate']:.2%})"
        leaks = f"{lp['min']}-{lp['max']} (sd {lp['stdev']})"
        print(f"{model:<20} {ls['tier_all_draws_agree']:>9.0%} "
              f"{ls['roles_all_draws_agree']:>8.0%} {ls['every_field_agrees']:>8.0%} "
              f"{unst:>16} {leaks:>17}")

    print(f"\n{'model':<20} {'mean tier entropy':>18} {'distinct ACLs/doc':>18} "
          f"{'coin-flip breaches':>19}")
    print("-" * 78)
    for model in models:
        m = report["models"][model]
        ls, ds = m["label_stability"], m["decision_stability"]
        print(f"{model:<20} {ls['mean_tier_entropy_bits']:>17.3f}b "
              f"{ls['mean_distinct_role_sets']:>18.2f} {ds['coin_flip_breaches']:>19}")

    print("\nBaseline: the gate + a fixed human label produces the SAME decision on all")
    print("2,520 flows, every run, by construction. Every number above is label-induced.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
