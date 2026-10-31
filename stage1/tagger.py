"""
Paper III — Clinic-Domain Information-Type Tagger (Stage 1)

A deterministic regex + gazetteer tagger over the controlled vocabulary in
stage1/vocabulary.py. It exists because the PANOPTICON tagger cannot do this job:
`pii_handler.match_pii(prompt, pii_values)` is a closed-world *verifier* that
confirms which of a supplied set of known values appear in a text, and its
PANORAMA-derived category schema has no referent for nine of the sixteen
vocabulary entries (see vocabulary.UNDETECTABLE_BY_PANOPTICON). This module is a
separate implementation, not an extension of it; no PANOPTICON pattern is reused.

Contract
--------
    tag(text) -> dict[str, list[Detection]]

The ONLY input is document text. The tagger never sees `label.pii_attributes`,
`label.sensitivity_tier`, `attributes[]`, or the subject's identity — if it did,
the Stage 3 reconciliation would be circular and the Stage 4 audit meaningless.
The one exception is `name`, which is resolved against the fixed 24-agent
registry; that is world knowledge rather than label knowledge, but it is a
closed-world assumption and is declared as such in
vocabulary.UNDETECTABLE_BY_STAGE1.

Determinism
-----------
No randomness, no model calls, no network, no clock. Patterns are compiled once;
detections are returned sorted by (type, start). Running twice over the same text
yields byte-identical output.

Rule identifiers
----------------
Every detection carries the id of the rule that produced it (e.g. "dob.labeled",
"billing.icd10_paren"). The audit scorer groups false positives by rule id, so a
bad rule can be identified rather than the whole type being written off.

Exports
-------
Detection            : dataclass
tag(text)            : dict[str, list[Detection]]
tag_types(text)      : set[str]
TAGGER_VERSION       : str
RULE_IDS             : tuple[str, ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from stage1.vocabulary import VOCAB

# 1.0.1 — home_address suppression moved from a positional letterhead heuristic to
#         a content/structure test. The positional version discarded the subject's
#         address in every short-header document (66 of 105).
TAGGER_VERSION = "1.0.1"


@dataclass(frozen=True)
class Detection:
    """One tagger hit: an information type, the text that triggered it, and where."""

    type: str
    value: str
    start: int
    end: int
    rule: str

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "value": self.value,
            "start": self.start,
            "end": self.end,
            "rule": self.rule,
        }


# ---------------------------------------------------------------------------
# Suppression: the clinic's own letterhead
# ---------------------------------------------------------------------------
# Riverside's premises address and switchboard numbers appear on nearly every
# document. They are organizational contact details, not subject PII, and tagging
# them as home_address would produce a false positive on ~90 documents.

# Suppression is by CONTENT, not by position. An earlier positional version — treat
# everything before the first box-drawing rule as letterhead — silently discarded
# the subject's address in every document with a short header (discharge summaries,
# contractor agreements: "Address: 89 Birch Lane…" at offset ~130). Matching the
# clinic's own street line is both narrower and correct. The ZIP alone is not a
# marker: staff home addresses share 62704.
CLINIC_ADDRESS_MARKERS = (
    "1200 riverside",
    "riverside medical clinic",
    "riverside drive, suite",
)

_CLINIC_PHONE = re.compile(r"\(217\)\s*555-01\d{2}")


_ORG_LINE = re.compile(
    r"(?i)\b(clinic|hospital|laborator(?:y|ies)|imaging|radiolog|medical\s+(?:center|group)"
    r"|health\s+(?:system|center)|associates|partners|LLC|L\.L\.C\.|Inc\.?|LLP|P\.?C\.?)\b"
)


def _is_clinic_premises(value: str) -> bool:
    """True if the matched address is the clinic's own premises, not a person's."""
    v = value.casefold()
    return any(marker in v for marker in CLINIC_ADDRESS_MARKERS)


def _preceded_by_org_line(text: str, start: int) -> bool:
    """
    True if the nearest preceding non-empty line names an organization.

    An unlabeled street address sitting directly beneath an organization header is
    that organization's premises, not a person's home. This is a structural test
    rather than a blocklist of specific buildings, so it also catches the referral
    and imaging facilities the corpus invents beyond the clinic's own address.
    """
    for line in reversed(text[:start].splitlines()):
        stripped = line.strip(" \t│|─=*-")
        if not stripped:
            continue
        letters = [c for c in stripped if c.isalpha()]
        is_shouted = bool(letters) and all(c.isupper() for c in letters)
        return is_shouted or bool(_ORG_LINE.search(stripped))
    return False


# ---------------------------------------------------------------------------
# Gazetteers
# ---------------------------------------------------------------------------
# Authored from general clinical/administrative knowledge rather than harvested
# from the Riverside corpus, so that the tagger retains genuine miss potential and
# the Stage 4 audit measures something. Residual fitting risk is stated in
# REPORT.md, Limitations.

MEDICATIONS = (
    # cardiovascular
    "lisinopril", "enalapril", "ramipril", "losartan", "valsartan", "amlodipine",
    "nifedipine", "diltiazem", "verapamil", "metoprolol", "atenolol", "carvedilol",
    "labetalol", "propranolol", "hydrochlorothiazide", "chlorthalidone", "furosemide",
    "spironolactone", "digoxin", "amiodarone", "warfarin", "apixaban", "rivaroxaban",
    "clopidogrel", "aspirin", "atorvastatin", "simvastatin", "rosuvastatin",
    "pravastatin", "ezetimibe", "isosorbide", "nitroglycerin", "hydralazine",
    # endocrine / metabolic
    "metformin", "glipizide", "glyburide", "glimepiride", "sitagliptin", "empagliflozin",
    "dapagliflozin", "canagliflozin", "liraglutide", "semaglutide", "dulaglutide",
    "insulin", "levothyroxine", "methimazole", "prednisone", "hydrocortisone",
    "alendronate", "calcitriol",
    # neuro / psych
    "donepezil", "memantine", "rivastigmine", "galantamine", "levetiracetam",
    "phenytoin", "carbamazepine", "valproate", "lamotrigine", "topiramate",
    "gabapentin", "pregabalin", "sumatriptan", "sertraline", "fluoxetine",
    "escitalopram", "citalopram", "paroxetine", "venlafaxine", "duloxetine",
    "bupropion", "mirtazapine", "trazodone", "amitriptyline", "nortriptyline",
    "lithium", "quetiapine", "risperidone", "olanzapine", "aripiprazole",
    "haloperidol", "ziprasidone", "lurasidone", "clozapine", "buspirone",
    "alprazolam", "lorazepam", "clonazepam", "diazepam", "zolpidem",
    "buprenorphine", "naloxone", "naltrexone", "methadone", "acamprosate",
    "disulfiram", "varenicline",
    # analgesia
    "acetaminophen", "ibuprofen", "naproxen", "meloxicam", "celecoxib", "diclofenac",
    "tramadol", "oxycodone", "hydrocodone", "morphine", "hydromorphone", "fentanyl",
    "codeine",
    # anti-infective
    "amoxicillin", "azithromycin", "ceftriaxone", "cephalexin", "ciprofloxacin",
    "levofloxacin", "doxycycline", "clindamycin", "metronidazole", "nitrofurantoin",
    "trimethoprim", "sulfamethoxazole", "vancomycin", "fluconazole", "acyclovir",
    "valacyclovir", "oseltamivir",
    # antiretroviral / oncology / other
    "biktarvy", "truvada", "descovy", "dolutegravir", "emtricitabine", "tenofovir",
    "bictegravir", "raltegravir", "tamoxifen", "anastrozole", "letrozole",
    "trastuzumab", "paclitaxel", "docetaxel", "doxorubicin", "cyclophosphamide",
    "carboplatin", "cisplatin", "capecitabine", "methotrexate",
    # respiratory / GI / other common
    "albuterol", "fluticasone", "budesonide", "montelukast", "tiotropium",
    "omeprazole", "pantoprazole", "famotidine", "ondansetron", "loratadine",
    "cetirizine", "diphenhydramine", "allopurinol", "colchicine", "tamsulosin",
    "finasteride", "sildenafil", "oxybutynin", "folic acid", "ferrous sulfate",
    "cyanocobalamin", "cholecalciferol", "prenatal vitamin",
)

CONDITIONS = (
    "diabetes", "diabetes mellitus", "hypertension", "hypertensive", "hyperlipidemia",
    "hypercholesterolemia", "atrial fibrillation", "heart failure", "cardiomyopathy",
    "coronary artery disease", "myocardial infarction", "angina", "stroke",
    "ischemic stroke", "transient ischemic attack", "chronic kidney disease",
    "renal insufficiency", "nephropathy", "asthma", "copd", "emphysema", "pneumonia",
    "bronchitis", "carcinoma", "adenocarcinoma", "melanoma", "lymphoma", "leukemia",
    "neoplasm", "cancer", "tumor", "metastatic", "anemia", "thrombocytopenia",
    "hypothyroidism", "hyperthyroidism", "osteoporosis", "osteoarthritis",
    "rheumatoid arthritis", "gout", "obesity", "sleep apnea", "gerd", "cirrhosis",
    "hepatitis", "pancreatitis", "diverticulitis", "colitis", "crohn",
    "alzheimer", "dementia", "parkinson", "multiple sclerosis", "epilepsy",
    "seizure disorder", "neuropathy", "migraine", "hiv", "aids", "preeclampsia",
    "gestational hypertension", "gestational diabetes", "prediabetes", "glaucoma",
    "cataract", "macular degeneration", "psoriasis", "eczema", "cellulitis",
    "sepsis", "fracture", "appendicitis",
)

# Split into two tiers so the audit can score them separately. A clinical term is
# evidence that the document states a psychiatric or substance-use finding about
# the subject. A category marker only says the document sits in that category —
# it fires on statutory confidentiality boilerplate ("...protected under the
# Illinois MHDDCA...") and on a clinician's specialty ("Psychiatry") in HR and
# credentialing records, where no subject mental-health information is present.
MENTAL_HEALTH_CLINICAL = (
    "depression", "depressive", "major depressive disorder", "mdd", "dysthymia",
    "anxiety", "generalized anxiety", "panic disorder", "ptsd",
    "post-traumatic stress", "bipolar", "mania", "manic", "schizophrenia",
    "schizoaffective", "psychosis", "psychotic", "suicidal ideation", "self-harm",
    "obsessive-compulsive", "ocd", "adhd", "eating disorder", "anorexia", "bulimia",
    "substance use disorder", "substance abuse", "opioid use disorder",
    "alcohol use disorder", "alcohol dependence", "detoxification",
    "phq-9", "phq9", "gad-7", "gad7", "mmse", "moca",
)

MENTAL_HEALTH_CATEGORY = (
    "psychiatric", "psychiatry", "psychotherapy", "behavioral health",
    "mental health", "counseling session", "42 cfr part 2", "mhddca",
)

INSURERS = (
    "bluecross", "blue cross", "blueshield", "blue shield", "bcbs", "anthem",
    "aetna", "cigna", "humana", "unitedhealthcare", "united healthcare",
    "united health", "uhc", "kaiser permanente", "kaiser", "medicare", "medicaid",
    "tricare", "molina", "centene", "wellcare", "oscar health", "ambetter",
)

JOB_TITLES = (
    "attending physician", "attending psychiatrist", "physician", "psychiatrist",
    "cardiologist", "oncologist", "radiologist", "internist", "surgeon",
    "nurse practitioner", "registered nurse", "licensed practical nurse",
    "charge nurse", "staff nurse", "nurse", "medical assistant", "phlebotomist",
    "billing specialist", "billing manager", "coding specialist", "hr manager",
    "human resources manager", "office manager", "practice administrator",
    "it contractor", "facilities contractor", "systems administrator",
    "receptionist", "front desk coordinator", "clinical director", "medical director",
)


def _alt(terms: tuple[str, ...]) -> str:
    """Regex alternation over a gazetteer, longest-first so the longest match wins."""
    return "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))


# ---------------------------------------------------------------------------
# Shared sub-patterns
# ---------------------------------------------------------------------------

_DATE = (
    r"(?:\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|(?:January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s+\d{1,2},?\s+\d{4})"
)
_ICD10 = r"[A-TV-Z]\d[0-9A-Z](?:\.[0-9A-Z]{1,4})?"
_MONEY = r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------
# (rule_id, information_type, compiled_pattern, capture_group)
# capture_group 0 means "the whole match is the evidence".

_RULES: list[tuple[str, str, re.Pattern, int]] = []


def _rule(rule_id: str, info_type: str, pattern: str, group: int = 0,
          flags: int = re.IGNORECASE) -> None:
    assert info_type in VOCAB, f"rule {rule_id} targets non-vocabulary type {info_type!r}"
    _RULES.append((rule_id, info_type, re.compile(pattern, flags), group))


# -- date_of_birth ----------------------------------------------------------
# Labeled only. Bare dates are ambiguous with dates of service, contract
# effective dates, and prescription dates, all of which are common here.
_rule("dob.labeled", "date_of_birth",
      rf"(?:date\s+of\s+birth|birth\s+date|\bDOB\b|\bD\.O\.B\.)\s*[:\-]?\s*({_DATE})", 1)

# -- ssn --------------------------------------------------------------------
_rule("ssn.masked_or_full", "ssn",
      r"\b(?:\d{3}|X{3}|\*{3})[-\s](?:\d{2}|X{2}|\*{2})[-\s]\d{4}\b")
_rule("ssn.labeled", "ssn",
      r"(?:\bSSN\b|social\s+security(?:\s+(?:number|no\.?|#))?)\s*[:\-#]?\s*"
      r"([X\*\d]{3}[-\s][X\*\d]{2}[-\s]\d{4})", 1)

# -- home_address -----------------------------------------------------------
_STREET_SUFFIX = (
    r"(?:St|Street|Rd|Road|Ave|Avenue|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court"
    r"|Cir|Circle|Pl|Place|Pkwy|Parkway|Way|Trl|Trail|Run|Ter|Terrace)"
)
_rule("address.street_city_state_zip", "home_address",
      rf"\b\d{{1,5}}\s+(?:[A-Z][A-Za-z'\-]+\s+){{0,3}}{_STREET_SUFFIX}\.?"
      rf"(?:\s*,\s*[A-Z][A-Za-z\s]+)?\s*,?\s*[A-Z]{{2}}\s+\d{{5}}(?:-\d{{4}})?\b",
      0, re.NOFLAG)
_rule("address.labeled", "home_address",
      rf"(?:home\s+address|residence|mailing\s+address|patient\s+address|address)"
      rf"\s*[:\-]\s*(\d{{1,5}}\s+[^\n]{{5,80}})", 1)

# -- emergency_contact ------------------------------------------------------
_rule("emergency.labeled", "emergency_contact",
      r"(?:emergency\s+contact|next\s+of\s+kin|legal\s+guardian|guardian)"
      r"\s*(?:name|phone)?\s*[:\-]\s*([^\n]{3,90})", 1)

# -- billing_code -----------------------------------------------------------
_rule("billing.cpt_labeled", "billing_code",
      r"\b(?:CPT|HCPCS)(?:\s*(?:code|®))?\s*[:\-#]?\s*(\d{5})\b", 1)
_rule("billing.icd_labeled", "billing_code",
      rf"\bICD[-\s]?(?:10|9)(?:[-\s]?CM)?\s*[:\-#]?\s*({_ICD10})\b", 1)
_rule("billing.icd_parenthetical", "billing_code",
      rf"\((({_ICD10}))\)", 1, re.NOFLAG)
# Bare 5-digit procedure codes appear in claim/statement line items. Springfield
# ZIP codes (627xx) are also five digits, so the code must sit on a line that
# also carries a charge amount or an explicit procedure/units column, and must
# not be preceded by a two-letter state abbreviation.
_rule("billing.cpt_line_item", "billing_code",
      rf"(?<![A-Z]{{2}}\s)\b(\d{{5}})\b(?=[^\n]*(?:{_MONEY}|\bunits?\b|\bmodifier\b"
      rf"|\bprocedure\b|\bcharge\b))", 1)

# -- insurance_info ---------------------------------------------------------
_rule("insurance.carrier_plan", "insurance_info",
      rf"\b({_alt(INSURERS)})\b(?:\s+(?:Part\s+[AB](?:\+B)?|PPO|HMO|EPO|POS|Advantage))?", 1)
# The captured token must contain a digit. Without that guard the rule fires on
# "Insurance: United Health PPO" -> "United" and "Member: Robert Lee" -> "Robert",
# i.e. on carrier and subscriber names rather than on identifiers.
_rule("insurance.member_id", "insurance_info",
      r"(?:member|policy|subscriber|insurance|plan|group)\s*(?:id|#|no\.?|number)?"
      r"\s*[:\-#]\s*#?((?=[A-Za-z0-9\-]*\d)[A-Za-z0-9][A-Za-z0-9\-]{4,20})\b", 1)

# -- salary -----------------------------------------------------------------
_rule("salary.labeled_amount", "salary",
      rf"(?:annual\s+salary|base\s+salary|base\s+pay|annual\s+compensation"
      rf"|total\s+compensation|salary|compensation)\s*[:\-]?\s*(?:of\s+)?({_MONEY})", 1)
_rule("salary.hourly_rate", "salary",
      rf"(?:hourly\s+rate|rate\s+of\s+pay|billing\s+rate)?\s*({_MONEY}\s*/\s*(?:hr|hour))", 1)

# -- medical_license --------------------------------------------------------
_rule("license.npi", "medical_license", r"\bNPI\s*[:\-#]?\s*(\d{10})\b", 1)
_rule("license.dea", "medical_license", r"\bDEA\s*[:\-#]*\s*([A-Z]{2}\d{7})\b", 1)
_rule("license.state", "medical_license",
      r"\b((?:IL|[A-Z]{2})-(?:MD|DO|RN|NP|PA)-\d{4,8})\b", 1, re.NOFLAG)
_rule("license.labeled", "medical_license",
      r"(?:medical\s+)?licen[sc]e\s*(?:number|no\.?|#)?\s*[:\-]\s*([A-Z0-9][A-Z0-9\-]{3,20})\b", 1)

# -- medical_medication -----------------------------------------------------
_rule("medication.gazetteer", "medical_medication",
      rf"\b({_alt(MEDICATIONS)})\b", 1)
# Excludes the imperative verbs that open a plan line ("Continue Metformin 500 mg"),
# which would otherwise be captured as part of the drug name.
_RX_VERBS = (r"Continue|Start|Stop|Take|Resume|Hold|Begin|Increase|Decrease"
             r"|Discontinue|Refill|Initiate|Administer|Prescribe|Titrate|Maintain")
_rule("medication.dose_form", "medical_medication",
      rf"\b((?!(?:{_RX_VERBS})\b)[A-Z][a-z]{{4,}}(?:\s+[A-Z][a-z]+)?"
      rf"\s+\d+(?:\.\d+)?\s?(?:mg|mcg|g|mL|units?)"
      rf"(?:/\d+(?:\.\d+)?\s?(?:mg|mcg|g|mL))?)\b", 1, re.NOFLAG)

# -- medical_diagnosis ------------------------------------------------------
# ICD-10 chapters F (mental/behavioural) are routed to mental_health instead.
_rule("diagnosis.icd_nonpsych", "medical_diagnosis",
      rf"\b([A-EG-TV-Z]\d[0-9A-Z](?:\.[0-9A-Z]{{1,4}})?)\b(?=\s*[\)\,\;\.\-\s])",
      1, re.NOFLAG)
_rule("diagnosis.gazetteer", "medical_diagnosis", rf"\b({_alt(CONDITIONS)})\b", 1)
# The separator may not cross a newline, and the captured text must contain a
# letter — otherwise a heading followed by a box-drawing rule captures the rule.
_rule("diagnosis.labeled", "medical_diagnosis",
      r"(?:^|\n)[ \t]*(?:assessment|diagnosis|diagnoses|impression|primary\s+diagnosis"
      r"|working\s+diagnosis|clinical\s+impression)[ \t]*[:\-][ \t]*"
      r"((?=[^\n]*[A-Za-z])[^\n]{3,120})",
      1, re.IGNORECASE | re.MULTILINE)

# -- mental_health ----------------------------------------------------------
_rule("mental.icd_f_code", "mental_health",
      r"\b(F\d{2}(?:\.\d{1,3})?)\b", 1, re.NOFLAG)
_rule("mental.clinical_term", "mental_health",
      rf"\b({_alt(MENTAL_HEALTH_CLINICAL)})\b", 1)
_rule("mental.category_marker", "mental_health",
      rf"\b({_alt(MENTAL_HEALTH_CATEGORY)})\b", 1)

# -- medical_history --------------------------------------------------------
_HISTORY_HEADING = (r"past\s+medical\s+history|pertinent\s+medical\s+history"
                    r"|past\s+surgical\s+history|medical\s+history|prior\s+history"
                    r"|active\s+problem\s+list|history\s+of\s+present\s+illness|\bPMH\b")
# Inline form: "Past Medical History: hypertension, ..." — a short qualifier may
# sit between the heading and the colon ("Medical History Note: ...").
_rule("history.section", "medical_history",
      rf"(?:^|\n)[ \t]*(?:{_HISTORY_HEADING})[ \t]*\w{{0,10}}[ \t]*[:\-][ \t]*"
      rf"((?=[^\n]*[A-Za-z])[^\n]{{3,200}})", 1, re.IGNORECASE | re.MULTILINE)
# Block form: heading on its own line, then either a bulleted list or a prose
# paragraph, commonly separated by a box-drawing rule and/or a blank line. This is
# how most Riverside clinical notes lay out history; the inline rule alone reaches
# only a small minority of them.
_rule("history.block", "medical_history",
      rf"(?:^|\n)[ \t]*(?:{_HISTORY_HEADING})\b[^\n]{{0,40}}\n"
      rf"(?:[ \t]*[─=_—–\-]{{5,}}[ \t]*\n|[ \t]*\n){{0,3}}"
      rf"((?:[ \t]*[^\n]{{5,}}\n?){{1,6}})",
      1, re.IGNORECASE | re.MULTILINE)
_rule("history.diagnosed_year", "medical_history",
      r"\b((?:diagnosed|dx'?d|onset|since)\s+(?:in\s+)?(?:approximately\s+)?"
      r"(?:19|20)\d{2})\b", 1)
_rule("history.history_of", "medical_history",
      r"\b((?:remote\s+)?history\s+of\s+[^\n\.;]{3,80})", 1)
_rule("history.status_post", "medical_history",
      r"\b(s/p\s+[^\n\.;]{3,60})", 1)

# -- employment_contract ----------------------------------------------------
# A qualifier is required; a bare "Contract" is not evidence of an employment
# agreement (it occurs in insurance and vendor language too).
_rule("employment.agreement_title", "employment_contract",
      r"\b((?:full[-\s]?time|part[-\s]?time|physician|employment|attending|staff"
      r"|nursing|offer)(?:[-\s]\w+){0,3}?[-\s](?:agreement|contract|letter))\b", 1)
_rule("employment.contract_id", "employment_contract",
      r"\b(EMP-\d{4}-[A-Z]+-\d{3,})\b", 1, re.NOFLAG)
_rule("employment.effective_date", "employment_contract",
      rf"\b(effective\s+(?:date\s*[:\-]\s*)?{_DATE})", 1)

# -- contract_terms ---------------------------------------------------------
_rule("contract.independent", "contract_terms",
      r"\b(independent\s+contractor|contractor\s+agreement|statement\s+of\s+work"
      r"|scope\s+of\s+work|consulting\s+agreement)\b", 1)
_rule("contract.no_phi", "contract_terms",
      r"\b(no\s+PHI\s+access(?:\s+permitted)?)\b", 1)

# -- job_title --------------------------------------------------------------
_rule("title.gazetteer", "job_title", rf"\b({_alt(JOB_TITLES)})\b", 1)
_rule("title.labeled", "job_title",
      r"(?:position|job\s+title|title|role|classification)\s*[:\-]\s*([^\n]{3,60})", 1)

RULE_IDS: tuple[str, ...] = tuple(r[0] for r in _RULES)


# ---------------------------------------------------------------------------
# Closed-world name registry
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _name_pattern() -> re.Pattern:
    """
    Alternation over the 24-agent registry, plus a generic titled-provider form.

    Imported lazily so that importing this module does not construct the world.
    Falls back to the provider pattern alone if the registry is unavailable, which
    keeps the tagger runnable standalone.
    """
    names: list[str] = []
    try:
        from world.agents_pool import EXTENDED_ALL_AGENTS
        names = sorted(
            {a.name for a in EXTENDED_ALL_AGENTS if a.name},
            key=len, reverse=True,
        )
    except Exception:
        pass

    provider = r"Dr\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z']+)+"
    alts = [re.escape(n) for n in names] + [provider]
    return re.compile(r"\b(" + "|".join(alts) + r")\b")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tag(text: str | None) -> dict[str, list[Detection]]:
    """
    Tag `text` against the controlled vocabulary.

    Returns {information_type: [Detection, ...]} containing only types with at
    least one hit. Detections are deduplicated on (type, normalized value) —
    keeping the earliest occurrence — and sorted by (type, start).
    """
    if not text:
        return {}

    hits: list[Detection] = []

    for rule_id, info_type, pattern, group in _RULES:
        for m in pattern.finditer(text):
            try:
                value = m.group(group)
            except IndexError:
                continue
            if not value or not value.strip():
                continue
            start, end = m.span(group)

            # Organizational premises are not a person's home address. The labeled
            # rule is anchored to an explicit "Address:" field and is left alone;
            # only the unlabeled pattern needs the structural guard.
            if info_type == "home_address":
                if _is_clinic_premises(value):
                    continue
                if (rule_id == "address.street_city_state_zip"
                        and _preceded_by_org_line(text, start)):
                    continue
            # Likewise the switchboard block.
            if info_type == "emergency_contact" and _CLINIC_PHONE.fullmatch(value.strip()):
                continue

            hits.append(Detection(info_type, value.strip(), start, end, rule_id))

    # Deduplicate per (type, casefolded value), earliest span wins.
    seen: set[tuple[str, str]] = set()
    unique: list[Detection] = []
    for d in sorted(hits, key=lambda d: (d.type, d.start, d.rule)):
        key = (d.type, d.value.casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)

    # Names last, so the registry import only happens when there is text to scan.
    for m in _name_pattern().finditer(text):
        key = ("name", m.group(1).casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(Detection("name", m.group(1), m.start(1), m.end(1),
                                "name.registry"))

    out: dict[str, list[Detection]] = {}
    for d in sorted(unique, key=lambda d: (d.type, d.start)):
        out.setdefault(d.type, []).append(d)
    return out


def tag_types(text: str | None) -> set[str]:
    """The set of information types present in `text`."""
    return set(tag(text))


if __name__ == "__main__":
    import json
    from pathlib import Path

    records = json.loads(Path("data/dataset.json").read_text(encoding="utf-8"))
    sample = records[0]
    found = tag(sample["content"])
    print(f"tagger v{TAGGER_VERSION} — {len(_RULES) + 1} rules over "
          f"{len(VOCAB)} vocabulary entries\n")
    print(f"{sample['title']}\n")
    for t in sorted(found):
        vals = ", ".join(d.value[:38] for d in found[t][:4])
        print(f"  {t:<22} {len(found[t]):>2}  {vals}")
