"""
Riverside Medical Clinic — Evaluation Flow Generator

Builds all (requester, document, expected_decision, flow_type) test cases
from the dataset and agent pool.

Flow taxonomy
-------------
F1  Authorized access          PERMIT  correct role + assigned to subject
F2  Wrong role                 DENY    role not in permitted_receiver_roles
F3  Right role, wrong patient  DENY    role ok, not assigned to this subject
F4  Extra-sensitive escalation DENY    role lacks extra-sensitive permission
F5  Public access              PERMIT  document is public tier
F6  Cross-context              DENY    deliberate context boundary crossing
                                       (e.g. Doctor → HR record)
"""

import json
from pathlib import Path

from core.Agent import Document, DocumentLabel, Attribute
from world.agents_pool import EXTENDED_ALL_AGENTS, EXTENDED_NAME_REGISTRY
from core.ci_policy import get_active_role, ASSIGNMENT_REQUIRED_TIERS

DATASET_PATH    = Path("data/dataset.json")
EVAL_FLOWS_PATH = Path("reports/eval_flows.json")

FLOW_TYPE_LABELS = {
    "F1": "Authorized access",
    "F2": "Wrong role",
    "F3": "Right role, wrong patient",
    "F4": "Extra-sensitive escalation",
    "F5": "Public access",
    "F6": "Cross-context",
}

EXPECTED_DECISION = {
    "F1": True,
    "F2": False,
    "F3": False,
    "F4": False,
    "F5": True,
    "F6": False,
}

# Roles that belong to each organizational context — used for F6 detection.
CONTEXT_ROLES = {
    "Medical":        {"Doctor", "Nurse"},
    "HR":             {"HR Manager"},
    "Administrative": {"Billing Specialist", "IT Contractor"},
    "Internal":       {"HR Manager", "Doctor", "Nurse", "Billing Specialist"},
    "Public":         set(),
    "Legal":          set(),
}


def load_dataset() -> list[dict]:
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def reconstruct_document(record: dict) -> Document:
    """Build a Document object from a flat dataset record."""
    label = DocumentLabel(
        document_type=record["document_type"],
        originating_context=record["originating_context"],
        sensitivity_tier=record["sensitivity_tier"],
        subject_type=record["subject_type"],
        pii_attributes=record.get("pii_attributes", []),
        implied_attributes=record.get("implied_attributes", []),
        extra_sensitive=record.get("extra_sensitive", False),
        extra_sensitive_reason=record.get("extra_sensitive_reason"),
        permitted_receiver_roles=record.get("permitted_receiver_roles", []),
        assignment_required=record.get("assignment_required", True),
        governing_principle=record.get("governing_principle"),
    )
    subject_name = record.get("subject_name")
    subject      = EXTENDED_NAME_REGISTRY.get(subject_name) if subject_name else None
    attributes   = [
        Attribute(information_type=a["information_type"], attribute=a.get("attribute", ""))
        for a in record.get("attributes", [])
        if a.get("information_type")
    ]
    return Document(
        title=record["title"],
        label=label,
        agent=subject,
        attributes=attributes,
        content=record.get("content", ""),
    )


def classify_flow(receiver, record: dict, doc: Document) -> tuple[str, bool]:
    """
    Classify a (receiver, document) pair into a flow type and expected decision.
    Returns (flow_type: str, expected_permit: bool).
    """
    tier               = record["sensitivity_tier"]
    extra_sensitive    = record.get("extra_sensitive", False)
    permitted_roles    = record.get("permitted_receiver_roles", [])
    assignment_req     = record.get("assignment_required", True)
    originating        = record.get("originating_context", "")

    # F5: public documents — no role or assignment restrictions
    if tier == "public":
        return "F5", True

    active_role = get_active_role(receiver)
    if active_role is None:
        return "F2", False

    role_name = active_role.role

    # ── Role check ────────────────────────────────────────────────
    if role_name not in permitted_roles:
        if extra_sensitive:
            # Role is blocked specifically because of heightened sensitivity
            return "F4", False

        # F6: role belongs to a context orthogonal to the document's origin
        # e.g. Doctor → HR record, HR Manager → clinical note
        own_contexts = {
            ctx for ctx, roles in CONTEXT_ROLES.items() if role_name in roles
        }
        if originating in CONTEXT_ROLES:
            originating_roles = CONTEXT_ROLES[originating]
            if originating_roles and role_name not in originating_roles:
                # Receiver's role has no legitimate stake in this context
                return "F6", False

        return "F2", False

    # ── Assignment check ──────────────────────────────────────────
    if assignment_req and doc.agent is not None:
        subject  = doc.agent
        assigned = any(
            str(ks.agent_id) == str(subject.uid)
            for ks in receiver.knowledge_base
        )
        if not assigned:
            return "F3", False

    return "F1", True


def generate_flows(records: list[dict] | None = None) -> list[dict]:
    """Generate all evaluation flows. Optionally pass pre-loaded records."""
    if records is None:
        records = load_dataset()

    docs = [(r, reconstruct_document(r)) for r in records]
    flows = []

    for receiver in EXTENDED_ALL_AGENTS:
        role = get_active_role(receiver)
        role_name = role.role if role else None

        for record, doc in docs:
            flow_type, expected = classify_flow(receiver, record, doc)
            flows.append({
                "requester_name":      receiver.name,
                "requester_role":      role_name,
                "document_title":      record["title"],
                "document_type":       record["document_type"],
                "sensitivity_tier":    record["sensitivity_tier"],
                "extra_sensitive":     record.get("extra_sensitive", False),
                "originating_context": record.get("originating_context", ""),
                "subject_name":        record.get("subject_name"),
                "flow_type":           flow_type,
                "flow_label":          FLOW_TYPE_LABELS[flow_type],
                "expected_permit":     expected,
            })

    return flows


def main():
    from collections import Counter

    records = load_dataset()
    print(f"Loaded {len(records)} documents, {len(EXTENDED_ALL_AGENTS)} agents")

    flows = generate_flows(records)
    print(f"Generated {len(flows)} evaluation flows\n")

    ft_counts = Counter(f["flow_type"] for f in flows)
    for ft in sorted(ft_counts):
        exp   = "PERMIT" if EXPECTED_DECISION[ft] else "DENY"
        label = FLOW_TYPE_LABELS[ft]
        print(f"  {ft}  {label:<35}  {ft_counts[ft]:>5} flows  [{exp}]")

    with open(EVAL_FLOWS_PATH, "w", encoding="utf-8") as f:
        json.dump(flows, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {EVAL_FLOWS_PATH}")


if __name__ == "__main__":
    main()
