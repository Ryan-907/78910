"""
Paper III — Stage 2a: Validate the Authored Role Permission Sets

Runs after the researcher fills in the template and before anything is
adjudicated. It checks the sets are well-formed and surfaces the two shapes that
are plausible but worth seeing deliberately, rather than discovering them in the
Stage 2b results.

This module makes no normative judgement. It never proposes a value for a blank
cell, never flags a decision as wrong, and never ranks one authored set against
another. "A type permitted to no role" and "a type permitted to every role" are
reported as facts to confirm, not as errors to fix — either may be exactly what
the author intends.

Checks
------
1. COMPLETE      every (role, type) cell holds a recognised decision. No blanks,
                 no third values, no typos silently read as deny.
2. IN VOCABULARY every type named exists in frozen v1.2.0, and every v1.2.0 type
                 is present. A permission set keyed against a type the vocabulary
                 does not contain would silently never fire; a missing type would
                 leave a hole in the subset test.
3. ROLES         exactly the six roles held by the agent pool, no more, no fewer.
4. SURFACED      types permitted to no role, and types permitted to every role.

Exit status is non-zero if any of 1-3 fail. Check 4 never fails; it reports.

Usage
-----
    python -m stage2.validate_permissions
    python -m stage2.validate_permissions --template path/to/other.csv

Outputs (stage2/artifacts/)
    role_permissions_v1.2.0.json      the validated sets, machine-readable
    validation_report_v1.2.0.json     every check and its result
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from stage2.build_template import (
    ARTIFACT_DIR, ROLES, DECISION_VALUES, TEMPLATE_PATH, IMPACT_JSON,
)
from stage1.vocabulary import INFORMATION_TYPES, VOCAB, VOCAB_VERSION
from stage1.subject_linkage import LINKAGE_VERSION

PERMISSIONS_PATH = ARTIFACT_DIR / f"role_permissions_v{VOCAB_VERSION}.json"
REPORT_PATH      = ARTIFACT_DIR / f"validation_report_v{VOCAB_VERSION}.json"

TYPE_NAMES = [t.name for t in INFORMATION_TYPES]

# Accepted spellings. Anything else is an error rather than a silent deny --
# a typo must not become a policy decision.
PERMIT_WORDS = {"permit", "p", "y", "yes", "allow", "1", "true"}
DENY_WORDS   = {"deny", "d", "n", "no", "block", "0", "false"}


def load_template(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `python -m stage2.build_template` first.")
    if path.suffix.lower() == ".xlsx":
        from stage1.xlsx_reader import read_dicts
        return read_dicts(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize(raw: str | None) -> str | None:
    if raw is None:
        return None
    v = raw.strip().casefold()
    if not v:
        return None
    if v in PERMIT_WORDS:
        return "permit"
    if v in DENY_WORDS:
        return "deny"
    return "__invalid__"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--template", type=Path, default=TEMPLATE_PATH)
    args = p.parse_args()

    # Validating a template other than the canonical one writes its results beside
    # that file, so a trial run cannot deposit synthetic policy in stage2/artifacts.
    # The canonical template's .xlsx sibling counts as canonical: authoring in Excel
    # is the expected path and must not divert the real permission set to a
    # test-shaped filename.
    canonical = {TEMPLATE_PATH.resolve(), TEMPLATE_PATH.with_suffix(".xlsx").resolve()}
    if args.template.resolve() in canonical:
        permissions_path, report_path = PERMISSIONS_PATH, REPORT_PATH
    else:
        stem = args.template.with_suffix("")
        permissions_path = stem.with_name(stem.name + "_role_permissions.json")
        report_path = stem.with_name(stem.name + "_validation_report.json")

    rows = load_template(args.template)
    problems: list[str] = []

    # ---- 3. roles ---------------------------------------------------------
    header_roles = [r for r in ROLES if rows and r in rows[0]]
    missing_roles = [r for r in ROLES if r not in (rows[0] if rows else {})]
    extra_roles: list[str] = []
    if rows:
        known = set(ROLES) | {
            "information_type", "family", "extra_sensitive",
            "subject_linked_documents", "tiers", "permitted_flows_carrying_it",
            "example_1", "example_2", "definition", "notes",
        }
        extra_roles = [c for c in rows[0] if c and c not in known]
    if missing_roles:
        problems.append(f"missing role column(s): {missing_roles}")
    if extra_roles:
        problems.append(f"unrecognised column(s), possibly a stray role: {extra_roles}")

    # ---- 2. vocabulary ----------------------------------------------------
    named = [(r.get("information_type") or "").strip() for r in rows]
    named = [n for n in named if n]
    unknown = sorted({n for n in named if n not in VOCAB})
    absent = sorted(set(TYPE_NAMES) - set(named))
    dupes = sorted({n for n, c in Counter(named).items() if c > 1})
    if unknown:
        problems.append(f"type(s) not in frozen vocabulary v{VOCAB_VERSION}: {unknown}")
    if absent:
        problems.append(f"vocabulary type(s) absent from the template: {absent}")
    if dupes:
        problems.append(f"duplicate row(s) for type(s): {dupes}")

    # ---- 1. completeness --------------------------------------------------
    permissions: dict[str, set[str]] = {r: set() for r in ROLES}
    blanks: list[tuple[str, str]] = []
    invalid: list[tuple[str, str, str]] = []
    decisions: dict[str, dict[str, str]] = {}

    for row in rows:
        t = (row.get("information_type") or "").strip()
        if not t or t not in VOCAB:
            continue
        decisions[t] = {}
        for role in header_roles:
            value = normalize(row.get(role))
            if value is None:
                blanks.append((t, role))
            elif value == "__invalid__":
                invalid.append((t, role, (row.get(role) or "").strip()))
            else:
                decisions[t][role] = value
                if value == "permit":
                    permissions[role].add(t)

    if blanks:
        problems.append(f"{len(blanks)} blank cell(s)")
    if invalid:
        problems.append(f"{len(invalid)} unrecognised value(s)")

    # ---- 4. surfaced shapes ----------------------------------------------
    permitted_to_none = sorted(
        t for t in TYPE_NAMES
        if t in decisions and not any(v == "permit" for v in decisions[t].values()))
    permitted_to_all = sorted(
        t for t in TYPE_NAMES
        if t in decisions and decisions[t]
        and all(v == "permit" for v in decisions[t].values())
        and len(decisions[t]) == len(ROLES))

    impact = {}
    if IMPACT_JSON.exists():
        impact = {e["information_type"]: e
                  for e in json.loads(IMPACT_JSON.read_text(encoding="utf-8"))["types"]}

    ok = not problems

    report = {
        "artifact":        "stage2a_validation_report",
        "vocab_version":   VOCAB_VERSION,
        "linkage_version": LINKAGE_VERSION,
        "template":        str(args.template).replace("\\", "/"),
        "valid":           ok,
        "cells_expected":  len(TYPE_NAMES) * len(ROLES),
        "cells_authored":  sum(len(v) for v in decisions.values()),
        "checks": {
            "roles":            {"missing": missing_roles, "unrecognised": extra_roles},
            "vocabulary":       {"unknown_types": unknown, "absent_types": absent,
                                 "duplicate_rows": dupes},
            "completeness":     {"blank_cells": [list(b) for b in blanks],
                                 "invalid_values": [list(i) for i in invalid]},
        },
        "surfaced": {
            "note": ("Both shapes are plausible and neither is an error. Reported so "
                     "they are confirmed deliberately rather than discovered in the "
                     "Stage 2b results."),
            "permitted_to_no_role": [
                {"information_type": t,
                 "subject_linked_documents": impact.get(t, {}).get("subject_linked_documents"),
                 "permitted_flows_carrying_it": impact.get(t, {}).get("permitted_flows_carrying_it")}
                for t in permitted_to_none],
            "permitted_to_every_role": [
                {"information_type": t,
                 "subject_linked_documents": impact.get(t, {}).get("subject_linked_documents"),
                 "permitted_flows_carrying_it": impact.get(t, {}).get("permitted_flows_carrying_it")}
                for t in permitted_to_all],
        },
        "problems": problems,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    if ok:
        permissions_path.write_text(json.dumps({
            "artifact":        "stage2_role_permissions",
            "vocab_version":   VOCAB_VERSION,
            "linkage_version": LINKAGE_VERSION,
            "authored_by":     "researcher",
            "provenance": ("Hand-authored against frozen vocabulary v1.2.0. No model "
                           "proposed, ranked, or defaulted any decision; the template "
                           "was delivered with every cell blank."),
            "source_template": str(args.template).replace("\\", "/"),
            "roles": {role: sorted(types) for role, types in permissions.items()},
            "decisions": {t: decisions[t] for t in TYPE_NAMES if t in decisions},
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---- report -----------------------------------------------------------
    print(f"Role permission validation - vocabulary v{VOCAB_VERSION} (frozen)")
    print(f"{args.template}\n")
    print(f"  cells expected : {report['cells_expected']}")
    print(f"  cells authored : {report['cells_authored']}")
    print(f"  status         : {'VALID' if ok else 'NOT VALID'}\n")

    if problems:
        print("Problems")
        print("-" * 62)
        for pr in problems:
            print(f"  - {pr}")
        if blanks:
            print("\n  blank cells (type / role):")
            for t, r in blanks[:40]:
                print(f"      {t:<22} {r}")
            if len(blanks) > 40:
                print(f"      ... and {len(blanks) - 40} more")
        if invalid:
            print("\n  unrecognised values:")
            for t, r, v in invalid[:20]:
                print(f"      {t:<22} {r:<20} {v!r}")
            print(f"\n  accepted: {', '.join(DECISION_VALUES)}")
        print(f"\nNo permission set written. Fix and re-run.")
        print(f"Report: {report_path}")
        raise SystemExit(1)

    print(f"{'role':<22}{'permits':>9}{'denies':>9}   types permitted")
    print("-" * 78)
    for role in ROLES:
        allowed = sorted(permissions[role])
        print(f"  {role:<20}{len(allowed):>9}{len(TYPE_NAMES) - len(allowed):>9}   "
              f"{', '.join(allowed) if allowed else '(none)'}"[:120])

    print(f"\nSurfaced for confirmation - neither is an error")
    print("-" * 62)
    if permitted_to_none:
        print("  permitted to NO role (no flow may carry it):")
        for t in permitted_to_none:
            e = impact.get(t, {})
            print(f"      {t:<22} {e.get('subject_linked_documents','?')} docs, "
                  f"{e.get('permitted_flows_carrying_it','?')} currently-permitted flows")
    else:
        print("  permitted to no role : none")
    if permitted_to_all:
        print("  permitted to EVERY role (the check never fires on it):")
        for t in permitted_to_all:
            e = impact.get(t, {})
            print(f"      {t:<22} {e.get('subject_linked_documents','?')} docs, "
                  f"{e.get('permitted_flows_carrying_it','?')} currently-permitted flows")
    else:
        print("  permitted to every role : none")

    print(f"\nWrote:\n  {permissions_path}\n  {report_path}")
    print("\nReady for Stage 2b.")


if __name__ == "__main__":
    main()
