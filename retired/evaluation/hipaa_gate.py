"""
Deterministic HIPAA gate — the human-authored policy P, enforced mechanically.

This is the architectural counterpart to the LLM-as-judge: instead of asking a
probabilistic model to decide what may be disclosed, a human authors a policy
over Contextual-Integrity parameters (sender, recipient, information, purpose)
and the gate applies it faithfully and identically every time.

The policy below is authored from HIPAA Privacy Rule PRINCIPLES, BLIND to the
ground-truth `norm_type` labels — the rules were written from 45 CFR Part 164,
not fitted to the answers. That is what makes the gate's fidelity meaningful
rather than circular.

Design stance (matches run_gate_eval.py's philosophy):
  * Releasing data that should be withheld = the critical failure (a privacy
    breach). The gate must NEVER do this on a should-deny flow.
  * Withholding data that could have been released = safe (operationally
    annoying, not a breach). The gate accepts this cost.
  * Therefore: when the gate cannot VERIFY that a disclosure exception applies
    (court order, valid authorization, treatment relationship), it DENIES.

Contract:  gate_decision(record) -> "permit" | "prohibit" | "not applicable"
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Feature extraction — transparent keyword maps over the flow's free-text CI
# fields. Built by reading the VOCABULARY of the corpus, never its labels.
# ---------------------------------------------------------------------------

# Recipient categories, checked most-specific first.
_RECIPIENT_PATTERNS: list[tuple[str, str]] = [
    ("patient_self",    r"patient|subject of|individual|the subject|himself|herself|data subject"),
    ("law_enforcement", r"law enforcement|police|officer|fbi|detective|investigator|sheriff|prosecut"),
    ("judicial_legal",  r"\blegal\b|court|attorney|counsel|litigant|defendant|plaintiff|adjudicat|"
                        r"judge|judicial|tribunal|expert witness|deposition|opposing"),
    ("family_rep",      r"parent|spouse|family|guardian|next of kin|representative|deceased|estate|heir"),
    ("government",      r"government|agenc|regulator|public entity|administrator|oversight|"
                        r"department of|state of|federal"),
    ("payer",           r"insur|health plan|payer|payor|medicaid|medicare"),
    ("employer",        r"employer|employment"),
    ("media_public",    r"media|press|public|journalist|reporter|news"),
    ("covered_entity",  r"health ?care|provider|physician|doctor|nurse|hospital|clinic|"
                        r"treating|medical (staff|center)|therapist|pharmac"),
]

# Sender categories — HIPAA only governs disclosures BY a covered entity /
# business associate. A non-covered sender => the Privacy Rule does not apply.
_COVERED_SENDER = re.compile(
    r"health ?care|provider|physician|doctor|nurse|hospital|clinic|treating|"
    r"medical|therapist|pharmac|insur|health plan|payer|payor|covered entity|"
    r"business associate|medicaid|medicare",
    re.I,
)

_PURPOSE_TREATMENT = re.compile(
    r"treatment|patient care|continuity of care|coordination|referral|payment|"
    r"billing|reimburs|health care operation", re.I)
_PURPOSE_COURT_ORDER = re.compile(
    r"court order|subpoena|warrant|ordered by (the )?court|judicial order|"
    r"pursuant to (a )?court|discovery order", re.I)
_PURPOSE_PUBLIC_HEALTH = re.compile(
    r"public health|disease|outbreak|epidemic|cdc|mandatory report|reportable|"
    r"abuse|neglect|required by law|health oversight|audit", re.I)


def _match_category(text: str, patterns: list[tuple[str, str]]) -> str:
    t = (text or "").lower()
    for name, pat in patterns:
        if re.search(pat, t):
            return name
    return "other"


def recipient_category(record: dict) -> str:
    return _match_category(record.get("receiver_role", "") + " " + record.get("receiver", ""),
                           _RECIPIENT_PATTERNS)


def sender_is_covered(record: dict) -> bool:
    field = (record.get("sender_role", "") + " " + record.get("sender", ""))
    return bool(_COVERED_SENDER.search(field))


# ---------------------------------------------------------------------------
# The policy P — deterministic disclosure rules (45 CFR Part 164)
# ---------------------------------------------------------------------------

def gate_decision(record: dict) -> str:
    """
    Apply the human-authored HIPAA policy to one information flow.
    Returns permit / prohibit / not applicable. Never consults `norm_type`.
    """
    purpose = record.get("transmission_principle", "") or ""

    # (0) Scope: HIPAA governs disclosures made BY a covered entity/BA. If the
    #     discloser is not one, the Privacy Rule does not apply. (§160.102/103)
    if not sender_is_covered(record):
        return "not applicable"

    rc = recipient_category(record)

    # (1) The individual accessing their own PHI — right of access. (§164.524)
    if rc == "patient_self":
        return "permit"

    # (2) Another covered entity for treatment / payment / operations. (§164.506)
    if rc in ("covered_entity", "payer") and _PURPOSE_TREATMENT.search(purpose):
        return "permit"

    # (3) Judicial / litigation recipients: permitted ONLY with a verifiable
    #     court order or subpoena-with-assurances. Absent that signal, DENY.
    #     (§164.512(e)) — this is where LLMs over-trust; the gate does not.
    if rc == "judicial_legal":
        return "permit" if _PURPOSE_COURT_ORDER.search(purpose) else "prohibit"

    # (4) Law enforcement: permitted only for specific enumerated conditions
    #     (court order, mandatory report, required by law). Else DENY. (§164.512(f))
    if rc == "law_enforcement":
        return "permit" if (_PURPOSE_COURT_ORDER.search(purpose)
                            or _PURPOSE_PUBLIC_HEALTH.search(purpose)) else "prohibit"

    # (5) Government / oversight agencies: permitted for public-health or health
    #     oversight purposes; otherwise DENY. (§164.512(a),(b),(d))
    if rc == "government":
        return "permit" if _PURPOSE_PUBLIC_HEALTH.search(purpose) else "prohibit"

    # (6) Employers, media/public, family/representatives, and everyone else:
    #     no verifiable authorization present (consent_form is empty corpus-wide),
    #     so default-deny. (§164.508 requires authorization for these.)
    return "prohibit"


if __name__ == "__main__":
    import json
    from collections import Counter
    d = json.load(open("data/hipaa_flows.json", encoding="utf-8"))
    preds = [gate_decision(r) for r in d]
    print("gate decision distribution:", dict(Counter(preds)))
    print("recipient categories:", dict(Counter(recipient_category(r) for r in d)))
    print("covered senders:", sum(sender_is_covered(r) for r in d), "/", len(d))
