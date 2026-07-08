"""
Riverside Medical Clinic — Dataset Validation

Reads dataset.json and checks for:

1. Coverage     — all sensitivity tiers and document types represented
2. Consistency  — label fields internally consistent (e.g. extra_sensitive
                  tier matches permitted roles)
3. Content      — generated content is non-empty and long enough to be useful
4. Attributes   — pii_attributes listed in the label appear in the
                  attributes list returned by generation
5. Warnings     — any generation_warnings flagged during creation

Prints a full report and writes validation_report.json.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

DATASET_PATH    = Path("data/dataset.json")
REPORT_PATH     = Path("reports/validation_report.json")
MIN_CONTENT_LEN = 100   # characters — documents shorter than this are flagged

# Tiers that should always have assignment_required=True
ASSIGNMENT_TIERS = {
    "clinical_standard",
    "clinical_sensitive",
    "financial",
    "employment",
}

# Extra-sensitive documents should only permit Doctors (not Nurses/Billing)
EXTRA_SENSITIVE_MAX_ROLES = {"Doctor"}


def load() -> list[dict]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"{DATASET_PATH} not found — run generate_dataset.py first")
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_coverage(records: list[dict]) -> dict:
    tiers  = Counter(r["sensitivity_tier"]  for r in records)
    dtypes = Counter(r["document_type"]     for r in records)
    stypes = Counter(r["subject_type"]      for r in records)

    from core.Agent import SensitivityTier, DocumentType, SubjectType
    all_tiers  = {v for k, v in vars(SensitivityTier).items()  if not k.startswith("_")}
    all_dtypes = {v for k, v in vars(DocumentType).items()     if not k.startswith("_")}
    all_stypes = {v for k, v in vars(SubjectType).items()      if not k.startswith("_")}

    missing_tiers  = all_tiers  - set(tiers)
    missing_dtypes = all_dtypes - set(dtypes)
    missing_stypes = all_stypes - set(stypes)

    return {
        "tier_counts":     dict(tiers),
        "dtype_counts":    dict(dtypes),
        "stype_counts":    dict(stypes),
        "missing_tiers":   sorted(missing_tiers),
        "missing_dtypes":  sorted(missing_dtypes),
        "missing_stypes":  sorted(missing_stypes),
    }


def check_consistency(records: list[dict]) -> list[dict]:
    issues = []
    for r in records:
        title = r["title"]
        tier  = r["sensitivity_tier"]
        roles = set(r.get("permitted_receiver_roles", []))

        # assignment_required should be True for sensitive tiers
        if tier in ASSIGNMENT_TIERS and not r.get("assignment_required", True):
            issues.append({"title": title,
                           "issue": f"assignment_required=False but tier={tier}"})

        # extra_sensitive documents should not permit Billing or IT roles
        if r.get("extra_sensitive"):
            disallowed = roles - EXTRA_SENSITIVE_MAX_ROLES - {"HR Manager"}
            if disallowed:
                issues.append({"title": title,
                               "issue": f"extra_sensitive=True but permitted roles include {disallowed}"})
            if not r.get("extra_sensitive_reason"):
                issues.append({"title": title,
                               "issue": "extra_sensitive=True but extra_sensitive_reason is null"})

        # public documents should have no assignment requirement
        if tier == "public" and r.get("assignment_required"):
            issues.append({"title": title,
                           "issue": "assignment_required=True on a public document"})

        # governing_principle should be set for non-public docs
        if tier != "public" and not r.get("governing_principle"):
            issues.append({"title": title,
                           "issue": f"governing_principle is null for tier={tier}"})

    return issues


def check_content(records: list[dict]) -> list[dict]:
    issues = []
    for r in records:
        content = r.get("content", "")
        if not content:
            issues.append({"title": r["title"], "issue": "content is empty"})
        elif len(content) < MIN_CONTENT_LEN:
            issues.append({"title": r["title"],
                           "issue": f"content too short ({len(content)} chars < {MIN_CONTENT_LEN})"})
    return issues


def check_attributes(records: list[dict]) -> list[dict]:
    issues = []
    for r in records:
        returned_types = {a["information_type"] for a in r.get("attributes", [])}
        content_lower  = r.get("content", "").lower()

        for pii in r.get("pii_attributes", []):
            if pii not in returned_types:
                issues.append({"title": r["title"],
                               "issue": f"pii_attribute '{pii}' missing from attributes list"})

        # Check each returned attribute value actually appears in content
        for attr in r.get("attributes", []):
            val = attr.get("attribute", "")
            if val and val.lower() not in content_lower:
                issues.append({"title": r["title"],
                               "issue": f"attribute value '{val[:40]}' not found in content"})

    return issues


def check_warnings(records: list[dict]) -> list[dict]:
    flagged = []
    for r in records:
        warnings = r.get("generation_warnings", [])
        if warnings:
            flagged.append({"title": r["title"], "warnings": warnings})
    return flagged


def print_section(title: str, items: list, formatter=None) -> None:
    status = "OK" if not items else f"{len(items)} issues"
    print(f"\n{'─' * 60}")
    print(f"  {title:<40} [{status}]")
    print(f"{'─' * 60}")
    if items:
        for item in items[:20]:
            if formatter:
                print(formatter(item))
            else:
                print(f"  {item}")
        if len(items) > 20:
            print(f"  … and {len(items) - 20} more")


def main() -> None:
    records = load()
    print(f"Validating {len(records)} records from {DATASET_PATH}\n")

    coverage     = check_coverage(records)
    consistency  = check_consistency(records)
    content      = check_content(records)
    attributes   = check_attributes(records)
    warnings     = check_warnings(records)

    # ---- Coverage summary ----
    print("=" * 60)
    print("COVERAGE")
    print("=" * 60)
    print("\nSensitivity tier distribution:")
    for tier, count in sorted(coverage["tier_counts"].items()):
        print(f"  {tier:<25} {count}")
    print("\nDocument type distribution:")
    for dtype, count in sorted(coverage["dtype_counts"].items()):
        print(f"  {dtype:<30} {count}")
    if coverage["missing_tiers"]:
        print(f"\n⚠  Missing tiers : {coverage['missing_tiers']}")
    if coverage["missing_dtypes"]:
        print(f"⚠  Missing dtypes: {coverage['missing_dtypes']}")

    # ---- Issue sections ----
    print_section("Consistency checks", consistency,
                  lambda x: f"  [{x['title'][:50]}]\n    {x['issue']}")
    print_section("Content checks", content,
                  lambda x: f"  [{x['title'][:50]}]\n    {x['issue']}")
    print_section("Attribute checks", attributes,
                  lambda x: f"  [{x['title'][:50]}]\n    {x['issue']}")
    print_section("Generation warnings", warnings,
                  lambda x: f"  [{x['title'][:50]}]\n    " + "; ".join(x["warnings"]))

    # ---- Summary ----
    total_issues = len(consistency) + len(content) + len(attributes)
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total records     : {len(records)}")
    print(f"  Consistency issues: {len(consistency)}")
    print(f"  Content issues    : {len(content)}")
    print(f"  Attribute issues  : {len(attributes)}")
    print(f"  Records with warnings: {len(warnings)}")
    print(f"  Total issues      : {total_issues}")
    print(f"  Status            : {'PASS' if total_issues == 0 else 'NEEDS REVIEW'}")

    report = {
        "total_records":    len(records),
        "coverage":         coverage,
        "consistency":      consistency,
        "content":          content,
        "attributes":       attributes,
        "warnings":         warnings,
        "total_issues":     total_issues,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nFull report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
