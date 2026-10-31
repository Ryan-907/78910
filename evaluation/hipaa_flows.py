"""
HIPAA information-flow dataset (external ground truth).

Source
------
PrivaCI-Bench (HKUST-KnowComp), HIPAA split — derived from the GoldCoin corpus
of real HIPAA court cases. Each record is one information flow whose
permit / prohibit / not-applicable label is grounded in the HIPAA articles the
court found followed or violated. The label authority is the regulation and the
ruling, NOT an LLM — which is exactly why this can serve as ground truth for an
experiment that evaluates LLM-produced labels/decisions.

    Repo : https://github.com/HKUST-KnowComp/PrivaCI-Bench
    Paper: PrivaCI-Bench (arXiv:2502.17041)

The flows are transcribed VERBATIM. Roles and information types are the paper's
free-text values (e.g. "Law Enforcement/Judicial Authority") and are deliberately
NOT remapped onto the clinic's role enum — that mapping is a separate, reviewable
step and would break "use their flows exactly."

Dataset fields (data/hipaa_flows.json)
--------------------------------------
flow_id                 : stable id, "hipaa_0000" ...
norm_type               : "permit" | "prohibit" | "not applicable"  (ground truth)
expected_permit         : True | False | None   (None = out of HIPAA scope)
subject / sender / receiver / message_type / transmission_principle
                        : InformationFlow-shaped view (joined strings)
subject_role / sender_role / receiver_role
                        : verbatim free-text roles
raw                     : original PrivaCI sequence fields, untouched
followed_articles / violated_articles : HIPAA §s (the label's authority)
consent_form            : verbatim consent context
case_content            : the case narrative (the text an LLM would read)

Helpers
-------
load_hipaa_flows()          -> list[dict]
to_information_flow(record)  -> InformationFlow   (real sim object)
iter_information_flows()     -> (record, InformationFlow) pairs
"""

from __future__ import annotations

import json
from pathlib import Path

from core.Agent import Agent, Role
from core.ci_policy import InformationFlow

DATASET_PATH = Path("data/hipaa_flows.json")

# The context tag placed on every actor's Role. All flows in this corpus are
# adjudicated under HIPAA, so this is uniform and carries no hidden judgment.
FLOW_CONTEXT = "HIPAA"


def load_hipaa_flows(path: Path | str = DATASET_PATH) -> list[dict]:
    """Load the raw HIPAA flow records (verbatim PrivaCI ground truth)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _actor(name: str, role: str) -> Agent | None:
    """
    Build a lightweight sim Agent for an external party named in a flow.

    These are not clinic staff, so they get a base Agent carrying a single
    free-text Role. get_active_role() falls back to roles[0], so the role the
    court identified is what the sim sees.
    """
    name = (name or "").strip()
    role = (role or "").strip() or "Unspecified"
    if not name:
        return None
    return Agent(name=name, roles=[Role(role=role, context=FLOW_CONTEXT)])


def to_information_flow(record: dict) -> InformationFlow:
    """
    Construct a real InformationFlow from a dataset record.

    subject / sender / receiver become Agents carrying the flow's verbatim roles;
    message_type and transmission_principle come straight from the record. The
    ground-truth label (norm_type / expected_permit) lives on the record, not on
    the InformationFlow — the flow object is the *input* to whatever gate or LLM
    you are testing; the record is what you score against.
    """
    return InformationFlow(
        subject=_actor(record["subject"], record.get("subject_role", "")),
        sender=_actor(record["sender"], record.get("sender_role", "")),
        receiver=_actor(record["receiver"], record.get("receiver_role", "")),
        message_type=record["message_type"] or None,
        transmission_principle=record.get("transmission_principle") or None,
    )


def iter_information_flows(path: Path | str = DATASET_PATH):
    """Yield (record, InformationFlow) pairs."""
    for record in load_hipaa_flows(path):
        yield record, to_information_flow(record)


def main():
    from collections import Counter

    records = load_hipaa_flows()
    print(f"Loaded {len(records)} HIPAA flows from {DATASET_PATH}\n")

    print("Ground-truth label (norm_type):")
    for k, v in sorted(Counter(r["norm_type"] for r in records).items()):
        print(f"  {k:<18} {v:>4}")

    # Prove they construct as real sim objects.
    built = 0
    for record, flow in iter_information_flows():
        assert isinstance(flow, InformationFlow)
        built += 1
    print(f"\nConstructed {built} InformationFlow objects successfully.")

    r0, f0 = next(iter_information_flows())
    print("\nExample flow:")
    print(f"  id           : {r0['flow_id']}")
    print(f"  norm_type    : {r0['norm_type']}  (expected_permit={r0['expected_permit']})")
    print(f"  sender       : {f0.sender.name}  [{f0.sender.roles[0].role}]")
    print(f"  receiver     : {f0.receiver.name}  [{f0.receiver.roles[0].role}]")
    print(f"  subject      : {f0.subject.name}")
    print(f"  message_type : {f0.message_type}")
    print(f"  principle    : {f0.transmission_principle}")
    print(f"  violated §   : {r0['violated_articles']}")


if __name__ == "__main__":
    main()
