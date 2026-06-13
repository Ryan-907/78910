from __future__ import annotations
from pydantic import BaseModel, Field
from Agent import (
    Agent, Role, Employee, Patient, Contractor,
    Attribute, KnowledgeState, AttributeType,
    Document, SensitivityTier,
)

'''
Potential problems: The paper mentions the ability to infer subsets of T from larger subsets of T (e.g. post code in address)
But here, we assume all attributes are discrete values. This is a design choice that may need to be changed later.

Intuitively, an Agent can only send a Message with Attribute(s) that are known by the sending Agent.
A receiving Agent's knowledge state is updated upon receipt of message.

Roles are complex and indeterminate. The paper has it as PxR where we have (Agent, Role) in PotentialState.
Thus, (Alice, MD) in p is active as a medical doctor, while (Alice, Banking Customer) would not have those
permissions. get_active_role() resolves this by reading the single active `role` field on Employee/Patient/
Contractor subclasses. Full multi-role disambiguation (where a doctor is also a patient) is a known
limitation and is tracked in the roadmap.

A piece of information may be transmitted under some principle, so the principle of transmission must be
encoded in the message to ensure it is not shared beyond its intended scope.

FUNCTIONS IMPLEMENTED
    contains(m, q, t)              -> bool
    incontext(p, c)                -> bool
    derived_attributes(T)          -> list[Attribute]
    get_active_role(p)             -> Role | None
    get_transmission_principle(p)  -> str | None
    evaluate_flow(flow)            -> tuple[bool, str]

POLICIES DEFINED
    ROLE_ATTRIBUTE_PERMISSIONS     — blanket role → allowed attribute-type set
    ASSIGNMENT_REQUIRED            — attribute types requiring explicit KB authorization
    EXTRA_SENSITIVE                — subset of above with heightened access controls
    ROLE_TRANSMISSION_PRINCIPLES   — role → governing transmission principle string
    ATTRIBUTE_IMPLICATIONS         — attribute types that imply other sensitive types
'''


# ---------------------------------------------------------------------------
# Core CI models
# ---------------------------------------------------------------------------

class InformationFlow(BaseModel):
    subject: Agent | None = Field(
        description="The person the information is about",
        default=None,
    )
    sender: Agent | None = Field(
        description="The entity transmitting the information",
        default=None,
    )
    receiver: Agent | None = Field(
        description="The entity receiving the information",
        default=None,
    )
    message_type: str | None = Field(
        description="The AttributeType string being transferred",
        default=None,
    )
    transmission_principle: str | None = Field(
        description="The norm governing this flow (e.g. 'Doctor-Patient Confidentiality')",
        default=None,
    )


class Organization(BaseModel):
    name: str
    employees: list[Employee] = Field(
        default_factory=list,
        description="List of organization's active employees",
    )


# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

# Blanket permissions: which attribute types each role is ever allowed to touch.
# Passing this check is necessary but not sufficient — assignment is also required
# for sensitive types (see evaluate_flow).
ROLE_ATTRIBUTE_PERMISSIONS: dict[str, set[str]] = {
    "Doctor": {
        AttributeType.MEDICAL_DIAGNOSIS,
        AttributeType.MEDICAL_MEDICATION,
        AttributeType.MEDICAL_HISTORY,
        AttributeType.MENTAL_HEALTH,
        AttributeType.DATE_OF_BIRTH,
        AttributeType.EMERGENCY_CONTACT,
        AttributeType.MEDICAL_LICENSE,
    },
    "Nurse": {
        AttributeType.MEDICAL_DIAGNOSIS,
        AttributeType.MEDICAL_MEDICATION,
        AttributeType.MEDICAL_HISTORY,
        AttributeType.DATE_OF_BIRTH,
    },
    "Billing Specialist": {
        AttributeType.BILLING_CODE,
        AttributeType.INSURANCE_INFO,
        AttributeType.DATE_OF_BIRTH,
    },
    "HR Manager": {
        AttributeType.SALARY,
        AttributeType.EMPLOYMENT_CONTRACT,
        AttributeType.DATE_OF_BIRTH,
        AttributeType.HOME_ADDRESS,
        AttributeType.MEDICAL_LICENSE,
    },
    "IT Contractor": set(),   # no PHI access
    "Patient":        set(),  # self-access not yet modeled
}

# Attribute types where role-level permission alone is not enough — the receiver
# must also appear in the subject's care team (i.e., have a knowledge-base entry).
ASSIGNMENT_REQUIRED: set[str] = {
    AttributeType.MEDICAL_DIAGNOSIS,
    AttributeType.MEDICAL_MEDICATION,
    AttributeType.MEDICAL_HISTORY,
    AttributeType.MENTAL_HEALTH,
    AttributeType.BILLING_CODE,
    AttributeType.INSURANCE_INFO,
    AttributeType.SALARY,
    AttributeType.EMPLOYMENT_CONTRACT,
}

# Subset of ASSIGNMENT_REQUIRED that carries heightened sensitivity (stricter messaging).
EXTRA_SENSITIVE: set[str] = {AttributeType.MENTAL_HEALTH}

# The transmission principle that governs outbound flows for each role.
ROLE_TRANSMISSION_PRINCIPLES: dict[str, str] = {
    "Doctor":             "Doctor-Patient Confidentiality",
    "Nurse":              "Need-to-Know — Nursing Care",
    "Billing Specialist": "Operational — Billing",
    "HR Manager":         "Employment — Confidential HR",
    "IT Contractor":      "Administrative — No PHI",
    "Patient":            "Self-Access",
}

# Attribute types that imply other sensitive information.
# Key insight: ICD billing codes directly encode diagnoses (e.g. F33.1 = MDD).
# derived_attributes() uses this table to surface implied sensitive types.
ATTRIBUTE_IMPLICATIONS: dict[str, list[str]] = {
    AttributeType.BILLING_CODE:   [AttributeType.MEDICAL_DIAGNOSIS],
    AttributeType.HOME_ADDRESS:   [],   # postcode is a subset — not yet modeled
    AttributeType.INSURANCE_INFO: [],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def contains(m: list[KnowledgeState], q: Agent, t: str) -> bool:
    """True if knowledge list m has an entry about agent q with attribute type t."""
    return any(
        str(ks.agent_id) == str(q.uid) and ks.known_attribute.information_type == t
        for ks in m
    )


def incontext(p: Agent, c: str) -> bool:
    """True if agent p's currently active role has context c."""
    active = get_active_role(p)
    return active is not None and active.context == c


def derived_attributes(T: list[Attribute]) -> list[Attribute]:
    """
    Returns attribute instances implied by the given list.
    Example: billing_code implies medical_diagnosis because ICD codes reveal conditions.
    Avoids duplicating types already present in T.
    """
    implied: list[Attribute] = []
    seen: set[str] = {a.information_type for a in T if a.information_type}
    for attr in T:
        for implied_type in ATTRIBUTE_IMPLICATIONS.get(attr.information_type or "", []):
            if implied_type not in seen:
                implied.append(
                    Attribute(
                        information_type=implied_type,
                        attribute=f"[inferred from {attr.information_type}]",
                    )
                )
                seen.add(implied_type)
    return implied


def get_active_role(p: Agent) -> Role | None:
    """
    Returns the role an agent is currently acting in.

    Employee / Patient / Contractor subclasses carry a single `role` field that
    represents their active capacity. The base Agent class carries a `roles` list;
    for those, we fall back to the first entry (least-privilege would be better but
    requires explicit role selection — a known limitation).
    """
    # Prefer the authoritative single-role field on typed subclasses
    single = getattr(p, "role", None)
    if isinstance(single, Role):
        return single
    # Fall back: first role in the roles list
    roles_list: list[Role] | None = getattr(p, "roles", None)
    if roles_list:
        return roles_list[0]
    return None


def get_transmission_principle(receiver: Agent) -> str | None:
    """Returns the transmission principle applicable to the receiver's active role."""
    active = get_active_role(receiver)
    if active is None:
        return None
    return ROLE_TRANSMISSION_PRINCIPLES.get(active.role)


# ---------------------------------------------------------------------------
# CI gate
# ---------------------------------------------------------------------------

def evaluate_flow(flow: InformationFlow) -> tuple[bool, str]:
    """
    Evaluates an InformationFlow against clinic CI norms.
    Returns (allowed: bool, reason: str).

    Two-level check
    ---------------
    1. Knowledge-base authorization: if the receiver's KB already contains an entry
       for (subject, attribute_type), that entry encodes explicit prior authorization —
       allow the flow and record the governing transmission principle.
    2. Role-level fallback: if not in the KB, check whether the receiver's active role
       even has blanket permission for this attribute type.
         • No  → deny with a role-violation message.
         • Yes → the role permits the type but the receiver isn't assigned to this
                 subject → deny with a "not explicitly authorized" message.

    This means the knowledge_base is the single source of truth for who can see what.
    Role permissions act as the outer envelope that catches clearly-wrong requests
    (e.g. HR asking for a diagnosis) before they reach the assignment check.
    """
    receiver     = flow.receiver
    subject      = flow.subject
    message_type = flow.message_type

    if receiver is None or subject is None or message_type is None:
        return False, "Incomplete flow — receiver, subject, and message_type are all required"

    active_role = get_active_role(receiver)
    if active_role is None:
        return False, "Receiver has no identifiable active role — access denied by default"

    role_name = active_role.role

    # Level 1: explicit knowledge-base authorization
    if contains(receiver.knowledge_base, subject, message_type):
        principle = get_transmission_principle(receiver) or "unspecified principle"
        return True, f"Flow permitted under '{principle}'"

    # Level 2: role-level blanket permission
    role_allowed = ROLE_ATTRIBUTE_PERMISSIONS.get(role_name, set())
    if message_type not in role_allowed:
        return (
            False,
            f"Role '{role_name}' ({active_role.context}) has no permission "
            f"to access '{message_type}'"
        )

    # Role permits the type but the receiver is not explicitly assigned to this subject
    sensitivity = "extra-sensitive " if message_type in EXTRA_SENSITIVE else ""
    return (
        False,
        f"Access denied: {receiver.name} ({role_name}) is not explicitly authorized "
        f"to access {sensitivity}'{message_type}' for {subject.name}"
    )


# ---------------------------------------------------------------------------
# Document-level CI gate
# ---------------------------------------------------------------------------

# Document tiers that require the receiver to have an explicit KB entry for the
# document's subject (i.e. assignment). PUBLIC and INTERNAL are excluded because
# those documents have no individual subject — anyone with the right role may see them.
ASSIGNMENT_REQUIRED_TIERS: set[str] = {
    SensitivityTier.PII_BASIC,
    SensitivityTier.CLINICAL_STANDARD,
    SensitivityTier.CLINICAL_SENSITIVE,
    SensitivityTier.FINANCIAL,
    SensitivityTier.EMPLOYMENT,
}


def evaluate_document_flow(receiver: Agent, doc: Document) -> tuple[bool, str]:
    """
    Evaluates whether `receiver` may access `doc` under CI norms.
    Returns (allowed: bool, reason: str).

    Two-level check (mirrors evaluate_flow but operates on a Document):
      1. Role check: is the receiver's active role in doc.label.permitted_receiver_roles?
      2. Assignment check (for sensitive tiers only): does the receiver's knowledge_base
         contain at least one entry about the document's subject agent?
    """
    active_role = get_active_role(receiver)
    if active_role is None:
        return False, "Receiver has no identifiable active role — access denied by default"

    role_name = active_role.role

    # Level 1: role-level permission for this document type
    if role_name not in doc.label.permitted_receiver_roles:
        return (
            False,
            f"Role '{role_name}' ({active_role.context}) is not a permitted receiver "
            f"for '{doc.label.document_type}' documents "
            f"(tier: {doc.label.sensitivity_tier})"
        )

    # Level 2: assignment check for tiers that require it
    subject = doc.agent
    if subject is not None and doc.label.sensitivity_tier in ASSIGNMENT_REQUIRED_TIERS:
        assigned = any(str(ks.agent_id) == str(subject.uid) for ks in receiver.knowledge_base)
        if not assigned:
            sensitivity = "extra-sensitive " if doc.label.extra_sensitive else ""
            return (
                False,
                f"Access denied: {receiver.name} ({role_name}) has no authorized "
                f"relationship with {subject.name} for this {sensitivity}"
                f"'{doc.label.document_type}' record"
            )

    principle = doc.label.governing_principle or "no specific governing principle"
    return True, f"Document access permitted under '{principle}'"


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ryan = Agent()
    print(f"Ryan knows {ryan.knowledge_base}")
    marim = Agent()
    marim_height = Attribute(information_type="height", attribute="130cm")
    marim.attributes.append(marim_height)
    marim_ks = KnowledgeState(
        agent_id=marim.uid,
        known_attribute=marim_height,
        transmission_principle="Confidentiality",
    )
    marim.knowledge_base.append(marim_ks)

    marim.send_message(ryan, marim.knowledge_base)
    print(f"Ryan knows {[i.model_dump_json() for i in ryan.knowledge_base]}")

    # Quick derived_attributes demo
    billing_attr = Attribute(information_type=AttributeType.BILLING_CODE, attribute="99213, E11.9")
    implied = derived_attributes([billing_attr])
    print(f"Implied by billing_code: {[a.information_type for a in implied]}")
