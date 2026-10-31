"""
Paper III — Controlled Information-Type Vocabulary (v1.2.0)

The shared vocabulary for document attribute inventories (Stage 1) and role
permission sets (Stage 2). Because the eventual fifth gate check is

    every information type in the document  ⊆  types the requester's role may receive

both sides of that subset test must be drawn from the *same* enumerated set.
This file is that set. It is versioned and additive-only: entries are never
renamed or removed in place, because a rename silently changes the meaning of
every stored inventory and every role permission set keyed against it.

Design constraints
------------------
1. SUPERSET OF THE LABEL FIELD. Every one of the 14 `core.Agent.AttributeType`
   constants appears here verbatim, so `label.pii_attributes` values are valid
   vocabulary members with no translation layer. Two corpus-observed types that
   AttributeType lacks (`name`, `job_title`) are added.
2. GROUNDED, NOT INVENTED. Every entry is attested in the Riverside corpus —
   either in an authored `pii_attributes` list or in a generation-time
   `attributes[].information_type`.
3. STABLE. VOCAB_VERSION is stamped into every artifact this package writes.

Deliberate exclusions
---------------------
`document_type` and `document_date` appear in the corpus's generation-time
`attributes` (4 and 2 instances) but are record metadata, not information types
about a person. They are excluded and mapped to None by `normalize_type()`.

Standalone `phone` and `email` are excluded. The corpus contains both, but every
occurrence is clinic switchboard/billing contact information (e.g.
"(217) 555-0100", "billing@riversidemedical.org") rather than subject PII;
subject-linked phone numbers occur only inside `emergency_contact` values. Adding
them would guarantee a "found but not authored" finding on nearly every document
for a type no label ever claims, which would inflate the Stage 1 reconciliation
with noise rather than signal. See REPORT.md, Limitations.

Exports
-------
VOCAB_VERSION            : str
INFORMATION_TYPES        : tuple[InformationType, ...]   — the enumerated vocabulary
VOCAB                    : dict[str, InformationType]
FAMILIES                 : dict[str, tuple[str, ...]]
PANOPTICON_CATEGORIES    : tuple[str, ...]               — the 33 PANORAMA-derived categories
PANOPTICON_TO_VOCAB      : dict[str, str | None]         — tagger category → vocabulary entry
UNDETECTABLE_BY_PANOPTICON : tuple[str, ...]             — vocabulary entries PANOPTICON cannot reach
UNDETECTABLE_BY_STAGE1     : tuple[str, ...]             — vocabulary entries this repo's tagger cannot reach
SUBJECT_LINKED_BY_DEFINITION : frozenset[str]            — entries always about the subject
normalize_type(raw)      : str | None

Version history
---------------
1.0.0  initial 16-entry vocabulary.
1.1.0  `emergency_contact` redefined as a subject attribute. No entry added,
       renamed, or removed, so every stored inventory and role permission set
       keyed against 1.0.0 remains valid.
1.2.0  `job_title` and `medical_license` definitions record ownership boundaries
       settled after the human audit pass. Again no entry added, renamed, or
       removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 1.1.0 — `emergency_contact` redefined as a subject attribute (the subject's
#         designation), not a third-party record. See SUBJECT_LINKED_BY_DEFINITION.
# 1.2.0 — `job_title` and `medical_license` definitions record the ownership
#         boundaries settled after the Stage 1c human pass: a staffing headcount
#         names no individual and is organisational; a Type 2 NPI belongs to the
#         organisation while a Type 1 NPI belongs to the clinician. Entry list
#         unchanged in both cases.
VOCAB_VERSION = "1.2.0"


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InformationType:
    """One enumerated information type."""

    name: str
    family: str
    definition: str
    # How reliably the Stage 1 tagger (stage1/tagger.py) can find this type in
    # free text: "high" = distinctive structural pattern; "medium" = depends on
    # a section heading or a gazetteer that will not generalize past this corpus;
    # "closed-world" = only findable via the fixed 24-agent registry.
    detectability: str
    # True for the AttributeType constants the CI gate's tier logic already
    # treats as heightened-sensitivity.
    extra_sensitive: bool = False
    examples: tuple[str, ...] = field(default_factory=tuple)


INFORMATION_TYPES: tuple[InformationType, ...] = (
    # -- Identity ------------------------------------------------------------
    InformationType(
        name="name",
        family="identity",
        definition="Personal name of a natural person (patient, employee, contractor, "
                   "or named provider).",
        detectability="closed-world",
        examples=("John Smith", "Dr. Aisha Patel"),
    ),
    InformationType(
        name="date_of_birth",
        family="identity",
        definition="A person's date of birth, in any format.",
        detectability="high",
        examples=("1968-03-14", "Date of Birth: March 14, 1968"),
    ),
    InformationType(
        name="ssn",
        family="identity",
        definition="Social Security Number, whole or partially masked.",
        detectability="high",
        examples=("XXX-XX-4821",),
    ),
    InformationType(
        name="home_address",
        family="identity",
        definition="Residential street address of a person. Excludes the clinic's own "
                   "premises address.",
        detectability="medium",
        examples=("412 Maple St, Springfield, IL 62701",),
    ),
    InformationType(
        name="emergency_contact",
        family="identity",
        definition="The subject's designated emergency or guardian contact — the "
                   "identity of the person the subject nominated, with or without a "
                   "phone number. This is an attribute OF THE SUBJECT: under HIPAA the "
                   "emergency contact recorded in a patient record forms part of the "
                   "designated record set, and is therefore PHI about the patient. Who "
                   "the subject designated is a relational fact about the subject, not "
                   "merely a record about the contact. Always subject-linked; see "
                   "SUBJECT_LINKED_BY_DEFINITION.",
        detectability="medium",
        examples=("Mary Smith (spouse) 555-0142",),
    ),

    # -- Clinical ------------------------------------------------------------
    InformationType(
        name="medical_diagnosis",
        family="clinical",
        definition="A current or working clinical diagnosis, stated in words or encoded "
                   "as a diagnostic code.",
        detectability="medium",
        examples=("Type 2 Diabetes Mellitus (E11.9)", "Chronic Kidney Disease, Stage 3"),
    ),
    InformationType(
        name="medical_medication",
        family="clinical",
        definition="A prescribed or administered drug, typically with dose and frequency.",
        detectability="high",
        examples=("Metformin 500 mg twice daily", "Lisinopril 10mg daily"),
    ),
    InformationType(
        name="medical_history",
        family="clinical",
        definition="Past conditions, procedures, or clinical events, as distinct from the "
                   "current presenting diagnosis.",
        detectability="medium",
        examples=("Hypertension diagnosed 2015", "Remote history of appendectomy (1984)"),
    ),
    InformationType(
        name="mental_health",
        family="clinical",
        definition="Psychiatric or substance-use diagnosis, assessment instrument score, "
                   "or treatment detail. The extra-sensitive subset of the clinical family.",
        detectability="medium",
        extra_sensitive=True,
        examples=("Opioid Use Disorder, moderate (F11.20)", "PHQ-9 score: 9"),
    ),

    # -- Financial -----------------------------------------------------------
    InformationType(
        name="billing_code",
        family="financial",
        definition="A procedure or diagnosis code used for billing — CPT, HCPCS, or ICD-10.",
        detectability="high",
        examples=("CPT 99213", "ICD-10 E11.9"),
    ),
    InformationType(
        name="insurance_info",
        family="financial",
        definition="Payer identity, plan type, and/or member, policy, or group identifier.",
        detectability="high",
        examples=("BlueCross PPO #BC-847261", "Medicare Part B #1EG4-TE5-MK72"),
    ),

    # -- Employment ----------------------------------------------------------
    InformationType(
        name="salary",
        family="employment",
        definition="An individual's compensation figure — annual salary, base pay, or "
                   "contractor hourly rate.",
        detectability="high",
        examples=("$195,000", "$88/hr"),
    ),
    InformationType(
        name="employment_contract",
        family="employment",
        definition="The existence, identifier, or terms of an employment agreement.",
        detectability="medium",
        examples=("Full-Time Physician Agreement, effective March 1, 2021", "EMP-2025-CHEN-001"),
    ),
    InformationType(
        name="contract_terms",
        family="employment",
        definition="Terms of a non-employee contractor engagement — scope, rate, restrictions.",
        detectability="medium",
        examples=("IT infrastructure support; $88/hr; no PHI access permitted",),
    ),
    InformationType(
        name="job_title",
        family="employment",
        definition="A person's occupational role or position within the organization. "
                   "OWNERSHIP BOUNDARY (v1.2.0): a title is subject- or third-party-"
                   "linked only where it is asserted OF AN IDENTIFIED INDIVIDUAL — "
                   "'Position: Staff Psychiatrist' on that clinician's own contract, or "
                   "'Attending Physician: Dr. Nguyen' naming a specific clinician. A "
                   "STAFFING HEADCOUNT ('2 RN, 1 Billing Specialist', 'Medical "
                   "Assistant: 1 per shift') names no individual and identifies no one; "
                   "it is a resource count rather than personal information about a "
                   "person, and is organizational.",
        detectability="medium",
        examples=("Billing Specialist", "Attending Psychiatrist"),
    ),
    InformationType(
        name="medical_license",
        family="employment",
        definition="A clinician credential identifier — state medical license, NPI, or DEA "
                   "registration number. OWNERSHIP BOUNDARY (v1.2.0): an NPI is "
                   "syntactically identical whether individual or organisational, so "
                   "ownership follows the entity the credential is asserted of. A Type 1 "
                   "NPI belongs to the individual clinician and is third-party on a "
                   "patient record (subject on that clinician's own employment record). "
                   "A Type 2 NPI belongs to the organisation — 'Facility NPI:', 'Group "
                   "NPI:', or an attribution block opened on the practice rather than a "
                   "person — and is organizational.",
        detectability="high",
        examples=("IL-MD-55432", "NPI: 1487320956", "DEA#: FE3291047"),
    ),
)

VOCAB: dict[str, InformationType] = {t.name: t for t in INFORMATION_TYPES}

FAMILIES: dict[str, tuple[str, ...]] = {
    fam: tuple(t.name for t in INFORMATION_TYPES if t.family == fam)
    for fam in ("identity", "clinical", "financial", "employment")
}

EXTRA_SENSITIVE_TYPES: frozenset[str] = frozenset(
    t.name for t in INFORMATION_TYPES if t.extra_sensitive
)


# ---------------------------------------------------------------------------
# Corpus metadata that is NOT an information type
# ---------------------------------------------------------------------------

# Present in the corpus's generation-time `attributes` but excluded from the
# vocabulary; normalize_type() maps these to None so they are dropped rather
# than silently counted as unauthored findings.
NON_INFORMATION_TYPES: frozenset[str] = frozenset({"document_type", "document_date"})


# ---------------------------------------------------------------------------
# Entries that are subject-linked by definition (v1.1.0)
# ---------------------------------------------------------------------------
# Some entries denote a RELATION the subject stands in rather than a fact about
# the person named in the value. For those, per-occurrence context cannot answer
# the linkage question correctly: the classifier sees "Mary Smith (spouse)" and
# correctly observes that the mention names someone other than the subject, but
# the information type recorded is the subject's DESIGNATION, which is theirs.
#
# `emergency_contact` is such an entry. Under HIPAA the emergency contact in a
# patient record forms part of the designated record set and is PHI about the
# patient. Stage 1b measured 21 of 22 occurrences as third_party on positional
# evidence; that evidence is right about the mention and wrong about the type.
#
# Detections of these types bypass positional classification and are always
# subject-linked. Note the consequence recorded in REPORT_1B.md: this makes the
# contact a SECOND data subject whose own privacy interest the architecture does
# not model.
SUBJECT_LINKED_BY_DEFINITION: frozenset[str] = frozenset({"emergency_contact"})


def normalize_type(raw: str | None) -> str | None:
    """
    Map a raw information-type string onto the controlled vocabulary.

    Returns None for record metadata (NON_INFORMATION_TYPES), for empty input,
    and for anything outside the vocabulary — callers are expected to count the
    Nones rather than let unknown types through silently.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    if key in NON_INFORMATION_TYPES:
        return None
    return key if key in VOCAB else None


# ---------------------------------------------------------------------------
# PANOPTICON (Paper I) reconciliation
# ---------------------------------------------------------------------------

# The union of the six PANORAMA-derived pools in
# PANOPTICON-DataGen/src/utils/pii_handler.py. Note that pii_handler.match_pii()
# is a closed-world *verifier* — it takes a dict of known ground-truth values and
# returns the subset present in the text. It has no open-text detection path, so
# these categories describe what it can *confirm*, not what it can *find*.
PANOPTICON_CATEGORIES: tuple[str, ...] = (
    "Address", "Age", "Allergies", "Annual Salary", "Birth City", "Birth Date",
    "Blood Type", "Children Count", "Credit Score", "Disability",
    "Driver's License", "Education Info", "Email Address",
    "Emergency Contact Name", "Emergency Contact Phone", "Employer",
    "Father's Name", "Finance Status", "First Name", "Gender", "Job Title",
    "Last Name", "Marital Status", "Mother's Name", "National ID", "Nationality",
    "Net Worth", "Passport Number", "Phone Number", "Social Media Handles",
    "Spouse Name", "Work Email", "Work Phone",
)

# PANOPTICON category -> clinic vocabulary entry, or None where the category has
# no referent in a clinic record.
PANOPTICON_TO_VOCAB: dict[str, str | None] = {
    "First Name":              "name",
    "Last Name":               "name",
    "Birth Date":              "date_of_birth",
    "Address":                 "home_address",
    "Annual Salary":           "salary",
    "Emergency Contact Name":  "emergency_contact",
    "Emergency Contact Phone": "emergency_contact",
    "Job Title":               "job_title",
    # PANORAMA's en_US "National ID" is SSN-shaped, so this is a genuine mapping,
    # but a weak one: match_pii compares National ID by exact alphanumeric token,
    # and every SSN in the Riverside corpus is masked ("XXX-XX-4821"), which no
    # PANORAMA profile value would ever equal.
    "National ID":             "ssn",

    # No clinic referent.
    "Age":                  None,
    "Allergies":            None,
    "Birth City":           None,
    "Blood Type":           None,
    "Children Count":       None,
    "Credit Score":         None,
    "Disability":           None,
    "Driver's License":     None,
    "Education Info":       None,
    "Email Address":        None,
    "Employer":             None,
    "Father's Name":        None,
    "Finance Status":       None,
    "Gender":               None,
    "Marital Status":       None,
    "Mother's Name":        None,
    "Nationality":          None,
    "Net Worth":            None,
    "Passport Number":      None,
    "Phone Number":         None,
    "Social Media Handles": None,
    "Spouse Name":          None,
    "Work Email":           None,
    "Work Phone":           None,
}

# Vocabulary entries no PANOPTICON category maps onto. These are the nine types
# that carry the Paper III argument: the clinical, coding, insurance, and
# contract families are absent from PANORAMA's consumer/social/government schema.
UNDETECTABLE_BY_PANOPTICON: tuple[str, ...] = tuple(
    t.name for t in INFORMATION_TYPES
    if t.name not in {v for v in PANOPTICON_TO_VOCAB.values() if v}
)

# Vocabulary entries the Stage 1 tagger does not attempt, or attempts only under
# a closed-world assumption. Kept explicit so the audit reports a known ceiling
# rather than discovering one.
UNDETECTABLE_BY_STAGE1: tuple[str, ...] = (
    # Detected only by matching the fixed 24-agent registry plus the provider
    # names attested in the corpus. Open-world personal-name detection is out of
    # scope for a regex tagger; a name outside the registry is a guaranteed miss.
    "name",
)


# ---------------------------------------------------------------------------
# Self-description, for stamping into artifacts
# ---------------------------------------------------------------------------

def vocabulary_manifest() -> dict:
    """The vocabulary as a serializable dict, for embedding in artifacts."""
    return {
        "vocab_version": VOCAB_VERSION,
        "size": len(INFORMATION_TYPES),
        "families": {k: list(v) for k, v in FAMILIES.items()},
        "types": [
            {
                "name": t.name,
                "family": t.family,
                "definition": t.definition,
                "detectability": t.detectability,
                "extra_sensitive": t.extra_sensitive,
                "examples": list(t.examples),
            }
            for t in INFORMATION_TYPES
        ],
        "non_information_types": sorted(NON_INFORMATION_TYPES),
        "subject_linked_by_definition": sorted(SUBJECT_LINKED_BY_DEFINITION),
        "panopticon": {
            "category_count": len(PANOPTICON_CATEGORIES),
            "categories": list(PANOPTICON_CATEGORIES),
            "mapping": dict(sorted(PANOPTICON_TO_VOCAB.items())),
            "undetectable_by_panopticon": list(UNDETECTABLE_BY_PANOPTICON),
        },
        "undetectable_by_stage1_tagger": list(UNDETECTABLE_BY_STAGE1),
    }


if __name__ == "__main__":
    import json

    mapped = {v for v in PANOPTICON_TO_VOCAB.values() if v}
    print(f"Controlled vocabulary v{VOCAB_VERSION} — {len(INFORMATION_TYPES)} types\n")
    for fam, names in FAMILIES.items():
        print(f"  {fam:<12} {', '.join(names)}")
    print()
    print(f"PANOPTICON categories            : {len(PANOPTICON_CATEGORIES)}")
    print(f"  mapping onto the vocabulary    : "
          f"{sum(1 for v in PANOPTICON_TO_VOCAB.values() if v)} categories "
          f"-> {len(mapped)} vocabulary entries")
    print(f"  with no clinic referent        : "
          f"{sum(1 for v in PANOPTICON_TO_VOCAB.values() if v is None)}")
    print(f"Vocabulary entries PANOPTICON cannot reach : "
          f"{len(UNDETECTABLE_BY_PANOPTICON)}/{len(INFORMATION_TYPES)}")
    for n in UNDETECTABLE_BY_PANOPTICON:
        print(f"    - {n}")
    print(f"Vocabulary entries the Stage 1 tagger cannot reach : "
          f"{len(UNDETECTABLE_BY_STAGE1)}/{len(INFORMATION_TYPES)}")
    for n in UNDETECTABLE_BY_STAGE1:
        print(f"    - {n}  ({VOCAB[n].detectability})")
