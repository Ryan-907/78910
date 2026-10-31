"""
Paper III — Stage 2b: Re-adjudicate all 2,520 flows and measure

Runs the baseline four-check gate and the extended five-check gate over the full
(agent x document) cross product with agents, assignments, role sets, and tiers
held fixed, then produces the four measurements.

Measurements
------------
1. OVER-DELIVERY CLOSED   flows that were PERMIT and are now DENY, attributed to
                          the information type responsible, and broken down by
                          role and tier.

2. OVER-BLOCKS INTRODUCED flows now denied that the authored policy does not
                          intend to deny. Measured, not asserted: the fifth check
                          is re-run using the HUMAN labels from the Stage 1c audit
                          in place of the classifier's linkage, and the flows that
                          flip back to PERMIT are over-blocks caused by linkage
                          error rather than by policy. Over-blocks are norm
                          violations too (Paper II III-D), so they are reported
                          separately from (1) and never netted against it.

3. DENIAL OVERLAP         every denial classified role-only, attribute-only, or
                          both. Then an ablation with `permitted_receiver_roles`
                          removed entirely, to measure what each field is actually
                          doing rather than asserting they differ.

4. UNREACHABLE DOCUMENTS  documents whose own permitted roles cannot receive their
                          own subject-linked types, and which are therefore
                          reachable by nobody. These are defects in the authored
                          policy that nothing currently surfaces.

Read-only with respect to the corpus, labels, assignment relation, and the
existing gate. The ablation builds modified Document objects in memory; nothing
is written back.

Usage
-----
    python -m stage2.adjudicate

Outputs (stage2/artifacts/)
    adjudication_v1.2.0.csv        one row per flow, both gates
    adjudication_v1.2.0.json       summary + all four measurements
    over_delivery_v1.2.0.csv       the closed flows, one per row
    unreachable_documents_v1.2.0.csv
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.ci_policy import evaluate_document_flow, get_active_role
from evaluation.eval_flows import load_dataset, reconstruct_document
from world.agents_pool import EXTENDED_ALL_AGENTS

from stage1.build_inventory import doc_id, load_corpus
from stage1.vocabulary import VOCAB_VERSION, INFORMATION_TYPES
from stage2.build_template import ROLES
from stage2.extended_gate import (
    Policy, load_policy, adjudicate, build_flows, information_type_check,
    evaluate_document_flow_extended, verify_monotonicity, verify_content_free,
    verify_stateless, CHECK_INFO_TYPES,
)

ARTIFACT_DIR = Path("stage2/artifacts")
FLOWS_CSV    = ARTIFACT_DIR / f"adjudication_v{VOCAB_VERSION}.csv"
SUMMARY_JSON = ARTIFACT_DIR / f"adjudication_v{VOCAB_VERSION}.json"
CLOSED_CSV   = ARTIFACT_DIR / f"over_delivery_v{VOCAB_VERSION}.csv"
UNREACH_CSV  = ARTIFACT_DIR / f"unreachable_documents_v{VOCAB_VERSION}.csv"

AUDIT_SHEET = Path("stage1/artifacts/audit/linkage_sheet_v1.1.0.xlsx")
AUDIT_KEY   = Path("stage1/artifacts/audit/linkage_key_v1.1.0.json")
TAGGER_SAMPLE = Path("stage1/artifacts/audit/audit_sample_v1.0.0.json")


# ---------------------------------------------------------------------------
# 1. Over-delivery closed
# ---------------------------------------------------------------------------

def over_delivery(rows: list[dict]) -> dict:
    closed = [r for r in rows if r["baseline_permit"] and not r["extended_permit"]]
    by_type = Counter()
    by_type_sole = Counter()
    for r in closed:
        by_type.update(r["check5_excess_types"])
        if len(r["check5_excess_types"]) == 1:
            by_type_sole[r["check5_excess_types"][0]] += 1
    return {
        "flows_closed": len(closed),
        "baseline_permits": sum(1 for r in rows if r["baseline_permit"]),
        "extended_permits": sum(1 for r in rows if r["extended_permit"]),
        "by_information_type": dict(by_type.most_common()),
        "by_information_type_sole_cause": dict(by_type_sole.most_common()),
        "by_role": dict(Counter(r["role"] for r in closed).most_common()),
        "by_tier": dict(Counter(r["sensitivity_tier"] for r in closed).most_common()),
        "by_document_type": dict(Counter(r["document_type"] for r in closed).most_common()),
        "flows": closed,
    }


# ---------------------------------------------------------------------------
# 2. Over-blocks introduced, measured against the human labels
# ---------------------------------------------------------------------------

def human_subject_types() -> tuple[dict[str, set[str]], set[str], dict]:
    """
    Rebuild the subject-linked type map from the Stage 1c HUMAN labels.

    Returns (types_by_doc, fully_audited_doc_ids, provenance).

    Coverage is uneven by design, and the distinction matters:

      * The 25 Block A documents had EVERY detection labelled, so their type sets
        can be rebuilt exactly from ground truth. Over-blocks are measured on
        these and nowhere else.
      * Elsewhere only the classifier's filtered detections were labelled, so a
        correction there can only ADD types (human said subject where the
        classifier filtered). Adding types can only cause more denials, so it
        bounds over-delivery rather than over-blocks and is not used for (2).
    """
    if not AUDIT_SHEET.exists():
        return {}, set(), {"available": False}
    from stage1.xlsx_reader import read_dicts

    key = json.loads(AUDIT_KEY.read_text(encoding="utf-8"))["rows"]
    sheet = read_dicts(AUDIT_SHEET)
    fully = set(json.loads(TAGGER_SAMPLE.read_text(encoding="utf-8"))["doc_ids"])

    types: dict[str, set[str]] = defaultdict(set)
    labelled = 0
    for row in sheet:
        verdict = (row.get("true_class") or "").strip().casefold()
        k = key.get(row.get("row_id", ""))
        if not k or not verdict:
            continue
        labelled += 1
        if verdict in ("subject", "s", "subj"):
            types[k["doc_id"]].add(k["information_type"])

    return types, fully, {
        "available": True,
        "labels_read": labelled,
        "fully_audited_documents": len(fully),
        "note": ("Over-blocks are measured only on the 25 fully-audited documents, "
                 "where every detection carries a human label and the type set can "
                 "be rebuilt exactly."),
    }


def over_blocks(policy: Policy, rows: list[dict]) -> dict:
    human, fully, prov = human_subject_types()
    if not prov.get("available"):
        return {"measurable": False, "reason": "no completed linkage audit found"}

    # Policy identical in every respect except that subject-linkage comes from the
    # human labels rather than the classifier, on the fully-audited documents.
    corrected = dict(policy.subject_types)
    for did in fully:
        corrected[did] = frozenset(human.get(did, set()))
    corrected_policy = Policy(policy.role_permissions, corrected,
                              policy.vocab_version, policy.linkage_version)

    flows = build_flows()
    by_key = {(r["agent"], r["doc_id"]): r for r in rows}
    introduced, missed = [], []
    for agent, did, rec, doc in flows:
        if did not in fully:
            continue
        base = by_key[(agent.name, did)]
        ok, reason, check = evaluate_document_flow_extended(
            agent, doc, did, corrected_policy)
        # Denied under the classifier, permitted under ground truth => the denial
        # was caused by linkage error, not by the authored policy.
        if not base["extended_permit"] and ok:
            introduced.append({
                "agent": agent.name, "role": base["role"], "doc_id": did,
                "document_type": base["document_type"],
                "sensitivity_tier": base["sensitivity_tier"],
                "denied_on_types": base["check5_excess_types"],
                "reason_under_classifier": base["extended_reason"],
            })
        # Permitted under the classifier, denied under ground truth => the
        # classifier let through a flow the policy would have refused.
        if base["extended_permit"] and not ok:
            missed.append({
                "agent": agent.name, "role": base["role"], "doc_id": did,
                "document_type": base["document_type"],
                "sensitivity_tier": base["sensitivity_tier"],
                "reason_under_ground_truth": reason,
            })

    scope = [r for r in rows if r["doc_id"] in fully]
    return {
        "measurable": True,
        "provenance": prov,
        "scope_flows": len(scope),
        "scope_documents": len(fully),
        "over_blocks_introduced": len(introduced),
        "over_block_rate_in_scope": (round(len(introduced) / len(scope), 4)
                                     if scope else None),
        "by_role": dict(Counter(f["role"] for f in introduced).most_common()),
        "by_type": dict(Counter(t for f in introduced
                                for t in f["denied_on_types"]).most_common()),
        "flows": introduced,
        "silent_passes_under_classifier": len(missed),
        "silent_pass_flows": missed,
    }


# ---------------------------------------------------------------------------
# 3. Denial overlap and the role-field ablation
# ---------------------------------------------------------------------------

def denial_overlap(rows: list[dict]) -> dict:
    """Every denial classified by which check(s) would independently catch it."""
    buckets = Counter()
    attribute_only: list[dict] = []
    for r in rows:
        if r["extended_permit"]:
            continue
        role_denies = r["baseline_check"] == "3_role_in_permitted_receiver_roles"
        attr_denies = not r["check5_passes"]
        other_denies = (r["baseline_check"] is not None and not role_denies)
        if role_denies and attr_denies:
            buckets["both_role_and_attribute"] += 1
        elif role_denies:
            buckets["role_only"] += 1
        elif attr_denies and not other_denies:
            buckets["attribute_only"] += 1
            attribute_only.append(r)
        elif attr_denies and other_denies:
            buckets["attribute_and_other_check"] += 1
        else:
            buckets["other_check_only"] += 1
    return {
        "denials_total": sum(1 for r in rows if not r["extended_permit"]),
        "buckets": dict(buckets.most_common()),
        "attribute_only_note": (
            "Flows the fifth check uniquely catches: role, context and assignment "
            "all pass, and only the information-type check refuses them."),
        "attribute_only_by_type": dict(Counter(
            t for r in attribute_only for t in r["check5_excess_types"]).most_common()),
        "attribute_only_by_role": dict(Counter(
            r["role"] for r in attribute_only).most_common()),
        "attribute_only_flows": attribute_only,
    }


def role_field_ablation(policy: Policy, rows: list[dict]) -> dict:
    """
    Re-adjudicate with `permitted_receiver_roles` removed entirely.

    Measures what the role field is actually doing rather than asserting that it
    and the attribute check differ. Documents are rebuilt in memory with every
    role permitted; nothing is written back to the corpus.
    """
    records = load_dataset()
    ablated = []
    for i, r in enumerate(records):
        doc = reconstruct_document(r)
        doc.label.permitted_receiver_roles = list(ROLES)
        ablated.append((doc_id(i), r, doc))
    flows = [(a, did, rec, doc) for a in EXTENDED_ALL_AGENTS for did, rec, doc in ablated]

    no_role_4check = no_role_5check = 0
    leaked: list[dict] = []
    by_key = {(r["agent"], r["doc_id"]): r for r in rows}
    for agent, did, rec, doc in flows:
        base_ok, _ = evaluate_document_flow(agent, doc)
        ext_ok, _reason, _c = evaluate_document_flow_extended(agent, doc, did, policy)
        if base_ok:
            no_role_4check += 1
        if ext_ok:
            no_role_5check += 1
            # Permitted without the role field, refused with it: the role field is
            # doing work here that the attribute check does not replicate.
            if not by_key[(agent.name, did)]["extended_permit"]:
                leaked.append({
                    "agent": agent.name,
                    "role": by_key[(agent.name, did)]["role"],
                    "doc_id": did,
                    "document_type": rec["document_type"],
                    "sensitivity_tier": rec["sensitivity_tier"],
                })
    return {
        "note": ("permitted_receiver_roles removed (every role permitted on every "
                 "document); checks 1, 2, 4 and 5 unchanged."),
        "permits_without_role_field_4check": no_role_4check,
        "permits_without_role_field_5check": no_role_5check,
        "permits_with_role_field_4check": sum(1 for r in rows if r["baseline_permit"]),
        "permits_with_role_field_5check": sum(1 for r in rows if r["extended_permit"]),
        "flows_the_role_field_uniquely_blocks": len(leaked),
        "by_role": dict(Counter(f["role"] for f in leaked).most_common()),
        "by_tier": dict(Counter(f["sensitivity_tier"] for f in leaked).most_common()),
        "by_document_type": dict(Counter(f["document_type"] for f in leaked).most_common()),
        "examples": leaked[:25],
    }


# ---------------------------------------------------------------------------
# 4. Unreachable documents
# ---------------------------------------------------------------------------

def unreachable_documents(policy: Policy) -> dict:
    """
    Documents whose own permitted roles cannot receive their own subject-linked
    types. Nobody the label admits can pass the fifth check, so the document is
    reachable by no one — a defect in the authored policy rather than in the gate.
    """
    records = load_dataset()
    out = []
    for i, rec in enumerate(records):
        did = doc_id(i)
        permitted_roles = [r for r in rec.get("permitted_receiver_roles", [])]
        if not permitted_roles:
            continue
        carried = policy.subject_types.get(did, frozenset())
        if not carried:
            continue
        blocking: dict[str, list[str]] = {}
        for role in permitted_roles:
            passes, excess = information_type_check(role, did, policy)
            if not passes:
                blocking[role] = sorted(excess)
        if len(blocking) == len(permitted_roles):
            union = sorted({t for v in blocking.values() for t in v})
            out.append({
                "doc_id": did,
                "title": rec["title"],
                "document_type": rec["document_type"],
                "sensitivity_tier": rec["sensitivity_tier"],
                "subject_name": rec.get("subject_name"),
                "permitted_receiver_roles": permitted_roles,
                "blocking_types_by_role": blocking,
                "conflicting_types": union,
            })
    return {
        "count": len(out),
        "note": ("Every role the label admits is refused by the fifth check, so no "
                 "agent can reach the document. A policy defect, surfaced here "
                 "because nothing else in the pipeline would."),
        "by_document_type": dict(Counter(d["document_type"] for d in out).most_common()),
        "by_tier": dict(Counter(d["sensitivity_tier"] for d in out).most_common()),
        "by_conflicting_type": dict(Counter(
            t for d in out for t in d["conflicting_types"]).most_common()),
        "documents": out,
    }


# ---------------------------------------------------------------------------

def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    policy = load_policy()
    rows = adjudicate(policy)

    mono = verify_monotonicity(rows)
    if not mono["is_subset"]:
        raise SystemExit("STOP: monotonicity violated; see stage2.extended_gate.")
    free = verify_content_free(policy, rows)
    stateless = verify_stateless(policy, rows)

    m1 = over_delivery(rows)
    m2 = over_blocks(policy, rows)
    m3 = denial_overlap(rows)
    m3_ablation = role_field_ablation(policy, rows)
    m4 = unreachable_documents(policy)

    # ---- per-flow CSV ----
    with open(FLOWS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = ["agent", "role", "doc_id", "document_type", "sensitivity_tier",
                "subject_name", "baseline_permit", "baseline_check",
                "extended_permit", "triggering_check", "check5_passes",
                "check5_excess_types", "extended_reason"]
        w.writerow(cols)
        for r in rows:
            w.writerow([r["agent"], r["role"], r["doc_id"], r["document_type"],
                        r["sensitivity_tier"], r["subject_name"],
                        r["baseline_permit"], r["baseline_check"] or "",
                        r["extended_permit"], r["triggering_check"] or "",
                        r["check5_passes"], ";".join(r["check5_excess_types"]),
                        r["extended_reason"]])

    with open(CLOSED_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["agent", "role", "doc_id", "document_type", "sensitivity_tier",
                    "subject_name", "excess_types", "reason"])
        for r in m1["flows"]:
            w.writerow([r["agent"], r["role"], r["doc_id"], r["document_type"],
                        r["sensitivity_tier"], r["subject_name"],
                        ";".join(r["check5_excess_types"]), r["extended_reason"]])

    with open(UNREACH_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "title", "document_type", "sensitivity_tier",
                    "subject_name", "permitted_receiver_roles", "conflicting_types"])
        for d in m4["documents"]:
            w.writerow([d["doc_id"], d["title"], d["document_type"],
                        d["sensitivity_tier"], d["subject_name"],
                        ";".join(d["permitted_receiver_roles"]),
                        ";".join(d["conflicting_types"])])

    summary = {
        "artifact":        "stage2b_adjudication",
        "vocab_version":   policy.vocab_version,
        "linkage_version": policy.linkage_version,
        "corpus_sha256":   load_corpus()[1],
        "flows":           len(rows),
        "properties": {"monotonicity": mono, "content_free": free,
                       "stateless": stateless},
        "m1_over_delivery_closed": {k: v for k, v in m1.items() if k != "flows"},
        "m2_over_blocks_introduced": {k: v for k, v in m2.items()
                                      if k not in ("flows", "silent_pass_flows")},
        "m2_over_block_flows": m2.get("flows", []),
        "m2_silent_pass_flows": m2.get("silent_pass_flows", []),
        "m3_denial_overlap": {k: v for k, v in m3.items()
                              if k != "attribute_only_flows"},
        "m3_role_field_ablation": m3_ablation,
        "m4_unreachable_documents": m4,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")

    # ---- report ----
    print(f"Stage 2b adjudication — vocabulary v{policy.vocab_version} (frozen), "
          f"linkage v{policy.linkage_version}")
    print(f"{len(rows)} flows, 24 agents x 105 documents\n")
    print(f"  baseline (4 checks) : {m1['baseline_permits']:>5} permit")
    print(f"  extended (5 checks) : {m1['extended_permits']:>5} permit")
    print(f"  monotone            : subset {mono['is_subset']}, "
          f"strict {mono['is_strict_subset']}, violations {len(mono['violations'])}")
    print(f"  content-free        : {free['content_free']}")
    print(f"  stateless           : {stateless['stateless']}")

    print(f"\n1. OVER-DELIVERY CLOSED — {m1['flows_closed']} flows PERMIT -> DENY")
    print("-" * 66)
    print("   by information type responsible (a flow may carry several):")
    for t, c in m1["by_information_type"].items():
        sole = m1["by_information_type_sole_cause"].get(t, 0)
        print(f"      {t:<22} {c:>4}   (sole cause in {sole})")
    print(f"   by role : {m1['by_role']}")
    print(f"   by tier : {m1['by_tier']}")

    print(f"\n2. OVER-BLOCKS INTRODUCED")
    print("-" * 66)
    if not m2["measurable"]:
        print(f"   not measurable: {m2['reason']}")
    else:
        print(f"   measured against human labels on {m2['scope_documents']} fully-audited "
              f"documents ({m2['scope_flows']} flows)")
        print(f"   over-blocks introduced : {m2['over_blocks_introduced']}"
              f"  ({m2['over_block_rate_in_scope']:.2%} of in-scope flows)")
        if m2["by_type"]:
            print(f"   by type : {m2['by_type']}")
            print(f"   by role : {m2['by_role']}")
        print(f"   flows the classifier let through that ground truth would refuse: "
              f"{m2['silent_passes_under_classifier']}")

    print(f"\n3. DENIAL OVERLAP — {m3['denials_total']} denials")
    print("-" * 66)
    for k, v in m3["buckets"].items():
        print(f"      {k:<30} {v:>5}")
    if m3["attribute_only_by_type"]:
        print(f"   attribute-only, by type : {m3['attribute_only_by_type']}")
        print(f"   attribute-only, by role : {m3['attribute_only_by_role']}")
    ab = m3_ablation
    print(f"\n   ablation: permitted_receiver_roles removed entirely")
    print(f"      permits, 4 checks : {ab['permits_with_role_field_4check']:>5} with "
          f"-> {ab['permits_without_role_field_4check']:>5} without")
    print(f"      permits, 5 checks : {ab['permits_with_role_field_5check']:>5} with "
          f"-> {ab['permits_without_role_field_5check']:>5} without")
    print(f"      flows the role field uniquely blocks: "
          f"{ab['flows_the_role_field_uniquely_blocks']}")
    print(f"         by tier : {ab['by_tier']}")

    print(f"\n4. UNREACHABLE DOCUMENTS — {m4['count']}")
    print("-" * 66)
    if m4["count"]:
        print(f"   by conflicting type : {m4['by_conflicting_type']}")
        for d in m4["documents"]:
            print(f"      {d['doc_id']}  {d['document_type']:<24} "
                  f"{d['sensitivity_tier']}")
            print(f"         roles {d['permitted_receiver_roles']} all blocked on "
                  f"{d['conflicting_types']}")
    else:
        print("   none")

    print(f"\nWrote:\n  {FLOWS_CSV}\n  {SUMMARY_JSON}\n  {CLOSED_CSV}\n  {UNREACH_CSV}")


if __name__ == "__main__":
    main()
