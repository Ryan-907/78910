"""
Riverside Medical Clinic — Dataset Attribute-Type Normalizer

The generation model returned attribute type names in three conventions
(UPPER_SNAKE, CamelCase, snake_case) plus a few free inventions
(ICD10Code, DEANumber, MentalHealthDiagnosis). This one-shot pass rewrites
every record's attributes[].information_type to the canonical AttributeType
snake_case constants so the leakage checkers and validators agree.

Usage
-----
    python normalize_dataset.py          # rewrites dataset.json in place
"""

import json
import re
from collections import Counter
from pathlib import Path

DATASET_PATH = Path("data/dataset.json")

# Post-normalization aliases: free-invented or off-schema names -> canonical.
ALIASES = {
    "icd10_code":              "billing_code",
    "dea_number":              "medical_license",
    "deanumber":               "medical_license",
    "mental_health_diagnosis": "mental_health",
    "medication":              "medical_medication",
    "full_name":               "name",
    "patient_name":            "name",
    "person_name":             "name",
    "job_title":               "job_title",
    "job_role":                "job_title",
}


def to_snake(name: str) -> str:
    """BILLING_CODE, BillingCode, DEANumber, billing_code -> snake_case."""
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", name)   # DEANumber -> DEA_Number
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)        # BillingCode -> Billing_Code
    return s.lower()


def normalize(name: str) -> str:
    snake = to_snake(name)
    return ALIASES.get(snake, snake)


def main():
    with open(DATASET_PATH, encoding="utf-8") as f:
        records = json.load(f)

    before = Counter()
    after  = Counter()
    changed = 0

    for record in records:
        for attr in record.get("attributes", []):
            t = attr.get("information_type")
            if not t:
                continue
            before[t] += 1
            nt = normalize(t)
            if nt != t:
                attr["information_type"] = nt
                changed += 1
            after[nt] += 1

        # Recompute generation warnings: the stored ones were recorded against
        # the pre-normalization type names and are mostly stale.
        present = {a.get("information_type") for a in record.get("attributes", [])}
        keep    = [w for w in record.get("generation_warnings", [])
                   if not w.startswith("pii_attribute ")]
        keep   += [
            f"pii_attribute '{pii}' missing from returned attributes"
            for pii in record.get("pii_attributes", [])
            if pii not in present
        ]
        record["generation_warnings"] = keep

    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Normalized {changed} attribute type names across {len(records)} records\n")
    print(f"{'Canonical type':<24} count")
    for name, count in sorted(after.items(), key=lambda x: -x[1]):
        print(f"  {name:<22} {count:>4}")


if __name__ == "__main__":
    main()
