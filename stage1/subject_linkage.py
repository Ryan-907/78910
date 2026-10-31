"""
Paper III — Stage 1b: Per-Occurrence Subject-Linkage Classification

Contextual Integrity defines an information type relative to the DATA SUBJECT.
The Stage 2 check

    document.information_types  ⊆  role_permissions[requester.role]

therefore has to mean "what does this role learn *about the subject*". A
clinician's name in a signature block is not something that check should govern:
if a signature causes a document to carry `medical_license`, and Billing
Specialists may not receive `medical_license`, the gate refuses an insurance
claim because a doctor signed it. That is a bug wearing the costume of a privacy
control.

This module classifies each of the 1,392 detections in the v1.0.0 inventory as
`subject`, `third_party`, `organizational`, or `ambiguous`.

Per-occurrence, not per-value
-----------------------------
The unit is the OCCURRENCE. The same string classifies differently by context:
"Dr. Chen" in a signature block on a patient's note is third_party; "Dr. Chen" on
Dr. Chen's own credentialing file is subject. No roster of the subject's known
attribute values is consulted — that would answer a different question ("is this
value one the subject holds") than the one Stage 2 asks ("is this mention about
the subject").

The employment tier inverts, and it is handled as a class from the label rather
than case by case: when `subject_type` is `employee` or `contractor`, the
subject IS staff, so name / job_title / medical_license / salary are
subject-linked, and an incidental patient mention would be third_party.

Signals, in priority order
--------------------------
1. `field_label`   — the enclosing "Label: value" field. This is the strongest
                     signal in this corpus and the most defensible: "Patient
                     Name:", "Ordering Physician:", "Prepared by:" state
                     ownership outright. Ownership is expressed as a ROLE
                     (subject-of-record / clinician / institution) and only then
                     resolved against the document's `subject_type`, which is
                     what makes the employment inversion fall out automatically.
2. `region`        — letterhead, signature/attestation block, confidentiality
                     footer, or a named section (PATIENT INFORMATION,
                     PROVIDER ATTESTATION, …).
3. `name_match`    — for `name` only: compared against the document's subject.
                     A name that is not the subject's is third_party by
                     definition.
4. `type_default`  — family default conditioned on `subject_type`. Clinical and
                     financial content in a patient-subject document is about the
                     patient by construction; employment content in one is not.
5. otherwise       — `ambiguous`. This is a real answer and is never suppressed
                     to produce a cleaner split.

No language model is used anywhere. Deriving subject-linkage from an LLM would
put a model in the position of authoring an enforcement input, which is the thing
this thesis argues against.

Read-only. Nothing here modifies the corpus, the labels, the gate, the
vocabulary, or any Stage 1 artifact; outputs are new v1.1.0 files.

Usage
-----
    python -m stage1.subject_linkage

Outputs (stage1/artifacts/)
    linkage_v1.1.0.json            per-detection classification + aggregates
    linkage_v1.1.0.csv             one row per detection
    linkage_by_type_v1.1.0.csv     one row per information type
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from stage1.build_inventory import (
    ARTIFACT_DIR, JSON_PATH as INVENTORY_PATH, load_corpus, doc_id,
)
from stage1.vocabulary import (
    INFORMATION_TYPES, VOCAB, VOCAB_VERSION, SUBJECT_LINKED_BY_DEFINITION,
)

# 1.2.0 — three defects found by the human audit pass (see REPORT_1B.md 1.5):
#         the organisation masthead conferred institutional ownership on a whole
#         document; letterhead detection failed on documents opening with a rule
#         line; staffing headcounts were classified third_party.
LINKAGE_VERSION = "1.2.0"

OUT_JSON    = ARTIFACT_DIR / f"linkage_v{LINKAGE_VERSION}.json"
OUT_CSV     = ARTIFACT_DIR / f"linkage_v{LINKAGE_VERSION}.csv"
OUT_BY_TYPE = ARTIFACT_DIR / f"linkage_by_type_v{LINKAGE_VERSION}.csv"

TYPE_NAMES = [t.name for t in INFORMATION_TYPES]

# Classification classes
SUBJECT      = "subject"
THIRD_PARTY  = "third_party"
ORGANIZATIONAL = "organizational"
AMBIGUOUS    = "ambiguous"

# Ownership roles, resolved against subject_type afterwards.
OWNER_SUBJECT_OF_RECORD = "subject_of_record"  # the person the document is about
OWNER_PATIENT           = "patient"            # explicitly a patient
OWNER_STAFF             = "staff"              # a clinician / employee, as such
OWNER_OTHER_PERSON      = "other_person"       # named third party (kin, guarantor)
OWNER_INSTITUTION       = "institution"


# ---------------------------------------------------------------------------
# Field-label ownership table
# ---------------------------------------------------------------------------
# Built from the labels actually attested in the corpus (every label occurring
# 3+ times was enumerated and assigned by hand). Keys are casefolded and stripped
# of trailing punctuation. A label absent from this table contributes no signal
# rather than a guessed one.

FIELD_LABEL_OWNER: dict[str, str] = {}


def _own(owner: str, *labels: str) -> None:
    for l in labels:
        FIELD_LABEL_OWNER[l.casefold()] = owner


# -- the person the record is about -----------------------------------------
_own(OWNER_SUBJECT_OF_RECORD,
     "name", "full name", "patient name", "employee name", "contractor name",
     "member", "subscriber", "subscriber name", "patient", "employee",
     "contractor", "date of birth", "birth date", "dob", "d.o.b.",
     "ssn", "ssn (last 4)", "ssn (last4)", "ssn (partial)", "social security",
     "social security number", "address", "home address", "mailing address",
     "patient address", "residence",
     "insurance", "insurer", "primary insurer", "insurance carrier", "plan",
     "member id", "policy", "policy number", "policy #", "group #", "group number",
     "account #", "account number", "claim #", "claim number",
     "diagnosis", "diagnoses", "primary diagnosis", "working diagnosis",
     "diagnosis code", "icd-10 code", "icd10 code", "assessment", "impression",
     "clinical impression", "indication", "reason for visit",
     "billing code", "billing codes", "billing code(s)", "cpt code", "cpt code(s)",
     "procedure code", "service code",
     "current medication", "current medications", "medication", "medications",
     "requested medication", "sig", "dispense", "refills", "qty",
     "allergies", "relevant history", "medical history", "past medical history",
     "history", "clinical summary",
     "annual salary", "annual base salary", "base salary", "salary",
     "compensation", "base pay", "pay frequency", "pay per period",
     "hourly rate", "rate of pay",
     "position", "role", "title", "job title", "department", "specialty",
     "employment type", "employment contract", "classification",
     "review period", "overall rating",
     "total billed", "patient responsibility", "patient responsibility (est.)",
     "amount due", "balance",
     )

# -- explicitly a clinician, in their professional capacity ------------------
_own(OWNER_STAFF,
     "provider", "providers", "attending provider", "attending physician",
     "prescribing physician", "prescriber", "ordering physician",
     "ordering provider", "rendering provider", "referring physician",
     "referring provider", "interpreting radiologist", "radiologist",
     "supervising physician", "physician", "clinician", "authorized by",
     "authorized signature", "signature", "signed", "prepared by", "verified by",
     "reviewed by", "completed by", "submitted by", "approved by",
     "attending", "consultant", "primary care physician", "pcp",
     "case manager", "coordinator",
     # added after inspecting the prose-default residue: all are explicit
     # attribution labels that were simply not enumerated on the first pass
     "discharging physician", "prescribing provider", "physician signature",
     "provider signature", "clinician signature", "verification completed by",
     "attending clinician", "treating physician", "consulting physician",
     "physician on duty", "performed by", "dictated by", "transcribed by",
     "evaluator", "reviewer", "supervisor", "nurse", "nurse/ma", "nurse / ma",
     "medical assistant", "rendering provider npi", "billing provider",
     )

# -- a named non-clinician third party ---------------------------------------
_own(OWNER_OTHER_PERSON,
     "emergency contact", "emergency contact name", "emergency contact phone",
     "next of kin", "guardian", "legal guardian", "guarantor", "responsible party",
     "spouse", "parent",
     )

# -- the institution ----------------------------------------------------------
_own(OWNER_INSTITUTION,
     "facility", "facility name", "facility npi", "facility tax id",
     "location", "clinic", "practice", "site", "place of service",
     "phone", "fax", "tax id", "ein", "office", "department phone",
     "billing office", "remit to", "clinic address", "group npi",
     )

# Credential fields are deliberately NOT given a fixed owner. They attach to
# whichever person the surrounding block is about, which is exactly the inversion
# this stage measures: on a patient's note they belong to the signing clinician,
# on a credentialing file they belong to the subject. Instead of hard-coding an
# answer they INHERIT from the block they sit in (see Segments.provider_block).
CREDENTIAL_LABELS: frozenset[str] = frozenset({
    "npi", "npi #", "npi number", "dea", "dea #", "dea number", "dea registration",
    "medical license", "medical license no.", "medical license no", "medical license #",
    "license", "license no.", "license no", "license #", "state license",
    "specialty", "specialties", "credentials", "date/time", "signature block",
})


# ---------------------------------------------------------------------------
# Region segmentation
# ---------------------------------------------------------------------------

# A provider block is a tight run of credential fields, not an open-ended tail.
MAX_PROVIDER_BLOCK_LINES = 6

_RULE_LINE = re.compile(r"^[ \t]*[─—–=_*\-]{6,}[ \t]*$")
_SECTION_HEADER = re.compile(r"^[ \t]*([A-Z][A-Z0-9 &/\-'(),\.]{3,60})[ \t]*:?[ \t]*$")
_TITLE_BLOCK = re.compile(r"^[ \t]*([A-Z][A-Za-z]+(?:[ \t][A-Z][A-Za-z]+){0,4})[ \t]*:[ \t]*$")

# A section header naming whose information the section carries.
SECTION_OWNER: dict[str, str] = {}


def _sown(owner: str, *headers: str) -> None:
    for h in headers:
        SECTION_OWNER[h.casefold()] = owner


_sown(OWNER_SUBJECT_OF_RECORD,
      "patient information", "patient demographics", "patient details",
      "demographics", "employee details", "employee information",
      "contractor information", "member information", "subscriber information",
      "insurance information", "insurance plan", "compensation", "compensation summary",
      "engagement details", "assessment", "plan", "diagnosis", "diagnoses",
      "active diagnoses", "diagnosis codes", "subjective",
      "objective", "vital signs", "physical examination", "medical history",
      "past medical history", "pertinent medical history", "current medications",
      "active medications", "current medication", "medication requested",
      "reason for visit", "clinical summary", "hospital course", "discharge diagnosis",
      "service detail", "charges summary", "charge summary", "laboratory results",
      "findings", "impression", "history of present illness", "review period",
      "performance summary", "employment terms", "position details",
      # attested in the corpus at 3+ occurrences and unambiguously about the
      # person the record is kept on
      "relevant medical history", "relevant history", "clinical indication",
      "medical / psychiatric history", "medical/psychiatric history",
      "mental health assessment", "psychiatric assessment", "rx",
      "pertinent obstetric history", "clinical correlation", "claim details",
      "insurance claim form", "justification", "indication",
      "prescription on file", "current medication on file", "prescription noted",
      "current medications noted", "clinical note",
      )
_sown(OWNER_STAFF,
      "provider attestation", "physician attestation", "attestation",
      "authorization", "signature", "signatures", "acknowledgment",
      "acknowledgement", "certification", "provider information",
      "prescriber information", "ordering provider", "ordering physician",
      "attending physician", "attending provider", "discharging physician",
      "prescribing physician", "referring physician", "interpreting radiologist",
      "credentials", "provider details",
      )
# Family history describes relatives, not the subject. Kept explicit rather than
# folded into the subject-owned list, because it is a genuine CI edge: the fact
# that the subject HAS this family history is about them, while the medical
# content is about someone else. Classified third_party and flagged in the report.
_sown(OWNER_OTHER_PERSON, "family history", "family medical history")
_sown(OWNER_INSTITUTION,
      "confidentiality notice", "confidentiality",
      "notice", "disclaimer", "contact information", "billing office",
      )

# An organisation-name line is a MASTHEAD, not an ownership declaration. It names
# the document's issuer, not the subject of the content beneath it.
#
# This was the dominant defect in v1.1.0. "RIVERSIDE MEDICAL CLINIC" matched the
# ALL-CAPS section-header pattern and was mapped to OWNER_INSTITUTION, and because
# section() returns the nearest PRECEDING header with no scope limit, in any
# document where no later header intervened the masthead governed the entire body.
# Every clinical detection beneath it resolved to institutional ownership and was
# filtered out of the inventory: HIV and AIDS on doc_008, suicidal ideation and
# PHQ-9 scores across six clinical_sensitive documents. 56 of 66 silent releases.
#
# The guard is a general property of the header, not a blocklisted string: any
# header naming an organisation confers no ownership on what follows.
_MASTHEAD = re.compile(
    r"(?i)\b(clinic|hospital|health\s+(?:system|center|centre|network)"
    r"|medical\s+(?:center|centre|group|associates|practice)"
    r"|imaging\s+(?:center|centre|associates)|radiology\s+associates"
    r"|associates|partners|foundation|institute"
    r"|LLC|L\.L\.C\.|Inc\.?|LLP|P\.?C\.)\b")


def is_masthead(header: str) -> bool:
    """True if a section header names an organisation rather than a content section."""
    return bool(_MASTHEAD.search(header))


# A staffing HEADCOUNT names no individual. "2 RN, 1 Billing Specialist" and
# "Medical Assistant: 1 per shift" are resource counts on a schedule or agenda --
# they identify nobody, so they are not personal information about a person and
# resolve to `organizational`. This does NOT weaken the rule for named
# individuals: a staff member's own attribute remains `third_party` (or `subject`
# on an employment-tier record). The distinction is whether an individual is
# identified, not whether the string denotes a role.
#
# Ruled in Stage 1d after the human pass classified these as organizational; see
# vocabulary.job_title for the recorded boundary.
_QUANTITY_BEFORE = re.compile(r"(?i)(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:[A-Za-z]+\s+){0,2}$")
_QUANTITY_AFTER  = re.compile(r"(?i)^[:\s]*(?:\s*[-–]\s*)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b")


def _line_names_a_person(line: str) -> bool:
    """
    True if the line identifies an individual, in which case a role appearing on it
    is that person's attribute rather than a headcount.

    Reuses the tagger's closed-world registry (the 24 agents plus a titled-provider
    pattern) rather than duplicating it, so the two modules agree on what counts as
    a name. Imported lazily to keep module import side-effect free.
    """
    from stage1.tagger import _name_pattern
    return bool(_name_pattern().search(line))


def looks_like_headcount(line: str, value: str) -> bool:
    """True if `value` sits in `line` as a counted quantity rather than a person's role."""
    idx = line.find(value)
    if idx < 0:
        return False
    before, after = line[:idx], line[idx + len(value):]
    return bool(_QUANTITY_BEFORE.search(before) or _QUANTITY_AFTER.match(after))

# Cues that open a signature / attestation block running to end of document.
_SIGNATURE_CUE = re.compile(
    r"(?im)^[ \t]*(?:sincerely|respectfully(?:\s+submitted)?|signature|signed"
    r"|authorized\s+signature|provider\s+attestation|attestation"
    r"|electronically\s+signed|by\s+signing\s+below|acknowledg(?:e)?ment)\b"
    r"|^[ \t]*_{6,}"
)
_FOOTER_CUE = re.compile(r"(?im)^[ \t]*(?:confidentiality\s+notice|confidentiality)\b")


class Segments:
    """Region lookup for one document."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.lines: list[tuple[int, int, str]] = []
        pos = 0
        for line in text.splitlines(keepends=True):
            self.lines.append((pos, pos + len(line), line.rstrip("\n")))
            pos += len(line)

        self.letterhead_end = self._find_letterhead_end()
        self.signature_start = self._find_signature_start()
        self.footer_start = self._find_footer_start()
        self._headers = self._find_headers()
        self._provider_spans = self._find_provider_blocks()

    # -- construction --------------------------------------------------------

    def _find_letterhead_end(self) -> int:
        """
        The letterhead is the leading block: organization name, premises address,
        switchboard. It ends at the first rule line or the first blank line that
        follows a non-empty line, whichever comes first.
        """
        seen_text = False
        for start, end, line in self.lines:
            stripped = line.strip()
            # Leading decoration is not the end of the letterhead -- it is before
            # the letterhead has begun. v1.1.0 returned 0 for any document opening
            # with a rule line (doc_008 among them), so those documents had no
            # letterhead region at all and the masthead fell into `body`.
            if not seen_text and (not stripped or _RULE_LINE.match(line)):
                continue
            if _RULE_LINE.match(line):
                return start
            if not stripped:
                if seen_text:
                    return start
                continue
            seen_text = True
        return 0

    def _find_signature_start(self) -> int:
        """Offset where a trailing signature/attestation block begins, or -1."""
        best = -1
        for start, end, line in self.lines:
            if _SIGNATURE_CUE.match(line):
                best = start
        # Only treat it as a signature block if it is in the last third of the
        # document; "Acknowledgment" sections mid-document are not signatures.
        if best >= 0 and best >= len(self.text) * 0.55:
            return best
        return -1

    def _find_footer_start(self) -> int:
        m = None
        for cand in _FOOTER_CUE.finditer(self.text):
            m = cand
        if m and m.start() >= len(self.text) * 0.5:
            return m.start()
        return -1

    def _find_headers(self) -> list[tuple[int, str]]:
        """(offset, casefolded header) for each recognized section header."""
        out: list[tuple[int, str]] = []
        for i, (start, end, line) in enumerate(self.lines):
            stripped = line.strip()
            if not stripped or _RULE_LINE.match(line):
                continue
            m = _SECTION_HEADER.match(line)
            if m:
                out.append((start, m.group(1).strip().casefold()))
                continue
            # Title-case block header terminated by a colon with no value, e.g.
            # "Employee Details:" / "Compensation Summary:"
            m = _TITLE_BLOCK.match(line)
            if m:
                out.append((start, m.group(1).strip().casefold()))
        return out

    def _find_provider_blocks(self) -> list[tuple[int, int]]:
        """
        Spans of a clinician-attribution block.

        Corpus documents attribute credentials positionally:

            PRESCRIBER INFORMATION
            Physician: Dr. Patricia Nguyen, MD     <- staff-owned label opens the block
            Medical License No.: IL-MD-082947      <- inherits the clinician
            DEA Number: BN4827163                  <- inherits
            NPI: 1234567890                        <- inherits
                                                   <- blank line closes the block

        Without this, `NPI:` and `Medical License:` fall through to a type default
        and read as unstructured, which understates how separable third-party
        credentials actually are. A block runs from a staff-owned label (or a
        staff-owned section header) until a blank line, a rule line, a new section
        header, or a subject-owned label.
        """
        spans: list[tuple[int, int]] = []
        open_at: int | None = None
        open_lines = 0

        for start, end, line in self.lines:
            stripped = line.strip()

            # Terminators
            if not stripped or _RULE_LINE.match(line):
                if open_at is not None:
                    spans.append((open_at, start))
                    open_at = None
                continue

            m = re.match(r"^[ \t]*([A-Za-z][A-Za-z0-9 /()'\-\.#]{1,40}?)[ \t]*:", line)
            label = m.group(1).strip().rstrip(".").casefold() if m else None
            header = _SECTION_HEADER.match(line)
            header_txt = header.group(1).strip().casefold() if header else None

            if open_at is not None:
                # A block continues ONLY through credential fields, further staff
                # labels, and unlabeled continuation lines. Anything else closes
                # it. An earlier version closed only on a subject-owned label,
                # which let "Ordering Physician:" run through "Exam Type:" and
                # swallow the patient's billing code two lines later.
                continues = (
                    open_lines < MAX_PROVIDER_BLOCK_LINES
                    and (label is None
                         or label in CREDENTIAL_LABELS
                         or FIELD_LABEL_OWNER.get(label) == OWNER_STAFF)
                    and not (header_txt and SECTION_OWNER.get(header_txt) != OWNER_STAFF)
                )
                if continues:
                    open_lines += 1
                    continue
                spans.append((open_at, start))
                open_at = None

            # Openers
            if label and FIELD_LABEL_OWNER.get(label) == OWNER_STAFF:
                open_at, open_lines = start, 1
            elif header_txt and SECTION_OWNER.get(header_txt) == OWNER_STAFF:
                open_at, open_lines = start, 1

        if open_at is not None:
            spans.append((open_at, len(self.text)))
        return spans

    # -- queries -------------------------------------------------------------

    def letterhead_is_masthead(self) -> bool:
        """
        True if the leading block is an organisation identity block.

        `region == letterhead -> organizational` rests on the leading block being
        the clinic's own masthead: name, premises address, switchboard. Some
        documents instead open with a statutory confidentiality banner
        ("CONFIDENTIALITY NOTICE - 42 CFR PART 2 - SUBSTANCE ABUSE TREATMENT
        RECORDS"), which is about the patient's record rather than the institution,
        and whose content must not be filtered out of the inventory on the strength
        of its position.
        """
        head = self.text[:self.letterhead_end]
        return bool(_MASTHEAD.search(head))

    def in_provider_block(self, offset: int) -> bool:
        return any(s <= offset < e for s, e in self._provider_spans)

    def provider_block_is_organizational(self, offset: int) -> bool:
        """
        True if the attribution block containing `offset` was opened on an
        organisation rather than a person.

        NPI numbers are syntactically identical whether individual (Type 1) or
        organisational (Type 2), so the only available evidence is who the block
        names. Where it names the clinic, the credentials beneath it are the
        clinic's. Where it names a clinician, they are that clinician's.
        """
        for start, end in self._provider_spans:
            if start <= offset < end:
                opener = self.text[start:end].splitlines()[0] if self.text[start:end] else ""
                value = opener.split(":", 1)[1] if ":" in opener else opener
                return bool(_MASTHEAD.search(value)) and not _line_names_a_person(value)
        return False

    def region(self, offset: int) -> str:
        if offset < self.letterhead_end:
            return "letterhead"
        if self.footer_start >= 0 and offset >= self.footer_start:
            return "footer"
        if self.signature_start >= 0 and offset >= self.signature_start:
            return "signature"
        return "body"

    def section(self, offset: int) -> str | None:
        """Casefolded text of the nearest preceding section header."""
        found = None
        for start, header in self._headers:
            if start <= offset:
                found = header
            else:
                break
        return found

    def line_at(self, offset: int) -> tuple[int, str]:
        for start, end, line in self.lines:
            if start <= offset < end:
                return start, line
        return 0, ""

    def field_label(self, offset: int) -> tuple[str | None, bool]:
        """
        The "Label:" of the field containing `offset`, and whether the detection
        sits ON the label rather than in its value.

        Both positions carry ownership information. A `job_title` detection whose
        span IS the text "ATTENDING PHYSICIAN" in "ATTENDING PHYSICIAN: Dr. Nguyen"
        names a clinician's role just as surely as the value does. Treating the
        on-label case as "no signal" previously pushed 35 detections into the
        type-default bucket and made the corpus look less structured than it is.
        """
        line_start, line = self.line_at(offset)
        m = re.match(r"^[ \t]*([A-Za-z][A-Za-z0-9 /()'\-\.#]{1,40}?)[ \t]*:[ \t]*", line)
        if not m:
            return None, False
        label = m.group(1).strip().rstrip(".").casefold()
        on_label = (offset - line_start) < m.end(1)
        return label, on_label


# ---------------------------------------------------------------------------
# Owner -> class resolution
# ---------------------------------------------------------------------------

# Which vocabulary types belong to which family, for the type-default rule.
CLINICAL   = {"medical_diagnosis", "medical_medication", "medical_history", "mental_health"}
FINANCIAL  = {"billing_code", "insurance_info"}
EMPLOYMENT = {"salary", "employment_contract", "contract_terms", "job_title", "medical_license"}
IDENTITY   = {"name", "date_of_birth", "ssn", "home_address", "emergency_contact"}

STAFF_SUBJECT_TYPES = {"employee", "contractor"}


def resolve_owner_to_class(owner: str, subject_type: str) -> str:
    """
    Map an ownership role onto a classification, given who the document is about.

    This is where the employment inversion happens: OWNER_STAFF resolves to
    `subject` when the document's subject IS staff, and to `third_party` when the
    subject is a patient.
    """
    if owner == OWNER_INSTITUTION:
        return ORGANIZATIONAL
    if owner == OWNER_OTHER_PERSON:
        return THIRD_PARTY
    if owner == OWNER_SUBJECT_OF_RECORD:
        # An organization-level document has no individual subject, so a
        # "subject-of-record" field cannot be about anyone in particular.
        return SUBJECT if subject_type != "organization" else THIRD_PARTY
    if owner == OWNER_PATIENT:
        return SUBJECT if subject_type == "patient" else THIRD_PARTY
    if owner == OWNER_STAFF:
        return SUBJECT if subject_type in STAFF_SUBJECT_TYPES else THIRD_PARTY
    return AMBIGUOUS


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

_TITLES = re.compile(r"^(?:dr\.?|doctor|mr\.?|mrs\.?|ms\.?|nurse|prof\.?)\s+", re.I)
_SUFFIX = re.compile(r",?\s*(?:m\.?d\.?|d\.?o\.?|r\.?n\.?|n\.?p\.?|p\.?a\.?|ph\.?d\.?"
                     r"|lcsw|licsw|msw|rd|cma)\.?$", re.I)


def normalize_name(n: str | None) -> str:
    if not n:
        return ""
    s = _SUFFIX.sub("", n.strip())
    s = _TITLES.sub("", s)
    return re.sub(r"[^a-z ]", "", s.casefold()).strip()


def name_matches_subject(value: str, subject_name: str | None) -> bool:
    """True if this name mention refers to the document's subject."""
    if not subject_name:
        return False
    a, b = normalize_name(value), normalize_name(subject_name)
    if not a or not b:
        return False
    if a == b:
        return True
    # Surname-only mention ("Mr. Lee presented…") where the surname is unique to
    # the subject within the document.
    a_parts, b_parts = a.split(), b.split()
    if len(a_parts) == 1 and a_parts[0] == b_parts[-1]:
        return True
    return False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_detection(det: dict, seg: Segments, subject_type: str,
                       subject_name: str | None) -> tuple[str, str, dict]:
    """
    Returns (classification, signal, evidence).

    `signal` records WHICH rule decided it, so §3's structural-vs-prose split is a
    measurement rather than an assertion.
    """
    offset = det["start"]
    t = det["type"]
    region = seg.region(offset)
    label, on_label = seg.field_label(offset)
    section = seg.section(offset)
    in_provider = seg.in_provider_block(offset)
    ev = {"region": region, "field_label": label, "section": section,
          "on_label": on_label, "provider_block": in_provider}

    # --- 0. subject-linked by definition (vocabulary v1.1.0) ----------------
    # The entry denotes a relation the subject stands in, so the identity of the
    # person named in the value does not decide the question. Placed ahead of
    # every positional signal because positional evidence is right about the
    # mention and wrong about the type.
    if t in SUBJECT_LINKED_BY_DEFINITION:
        return ((SUBJECT if subject_type != "organization" else THIRD_PARTY),
                "vocabulary_definition", ev)

    # --- 1. name: decided by identity comparison, not position --------------
    if t == "name":
        if subject_type == "organization":
            return THIRD_PARTY, "name_match", ev
        if name_matches_subject(det["value"], subject_name):
            return SUBJECT, "name_match", ev
        return THIRD_PARTY, "name_match", ev

    # --- 1b. staffing headcount: names no individual ------------------------
    if t == "job_title":
        _ls, _line = seg.line_at(offset)
        if looks_like_headcount(_line, det["value"]) and not _line_names_a_person(_line):
            return ORGANIZATIONAL, "headcount", ev

    # --- 2. field label: the strongest and most defensible signal -----------
    if label:
        owner = FIELD_LABEL_OWNER.get(label)
        if owner:
            return (resolve_owner_to_class(owner, subject_type),
                    "field_label_self" if on_label else "field_label", ev)
        # A credential field inherits the person its block is about.
        if label in CREDENTIAL_LABELS and in_provider:
            return resolve_owner_to_class(OWNER_STAFF, subject_type), "provider_block", ev

    # --- 2b. any detection inside an attribution block ----------------------
    # A block opened on an ORGANISATION rather than a person carries that
    # organisation's credentials: "Provider: Riverside Medical Clinic / Rendering
    # Provider NPI: ..." is a Type 2 (organisational) NPI, not a clinician's Type 1.
    if in_provider:
        if seg.provider_block_is_organizational(offset):
            return ORGANIZATIONAL, "provider_block_org", ev
        return resolve_owner_to_class(OWNER_STAFF, subject_type), "provider_block", ev

    # --- 3. region ----------------------------------------------------------
    if region == "letterhead" and seg.letterhead_is_masthead():
        # The leading block is the institution's own identity.
        return ORGANIZATIONAL, "region", ev
    if region == "footer":
        # Statutory confidentiality boilerplate is about the document, not a
        # person. It is the main source of `mental_health` category markers.
        return ORGANIZATIONAL, "region", ev
    if region == "signature":
        return (SUBJECT if subject_type in STAFF_SUBJECT_TYPES else THIRD_PARTY), "region", ev

    # --- 4. section header --------------------------------------------------
    if section and not is_masthead(section):
        owner = SECTION_OWNER.get(section)
        if owner:
            return resolve_owner_to_class(owner, subject_type), "section", ev

    # --- 5. family default, conditioned on who the document is about --------
    if subject_type == "patient":
        if t in CLINICAL or t in FINANCIAL:
            # A patient record's clinical and billing content is about the patient
            # by construction. This is the single largest default and is stated
            # plainly rather than hidden.
            return SUBJECT, "type_default", ev
        if t in EMPLOYMENT:
            # A patient has no salary, job title, or medical licence in their own
            # clinical record; these come from provider and credential strings.
            return THIRD_PARTY, "type_default", ev
        if t in IDENTITY:
            return SUBJECT, "type_default", ev

    if subject_type in STAFF_SUBJECT_TYPES:
        if t in EMPLOYMENT or t in IDENTITY:
            return SUBJECT, "type_default", ev
        if t in CLINICAL:
            # On an HR or credentialing record a clinical term is usually the
            # subject's specialty rather than a finding about them. Genuinely
            # undecidable without reading the sentence.
            return AMBIGUOUS, "unresolved", ev
        if t in FINANCIAL:
            return AMBIGUOUS, "unresolved", ev

    if subject_type == "organization":
        # No individual subject exists, so nothing can be subject-linked.
        if t in EMPLOYMENT or t in IDENTITY or t in CLINICAL or t in FINANCIAL:
            return THIRD_PARTY, "type_default", ev

    return AMBIGUOUS, "unresolved", ev


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

# Three buckets, not two. `name_match` is decisive but is an identity comparison
# against the label's subject rather than a positional cue, so folding it into
# either "structural" or "prose" would misdescribe it.
STRUCTURAL_SIGNALS = {"field_label", "field_label_self", "provider_block",
                      "provider_block_org", "region", "section", "headcount"}
IDENTITY_SIGNALS   = {"name_match"}
# Decided by the vocabulary rather than by anything in the document.
DEFINITION_SIGNALS = {"vocabulary_definition"}
PROSE_SIGNALS      = {"type_default", "unresolved"}


def run() -> dict:
    if not INVENTORY_PATH.exists():
        raise SystemExit("Run `python -m stage1.build_inventory` first.")
    inv = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    records, corpus_hash = load_corpus()
    if corpus_hash != inv["source"]["sha256"]:
        raise SystemExit("Corpus changed since the inventory was built — rebuild it.")

    contents = {doc_id(i): (r.get("content") or "") for i, r in enumerate(records)}
    authored = {doc_id(i): set(r.get("pii_attributes") or []) for i, r in enumerate(records)}

    rows: list[dict] = []
    for d in inv["documents"]:
        did = d["doc_id"]
        seg = Segments(contents[did])
        st = d["subject_type"]
        sn = d.get("subject_name")
        for t in sorted(d["detections"]):
            for det in d["detections"][t]:
                cls, signal, ev = classify_detection(det, seg, st, sn)
                rows.append({
                    "doc_id":            did,
                    "document_type":     d["document_type"],
                    "sensitivity_tier":  d["sensitivity_tier"],
                    "subject_type":      st,
                    "subject_name":      sn,
                    "information_type":  t,
                    "value":             det["value"],
                    "rule":              det["rule"],
                    "start":             det["start"],
                    "classification":    cls,
                    "signal":            signal,
                    "structural":        signal in STRUCTURAL_SIGNALS,
                    "identity_based":    signal in IDENTITY_SIGNALS,
                    "region":            ev["region"],
                    "field_label":       ev["field_label"],
                    "section":           ev["section"],
                    "provider_block":    ev["provider_block"],
                    # Was this (doc, type) pair one of the 520 found-but-not-authored?
                    "found_not_authored": t not in authored[did],
                })

    return {"rows": rows, "corpus_sha256": corpus_hash}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _subset_split(subset: list[dict]) -> dict:
    """Structural / identity / prose breakdown for a subset of detections."""
    n = len(subset)
    st = sum(1 for r in subset if r["structural"])
    idn = sum(1 for r in subset if r["identity_based"])
    pr = n - st - idn
    return {
        "n": n, "structural": st, "identity": idn, "prose": pr,
        "pct_structural": round(st / n, 4) if n else None,
        "pct_identity":   round(idn / n, 4) if n else None,
        "pct_prose":      round(pr / n, 4) if n else None,
        "pct_separable":  round((st + idn) / n, 4) if n else None,
    }


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    overall = Counter(r["classification"] for r in rows)

    def split(subset: list[dict]) -> dict:
        c = Counter(r["classification"] for r in subset)
        tot = len(subset)
        return {
            "n": tot,
            **{k: c.get(k, 0) for k in (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS)},
            "pct_subject": round(c.get(SUBJECT, 0) / tot, 4) if tot else None,
            "pct_third_party": round(c.get(THIRD_PARTY, 0) / tot, 4) if tot else None,
        }

    by_type = {t: split([r for r in rows if r["information_type"] == t]) for t in TYPE_NAMES}
    by_tier = {k: split([r for r in rows if r["sensitivity_tier"] == k])
               for k in sorted({r["sensitivity_tier"] for r in rows})}
    by_stype = {k: split([r for r in rows if r["subject_type"] == k])
                for k in sorted({r["subject_type"] for r in rows})}

    # Signal provenance / structural analysis
    by_signal = Counter(r["signal"] for r in rows)
    non_subject = [r for r in rows if r["classification"] == THIRD_PARTY]
    ns_structural = sum(1 for r in non_subject if r["structural"])
    ns_identity   = sum(1 for r in non_subject if r["identity_based"])
    ns_prose      = sum(1 for r in non_subject
                        if not r["structural"] and not r["identity_based"])
    ns_region = Counter(r["region"] for r in non_subject)
    ns_signal = Counter(r["signal"] for r in non_subject)

    # The 520 found-but-not-authored pairs, rolled up from detections.
    fna_rows = [r for r in rows if r["found_not_authored"]]
    fna_pairs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in fna_rows:
        fna_pairs[(r["doc_id"], r["information_type"])].append(r)

    # A pair counts as subject-linked if ANY of its occurrences is subject-linked:
    # the future check governs whether the document carries the type about the
    # subject at all, so one subject-linked occurrence is enough to make it count.
    pair_class: dict[tuple[str, str], str] = {}
    for key, occ in fna_pairs.items():
        classes = {o["classification"] for o in occ}
        if SUBJECT in classes:
            pair_class[key] = SUBJECT
        elif AMBIGUOUS in classes:
            pair_class[key] = AMBIGUOUS
        elif THIRD_PARTY in classes:
            pair_class[key] = THIRD_PARTY
        else:
            pair_class[key] = ORGANIZATIONAL

    fna_summary = Counter(pair_class.values())
    fna_by_type: dict[str, Counter] = defaultdict(Counter)
    for (did, t), c in pair_class.items():
        fna_by_type[t][c] += 1

    return {
        "detections": n,
        "overall": {
            **{k: overall.get(k, 0) for k in (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS)},
            "pct": {k: round(overall.get(k, 0) / n, 4)
                    for k in (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS)},
        },
        "by_information_type":  by_type,
        "by_sensitivity_tier":  by_tier,
        "by_subject_type":      by_stype,
        "signal_provenance":    dict(by_signal.most_common()),
        "structural_analysis": {
            "third_party_detections": len(non_subject),
            "resolved_structurally":  ns_structural,
            "resolved_by_identity":   ns_identity,
            "resolved_in_prose":      ns_prose,
            "pct_structural": round(ns_structural / len(non_subject), 4) if non_subject else None,
            "pct_identity":   round(ns_identity / len(non_subject), 4) if non_subject else None,
            "pct_prose":      round(ns_prose / len(non_subject), 4) if non_subject else None,
            "by_region": dict(ns_region.most_common()),
            "by_signal": dict(ns_signal.most_common()),
            # The split that governs the Stage 2 decision. On an
            # organization-subject document no individual subject exists, so
            # every person-attribute is third_party by definition and needs no
            # separation rule. The question is whether third-party attributes are
            # separable on the 95 documents that DO have an individual subject.
            "individual_subject_docs": _subset_split(
                [r for r in non_subject if r["subject_type"] != "organization"]
            ),
            "organization_docs": _subset_split(
                [r for r in non_subject if r["subject_type"] == "organization"]
            ),
        },
        "found_not_authored": {
            "pairs_total":  len(pair_class),
            "by_class":     {k: fna_summary.get(k, 0)
                             for k in (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS)},
            "corrected_subject_linked": fna_summary.get(SUBJECT, 0),
            "by_information_type": {
                t: dict(fna_by_type[t]) for t in TYPE_NAMES if fna_by_type[t]
            },
        },
    }


def write_outputs(rows: list[dict], agg: dict, corpus_hash: str) -> None:
    artifact = {
        "artifact":         "stage1b_subject_linkage",
        "linkage_version":  LINKAGE_VERSION,
        "vocab_version":    VOCAB_VERSION,
        "corpus_sha256":    corpus_hash,
        "note": (
            "Per-occurrence classification of every detection in inventory v1.0.0. "
            "Deterministic rules only — no language model. `ambiguous` is a real "
            "class and is not suppressed. Does not modify the vocabulary, the "
            "inventory, the reconciliation, or the audit sheet."
        ),
        "classes": {
            SUBJECT:        "the mention is about the document's data subject",
            THIRD_PARTY:    "the mention is about some other individual",
            ORGANIZATIONAL: "belongs to the institution rather than any individual",
            AMBIGUOUS:      "not determinable from available deterministic signals",
        },
        "summary":   agg,
        "detections": rows,
    }
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        cols = ["doc_id", "document_type", "sensitivity_tier", "subject_type",
                "information_type", "value", "rule", "start", "classification",
                "signal", "structural", "region", "field_label", "section",
                "found_not_authored"]
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])

    with open(OUT_BY_TYPE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["information_type", "n", SUBJECT, THIRD_PARTY,
                    ORGANIZATIONAL, AMBIGUOUS, "pct_subject", "pct_third_party"])
        for t in TYPE_NAMES:
            d = agg["by_information_type"][t]
            w.writerow([t, d["n"], d[SUBJECT], d[THIRD_PARTY], d[ORGANIZATIONAL],
                        d[AMBIGUOUS], d["pct_subject"], d["pct_third_party"]])


def main() -> None:
    out = run()
    rows, corpus_hash = out["rows"], out["corpus_sha256"]
    agg = aggregate(rows)
    write_outputs(rows, agg, corpus_hash)

    n = agg["detections"]
    o = agg["overall"]
    print(f"Subject-linkage classification — linkage v{LINKAGE_VERSION}, "
          f"vocab v{VOCAB_VERSION}")
    print(f"{n} detections across 105 documents\n")
    for k in (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS):
        print(f"  {k:<16} {o[k]:>5}  {o['pct'][k]:>6.1%}")

    print(f"\n{'information type':<22} {'n':>5} {'subj':>5} {'3rd':>5} "
          f"{'org':>5} {'amb':>5}  {'%3rd':>6}")
    print("-" * 62)
    for t in sorted(TYPE_NAMES,
                    key=lambda x: -(agg["by_information_type"][x]["pct_third_party"] or 0)):
        d = agg["by_information_type"][t]
        p = d["pct_third_party"]
        print(f"  {t:<20} {d['n']:>5} {d[SUBJECT]:>5} {d[THIRD_PARTY]:>5} "
              f"{d[ORGANIZATIONAL]:>5} {d[AMBIGUOUS]:>5}  "
              f"{(f'{p:.1%}' if p is not None else '—'):>6}")

    print(f"\n{'sensitivity tier':<22} {'n':>5} {'subj':>5} {'3rd':>5} {'org':>5} {'amb':>5}")
    print("-" * 55)
    for k, d in agg["by_sensitivity_tier"].items():
        print(f"  {k:<20} {d['n']:>5} {d[SUBJECT]:>5} {d[THIRD_PARTY]:>5} "
              f"{d[ORGANIZATIONAL]:>5} {d[AMBIGUOUS]:>5}")

    print(f"\n{'subject_type':<22} {'n':>5} {'subj':>5} {'3rd':>5} {'org':>5} {'amb':>5}")
    print("-" * 55)
    for k, d in agg["by_subject_type"].items():
        print(f"  {k:<20} {d['n']:>5} {d[SUBJECT]:>5} {d[THIRD_PARTY]:>5} "
              f"{d[ORGANIZATIONAL]:>5} {d[AMBIGUOUS]:>5}")

    sa = agg["structural_analysis"]
    print(f"\nStructural analysis — third-party detections")
    print("-" * 55)
    print(f"  third-party detections      : {sa['third_party_detections']}")
    print(f"  resolved by structure       : {sa['resolved_structurally']:>4}"
          f"  ({sa['pct_structural']:.1%})")
    print(f"  resolved by identity match  : {sa['resolved_by_identity']:>4}"
          f"  ({sa['pct_identity']:.1%})")
    print(f"  left to prose default       : {sa['resolved_in_prose']:>4}"
          f"  ({sa['pct_prose']:.1%})")
    print(f"  by region : {sa['by_region']}")
    print(f"  by signal : {sa['by_signal']}")
    for key, title in (("individual_subject_docs", "documents WITH an individual subject"),
                       ("organization_docs",       "organization-subject documents")):
        d = sa[key]
        if not d["n"]:
            continue
        print(f"\n  third-party detections on {title}: {d['n']}")
        print(f"    structural {d['structural']:>4} ({d['pct_structural']:.1%})   "
              f"identity {d['identity']:>4} ({d['pct_identity']:.1%})   "
              f"prose {d['prose']:>4} ({d['pct_prose']:.1%})")
        print(f"    separable without reading prose: {d['pct_separable']:.1%}")

    print(f"\nSignal provenance (all detections): {agg['signal_provenance']}")

    f = agg["found_not_authored"]
    print(f"\nThe found-but-not-authored pairs, re-examined")
    print("-" * 55)
    print(f"  pairs total                 : {f['pairs_total']}")
    for k in (SUBJECT, THIRD_PARTY, ORGANIZATIONAL, AMBIGUOUS):
        print(f"  {k:<26}: {f['by_class'][k]:>4}")
    print(f"\n  CORRECTED FIGURE (subject-linked): {f['corrected_subject_linked']}")

    print(f"\nWrote:\n  {OUT_JSON}\n  {OUT_CSV}\n  {OUT_BY_TYPE}")


if __name__ == "__main__":
    main()
