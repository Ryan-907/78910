"""
Paper III — Stage 2b: The Fifth Conjoined Check

Extends Algorithm 1 with an information-type check, applied after the assignment
check and before PERMIT:

    { t : t in types(d) and subject_linked(t,d) }  subset-of  role_permissions[role(r)]

Access becomes a three-term intersection:

    A(agent) = D(role) ∩ D(assignment) ∩ D(information_types)

The existing gate is NOT modified
--------------------------------
`core.ci_policy.evaluate_document_flow` is imported and called, never edited.
This module runs it first and adds the fifth check only where it returned PERMIT,
so both gates can be run over the same flows and compared. That structure is also
what makes monotonicity true by construction rather than by assertion — see
`verify_monotonicity`, which checks it empirically anyway.

Properties this module guarantees, each verified rather than asserted
--------------------------------------------------------------------
MONOTONE      The extended permit set is a subset of the baseline permit set. The
              check can convert PERMIT -> DENY and never the reverse.
              `verify_monotonicity()` proves it over all 2,520 flows.
CONTENT-FREE  The decision path reads category NAMES on the label and the
              precomputed subject-linked type set. It never reads document text.
              `verify_content_free()` proves it by re-running every flow with
              document content replaced by a poison string and requiring
              byte-identical decisions and reasons.
STATELESS     No memory of prior requests; identical inputs give identical output
              indefinitely. `verify_stateless()` proves it by re-running the full
              adjudication in a shuffled order and requiring identical per-flow
              results.
EXPLAINABLE   A denial from the fifth check names the information type(s) that
              triggered it. Without that the new failure mode -- a document
              refused because of one attribute among many -- would be opaque
              exactly where opacity is most expensive.

The permission sets were authored by the researcher against frozen vocabulary
v1.2.0. No model proposed, ranked, or defaulted any of the 96 decisions.

Usage
-----
    python -m stage2.extended_gate      # runs the three property verifications
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from core.ci_policy import evaluate_document_flow, get_active_role
from evaluation.eval_flows import load_dataset, reconstruct_document
from world.agents_pool import EXTENDED_ALL_AGENTS

from stage1.build_inventory import doc_id, load_corpus
from stage1.subject_linkage import OUT_JSON as LINKAGE_PATH, LINKAGE_VERSION
from stage1.vocabulary import VOCAB, VOCAB_VERSION

PERMISSIONS_PATH = Path("stage2/artifacts") / f"role_permissions_v{VOCAB_VERSION}.json"

# Which of the five checks produced a denial. Checks 1-4 are attributed by reading
# the existing gate's own reason string rather than by reimplementing its logic --
# a reimplementation could drift out of agreement with the gate it describes.
CHECK_ROLE_ACTIVE   = "1_role_active"
CHECK_ROLE_CONTEXT  = "2_role_authoritative_in_context"
CHECK_ROLE_PERMITTED = "3_role_in_permitted_receiver_roles"
CHECK_ASSIGNMENT    = "4_assignment_held"
CHECK_INFO_TYPES    = "5_information_types"
PERMITTED           = None


def attribute_baseline_denial(reason: str) -> str:
    """Map the existing gate's reason string onto the check that produced it."""
    if "no identifiable active role" in reason:
        return CHECK_ROLE_ACTIVE
    if "is not authoritative in context" in reason:
        return CHECK_ROLE_CONTEXT
    if "is not a permitted receiver" in reason:
        return CHECK_ROLE_PERMITTED
    if "has no authorized relationship" in reason:
        return CHECK_ASSIGNMENT
    return "unattributed"


@dataclass(frozen=True)
class Policy:
    """
    Everything the fifth check reads. Frozen, and carries no document text.

    `subject_types` maps doc_id to the set of information types the Stage 1b/1d
    linkage classification found SUBJECT-linked in that document. Third-party and
    organisational occurrences are absent by construction: they are the recipient's
    business only in so far as they concern the subject, and the check governs what
    a role learns about the subject.
    """

    role_permissions: dict[str, frozenset[str]]
    subject_types: dict[str, frozenset[str]]
    vocab_version: str
    linkage_version: str

    def permitted_for(self, role: str) -> frozenset[str]:
        # A role absent from the authored sets permits nothing. Failing closed is
        # the safe direction for a check that can only remove access.
        return self.role_permissions.get(role, frozenset())


def load_policy() -> Policy:
    if not PERMISSIONS_PATH.exists():
        raise SystemExit(
            f"{PERMISSIONS_PATH} not found. Author the template and run "
            f"`python -m stage2.validate_permissions` first.")
    perms = json.loads(PERMISSIONS_PATH.read_text(encoding="utf-8"))
    if perms["vocab_version"] != VOCAB_VERSION:
        raise SystemExit(
            f"Permission sets were authored against vocabulary v{perms['vocab_version']} "
            f"but the vocabulary is now v{VOCAB_VERSION}. The vocabulary is frozen; "
            f"a change means re-authoring.")

    link = json.loads(LINKAGE_PATH.read_text(encoding="utf-8"))
    if link["corpus_sha256"] != load_corpus()[1]:
        raise SystemExit("Corpus changed since linkage was built.")
    if link["linkage_version"] != perms["linkage_version"]:
        raise SystemExit(
            f"Permission sets reference linkage v{perms['linkage_version']} but the "
            f"linkage artifact is v{link['linkage_version']}.")

    subject_types: dict[str, set[str]] = {}
    for d in link["detections"]:
        if d["classification"] == "subject":
            subject_types.setdefault(d["doc_id"], set()).add(d["information_type"])

    unknown = {t for ts in subject_types.values() for t in ts} - set(VOCAB)
    if unknown:
        raise SystemExit(f"linkage names types outside frozen v{VOCAB_VERSION}: {unknown}")

    return Policy(
        role_permissions={r: frozenset(t) for r, t in perms["roles"].items()},
        subject_types={k: frozenset(v) for k, v in subject_types.items()},
        vocab_version=perms["vocab_version"],
        linkage_version=perms["linkage_version"],
    )


# ---------------------------------------------------------------------------
# The fifth check
# ---------------------------------------------------------------------------

def information_type_check(role: str | None, did: str,
                           policy: Policy) -> tuple[bool, frozenset[str]]:
    """
    The fifth check in isolation, evaluated independently of checks 1-4.

    Returns (passes, excess_types). Kept separate from `evaluate_document_flow_extended`
    so the denial-overlap analysis can ask "would check 5 have denied this?" of every
    flow, including those checks 1-4 already denied.
    """
    if role is None:
        return False, policy.subject_types.get(did, frozenset())
    carried = policy.subject_types.get(did, frozenset())
    excess = carried - policy.permitted_for(role)
    return (not excess), excess


def evaluate_document_flow_extended(receiver, doc, did: str,
                                    policy: Policy) -> tuple[bool, str, str | None]:
    """
    Algorithm 1 plus the fifth check.

    Returns (allowed, reason, triggering_check). Conjoined and last: the baseline
    gate runs first and unchanged, and the fifth check is reached only where the
    baseline permitted, so it can subtract from the permit set and never add.
    """
    allowed, reason = evaluate_document_flow(receiver, doc)
    if not allowed:
        return False, reason, attribute_baseline_denial(reason)

    active = get_active_role(receiver)
    role = active.role if active else None
    passes, excess = information_type_check(role, did, policy)
    if passes:
        return True, reason, PERMITTED

    # Name the triggering types. A denial that says only "information type policy"
    # would move the opacity into exactly the place the new failure mode lives.
    named = ", ".join(f"'{t}'" for t in sorted(excess))
    return False, (
        f"Access denied: role '{role}' may not receive {named} about "
        f"{getattr(doc.agent, 'name', 'the subject')} "
        f"(carried by this '{doc.label.document_type}' record)"
    ), CHECK_INFO_TYPES


# ---------------------------------------------------------------------------
# Flow construction
# ---------------------------------------------------------------------------

def build_flows() -> list[tuple]:
    """All (agent, doc_id, record, Document) pairs — the 24 x 105 cross product."""
    records = load_dataset()
    docs = [(doc_id(i), r, reconstruct_document(r)) for i, r in enumerate(records)]
    return [(a, did, rec, doc) for a in EXTENDED_ALL_AGENTS for did, rec, doc in docs]


def adjudicate(policy: Policy, flows=None) -> list[dict]:
    """Both gates over every flow. Deterministic; order follows `flows`."""
    out = []
    for agent, did, rec, doc in (flows if flows is not None else build_flows()):
        base_ok, base_reason = evaluate_document_flow(agent, doc)
        ext_ok, ext_reason, check = evaluate_document_flow_extended(agent, doc, did, policy)
        active = get_active_role(agent)
        role = active.role if active else None
        passes5, excess = information_type_check(role, did, policy)
        out.append({
            "agent": agent.name,
            "role": role,
            "doc_id": did,
            "document_type": rec["document_type"],
            "sensitivity_tier": rec["sensitivity_tier"],
            "subject_name": rec.get("subject_name"),
            "baseline_permit": base_ok,
            "baseline_reason": base_reason,
            "baseline_check": None if base_ok else attribute_baseline_denial(base_reason),
            "extended_permit": ext_ok,
            "extended_reason": ext_reason,
            "triggering_check": check,
            # Evaluated for every flow, not only those the baseline permitted, so
            # denial overlap can be computed.
            "check5_passes": passes5,
            "check5_excess_types": sorted(excess),
        })
    return out


# ---------------------------------------------------------------------------
# Property verification
# ---------------------------------------------------------------------------

def verify_monotonicity(rows: list[dict]) -> dict:
    """The extended permit set must be a STRICT subset of the baseline permit set."""
    base = {(r["agent"], r["doc_id"]) for r in rows if r["baseline_permit"]}
    ext  = {(r["agent"], r["doc_id"]) for r in rows if r["extended_permit"]}
    violations = sorted(ext - base)
    return {
        "baseline_permits": len(base),
        "extended_permits": len(ext),
        "is_subset": not violations,
        "is_strict_subset": (not violations) and len(ext) < len(base),
        "violations": [{"agent": a, "doc_id": d} for a, d in violations],
        "converted_permit_to_deny": len(base - ext),
    }


def verify_content_free(policy: Policy, rows: list[dict]) -> dict:
    """
    Re-adjudicate with every document's content replaced by a poison string.

    If any decision or reason changes, content reached the decision path.
    """
    poison = "!!CONTENT-MUST-NOT-REACH-THE-DECISION-PATH!!"
    records = load_dataset()
    docs = []
    for i, r in enumerate(records):
        doc = reconstruct_document(r)
        doc.content = poison
        # Attribute VALUES are content too; only the type names may be read.
        for a in doc.attributes:
            a.attribute = poison
        docs.append((doc_id(i), r, doc))
    flows = [(a, did, rec, doc) for a in EXTENDED_ALL_AGENTS for did, rec, doc in docs]
    poisoned = adjudicate(policy, flows)

    mismatches = [
        {"agent": a["agent"], "doc_id": a["doc_id"],
         "with_content": a["extended_reason"], "without": b["extended_reason"]}
        for a, b in zip(rows, poisoned)
        if a["extended_permit"] != b["extended_permit"]
        or a["extended_reason"] != b["extended_reason"]
    ]
    return {
        "flows_compared": len(rows),
        "content_free": not mismatches,
        "mismatches": mismatches[:20],
        "mismatch_count": len(mismatches),
    }


def verify_stateless(policy: Policy, rows: list[dict], seed: int = 7926) -> dict:
    """Re-adjudicate in a shuffled order; per-flow results must be identical."""
    flows = build_flows()
    rng = random.Random(seed)
    shuffled = flows[:]
    rng.shuffle(shuffled)
    again = {(r["agent"], r["doc_id"]): r for r in adjudicate(policy, shuffled)}

    mismatches = [
        {"agent": r["agent"], "doc_id": r["doc_id"]}
        for r in rows
        if (again[(r["agent"], r["doc_id"])]["extended_permit"] != r["extended_permit"]
            or again[(r["agent"], r["doc_id"])]["extended_reason"] != r["extended_reason"])
    ]
    return {
        "seed": seed,
        "flows_compared": len(rows),
        "stateless": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
    }


def main() -> None:
    policy = load_policy()
    rows = adjudicate(policy)

    mono = verify_monotonicity(rows)
    free = verify_content_free(policy, rows)
    stateless = verify_stateless(policy, rows)

    print(f"Extended gate — vocabulary v{policy.vocab_version} (frozen), "
          f"linkage v{policy.linkage_version}")
    print(f"{len(rows)} flows\n")
    print("Property verification")
    print("-" * 62)
    print(f"  MONOTONE     baseline permits {mono['baseline_permits']}, "
          f"extended {mono['extended_permits']}")
    print(f"               subset: {mono['is_subset']}   "
          f"strict subset: {mono['is_strict_subset']}   "
          f"violations: {len(mono['violations'])}")
    print(f"  CONTENT-FREE {free['flows_compared']} flows re-run with poisoned "
          f"content -> identical: {free['content_free']}")
    print(f"  STATELESS    re-run in shuffled order (seed {stateless['seed']}) "
          f"-> identical: {stateless['stateless']}")

    if not mono["is_subset"]:
        raise SystemExit(
            "\nSTOP: the extended gate PERMITS flows the baseline DENIED. The fifth "
            "check is not conjoined-and-last. Nothing downstream should be trusted.")
    if not free["content_free"]:
        raise SystemExit(
            f"\nSTOP: {free['mismatch_count']} decision(s) changed when document "
            f"content was replaced. Content is reaching the decision path.")
    if not stateless["stateless"]:
        raise SystemExit(
            f"\nSTOP: {stateless['mismatch_count']} decision(s) differ on re-run. "
            f"The gate is carrying state.")

    print(f"\n  all three properties hold; "
          f"{mono['converted_permit_to_deny']} flows converted PERMIT -> DENY")


if __name__ == "__main__":
    main()
