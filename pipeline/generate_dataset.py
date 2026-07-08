"""
Riverside Medical Clinic — Dataset Generation Pipeline

Iterates over ALL_SPECS, calls Claude to generate realistic document
content for each spec, and writes the results to dataset.json.

Each output record is a flat dict combining the spec (ground-truth CI
label) with the generated content and extracted attribute values.

Usage
-----
    python generate_dataset.py

Requires
--------
    ANTHROPIC_API_KEY environment variable (or .env file)
    pip install anthropic python-dotenv

Resume behaviour
----------------
If dataset.json already exists, specs whose titles are already present
are skipped. Re-run freely after interruptions.

Output schema (per record)
--------------------------
{
  "title":                   str,
  "document_type":           str,
  "originating_context":     str,
  "subject_type":            str,
  "subject_name":            str | null,
  "date":                    str,
  "sensitivity_tier":        str,
  "extra_sensitive":         bool,
  "extra_sensitive_reason":  str | null,
  "pii_attributes":          list[str],
  "implied_attributes":      list[str],
  "permitted_receiver_roles":list[str],
  "assignment_required":     bool,
  "governing_principle":     str | null,
  "attributes":              list[{"information_type": str, "attribute": str}],
  "content":                 str,
  "generation_warnings":     list[str]
}
"""

import json
import os
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

from world.agents_pool import EXTENDED_NAME_REGISTRY, clinic_system
from pipeline.doc_specs import ALL_SPECS

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL          = "claude-sonnet-4-6"
OUTPUT_PATH    = Path("data/dataset.json")
RETRY_LIMIT    = 3
RETRY_DELAY    = 5   # seconds between retries
REQUEST_DELAY  = 0.5 # seconds between successful requests (rate-limit courtesy)

client = anthropic.Anthropic(timeout=45.0, max_retries=0)

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a document generation assistant for Riverside Medical Clinic, a fictional medical facility used for privacy research. Your task is to generate realistic, professional clinic documents based on specifications provided.

Guidelines:
- Keep documents SHORT (150-250 words). This is for research, not production.
- Match the tone and format of real medical, billing, or HR documents
- Include specific values: exact ICD-10 codes, medication doses, dollar amounts, dates
- Every labeled pii_attribute MUST appear verbatim as a value in the attributes list
- For clinical documents: one brief SOAP note or summary — no lengthy narratives
- For billing documents: key line items only
- For HR documents: essential terms only, no boilerplate

You must return a JSON object with exactly two fields:
{
  "content": "<full document text as a single string with \\n for newlines>",
  "attributes": [{"information_type": "<AttributeType constant>", "attribute": "<exact value as it appears in the content>"}]
}

The attributes list must contain one entry per sensitive value in the document, using the exact string that appears in the content. Do not include values not present in the content.\
"""

def _subject_context(spec: dict) -> str:
    """Build a description of the subject for the generation prompt."""
    name = spec.get("subject_name")
    if not name:
        return "Subject: Riverside Medical Clinic (organizational document — no individual subject)"
    agent = EXTENDED_NAME_REGISTRY.get(name)
    if not agent:
        return f"Subject: {name} (details not in registry)"
    lines = [f"Subject: {name}"]
    role = getattr(agent, "role", None)
    if role:
        lines.append(f"Role: {role.role} ({role.context})")
    for attr in agent.attributes:
        lines.append(f"  {attr.information_type}: {attr.attribute}")
    return "\n".join(lines)


def _pii_description(spec: dict) -> str:
    piis = spec.get("pii_attributes", [])
    implied = spec.get("implied_attributes", [])
    lines = []
    if piis:
        lines.append("Explicit sensitive content (must appear):")
        for p in piis:
            lines.append(f"  - {p}")
    if implied:
        lines.append("Implied sensitive content (encoded but not stated directly):")
        for i in implied:
            lines.append(f"  - {i} (e.g. via ICD code or medication name)")
    return "\n".join(lines) if lines else "No sensitive content required."


def build_prompt(spec: dict) -> str:
    extra = ""
    if spec.get("extra_sensitive"):
        reason = spec.get("extra_sensitive_reason") or "extra-sensitive category"
        extra = (f"\nIMPORTANT: This document is EXTRA SENSITIVE ({reason}). "
                 f"Include a prominent confidentiality notice at the top. "
                 f"Use appropriate statutory language (e.g. 42 CFR Part 2 for substance abuse, "
                 f"Illinois MHDDCA for mental health, HIPAA for HIV).\n")

    return f"""\
Generate the following clinic document:

Document Type    : {spec['document_type']}
Document Date    : {spec['date']}
Originating Context: {spec['originating_context']}
Sensitivity Tier : {spec['sensitivity_tier']}
Governing Principle: {spec.get('governing_principle', 'N/A')}
{extra}
{_subject_context(spec)}

{_pii_description(spec)}

Scenario: {spec['scenario_hint']}

Permitted receivers (for your reference only — do not include in the document):
{', '.join(spec.get('permitted_receiver_roles', []))}

Return only the JSON object with "content" and "attributes" fields.\
"""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _derive_title(spec: dict) -> str:
    """Derive a human-readable document title from the spec."""
    dtype = spec["document_type"].replace("_", " ").title()
    subject = spec.get("subject_name") or "Riverside Medical Clinic"
    date = spec.get("date", "")
    return f"{dtype} — {subject}, {date}"


def generate_one(spec: dict) -> dict:
    """Call Claude to generate content for a single spec. Returns the full record."""
    prompt = build_prompt(spec)

    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=800,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()

            # Extract JSON — tolerate markdown fences
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            json_str = raw[start:end] if start != -1 and end > start else raw

            parsed = json.loads(json_str)
            content    = parsed.get("content", "")
            attributes = parsed.get("attributes", [])

            warnings = []
            if not content:
                warnings.append("empty content returned")
            for pii in spec.get("pii_attributes", []):
                matched = any(a.get("information_type") == pii for a in attributes)
                if not matched:
                    warnings.append(f"pii_attribute '{pii}' missing from returned attributes")

            return {
                "title":                    _derive_title(spec),
                "document_type":            spec["document_type"],
                "originating_context":      spec["originating_context"],
                "subject_type":             spec["subject_type"],
                "subject_name":             spec.get("subject_name"),
                "date":                     spec["date"],
                "sensitivity_tier":         spec["sensitivity_tier"],
                "extra_sensitive":          spec.get("extra_sensitive", False),
                "extra_sensitive_reason":   spec.get("extra_sensitive_reason"),
                "pii_attributes":           spec.get("pii_attributes", []),
                "implied_attributes":       spec.get("implied_attributes", []),
                "permitted_receiver_roles": spec.get("permitted_receiver_roles", []),
                "assignment_required":      spec.get("assignment_required", True),
                "governing_principle":      spec.get("governing_principle"),
                "attributes":               attributes,
                "content":                  content,
                "generation_warnings":      warnings,
            }

        except Exception as e:
            if attempt < RETRY_LIMIT:
                print(f"    [attempt {attempt} failed: {type(e).__name__}: {e}] retrying in {RETRY_DELAY}s", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                print(f"    [FAILED after {RETRY_LIMIT} attempts: {type(e).__name__}: {e}]", flush=True)
                return {
                    "title":                    _derive_title(spec),
                    "document_type":            spec["document_type"],
                    "originating_context":      spec["originating_context"],
                    "subject_type":             spec["subject_type"],
                    "subject_name":             spec.get("subject_name"),
                    "date":                     spec["date"],
                    "sensitivity_tier":         spec["sensitivity_tier"],
                    "extra_sensitive":          spec.get("extra_sensitive", False),
                    "extra_sensitive_reason":   spec.get("extra_sensitive_reason"),
                    "pii_attributes":           spec.get("pii_attributes", []),
                    "implied_attributes":       spec.get("implied_attributes", []),
                    "permitted_receiver_roles": spec.get("permitted_receiver_roles", []),
                    "assignment_required":      spec.get("assignment_required", True),
                    "governing_principle":      spec.get("governing_principle"),
                    "attributes":               [],
                    "content":                  "",
                    "generation_warnings":      [f"generation failed: {type(e).__name__}: {e}"],
                }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def load_existing() -> dict[str, dict]:
    """Load already-generated records keyed by title."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            records = json.load(f)
        return {r["title"]: r for r in records}
    return {}


def save(records: dict[str, dict]) -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(list(records.values()), f, indent=2, ensure_ascii=False)


LOG_PATH = Path("logs/generation_log.txt")

def log(msg: str) -> None:
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main() -> None:
    # Clear log for fresh run
    LOG_PATH.write_text("", encoding="utf-8")

    existing = load_existing()
    log(f"Loaded {len(existing)} existing records from {OUTPUT_PATH}")
    log(f"Specs to process: {len(ALL_SPECS)}")
    log(f"Remaining: {len(ALL_SPECS) - len(existing)}\n")

    for i, spec in enumerate(ALL_SPECS, 1):
        title = _derive_title(spec)
        if title in existing:
            log(f"[{i:>3}/{len(ALL_SPECS)}] skip  {title}")
            continue

        log(f"[{i:>3}/{len(ALL_SPECS)}] gen   {title}")
        record = generate_one(spec)
        existing[title] = record

        if record["generation_warnings"]:
            for w in record["generation_warnings"]:
                log(f"    [WARN] {w}")

        save(existing)
        time.sleep(REQUEST_DELAY)

    log(f"\nDone. {len(existing)} records written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
