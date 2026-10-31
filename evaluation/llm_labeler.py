"""
LLM-as-labeler: the professor's original proposal, on solid ground.

Instead of asking the LLM to *decide* each access (LLM-as-judge), we ask it to do
the one-time human job it's being proposed as a substitute for: read a document
and assign its CI label — sensitivity tier and the roles permitted to receive it.
Those LLM labels are then fed into the SAME deterministic gate that scores 100%
on human labels. Any downstream leak is therefore attributable entirely to the
label, not the gate.

The LLM is given the policy vocabulary (the human-defined tiers and roles) and the
document's content and type — but NEVER the ground-truth label fields. That mirrors
a real labeling deployment: humans define the schema, the model fills it in.

Contract:  label_document(record, model) -> dict with the label fields + ok flag
Cache: reports/labeler/<model>.jsonl, keyed by (title, sample) and resumable.

Repeated sampling
-----------------
`samples > 1` re-labels every document N times with an identical request, so any
disagreement across draws is the model's own non-determinism on a fixed input. That
is the quantity the mediator thesis rests on, so it is measured rather than asserted;
see run_variance_eval.py. Records written before sampling existed carry no `sample`
field and are read back as sample 0.

Sampling is controlled differently per provider, and the difference matters:
Opus 4.8 and Sonnet 5 REJECT temperature outright, so there is no knob to turn.
OpenAI chat models accept it and default to 1.0, so we pin them to 0 — variance
that survives that is non-determinism rather than deliberate sampling. The value
actually used is recorded on every label (see providers.sampling_note).
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from evaluation.llm_client import DEFAULT_MODELS
from evaluation.providers import parse_structured, sampling_note

CACHE_DIR = Path("reports/labeler")
MAX_TOKENS = 3072   # must exceed Haiku's 2048 thinking budget
REQUEST_DELAY = 0.3
PARSE_RETRIES = 2
WORKERS = 4         # concurrent requests per model; SDK retries 429/5xx on its own

# The human-defined policy vocabulary the labeler must use.
TIERS = ("public", "internal", "pii_basic", "clinical_standard",
         "clinical_sensitive", "financial", "employment")
ROLES = ("Doctor", "Nurse", "Billing Specialist", "HR Manager", "IT Contractor", "Patient")


class DocLabel(BaseModel):
    sensitivity_tier: Literal[
        "public", "internal", "pii_basic", "clinical_standard",
        "clinical_sensitive", "financial", "employment"]
    permitted_receiver_roles: list[Literal[
        "Doctor", "Nurse", "Billing Specialist", "HR Manager", "IT Contractor", "Patient"]]
    extra_sensitive: bool
    governing_principle: str


SYSTEM_PROMPT = """\
You are a records-classification officer at Riverside Medical Clinic. Your job is to
assign each document its access-control label under the clinic's fixed policy. You do
NOT decide individual access requests — you label the document once, and a
deterministic gate enforces your label thereafter.

SENSITIVITY TIERS (choose exactly one):
- public: no private info; freely shareable (pamphlets, notices).
- internal: org-internal, not private, not public (schedules, agendas, policy memos).
- pii_basic: identifiers only (name, DOB, address) with no clinical/financial content.
- clinical_standard: diagnoses, medications, clinical history.
- clinical_sensitive: mental health, substance use, HIV/AIDS, reproductive care.
- financial: billing codes, insurance numbers, salary figures.
- employment: employment contracts, HR records, performance reviews, credentialing.

ROLES that may be permitted to receive a document (list ALL that legitimately apply):
- Doctor, Nurse: clinical care staff.
- Billing Specialist: billing/insurance operations only.
- HR Manager: employment/HR records only.
- IT Contractor: no access to protected health information.
- Patient: the individual; may receive public materials.

Guidance: grant the MINIMUM necessary roles. Clinical records go to clinical staff;
financial records to billing; employment records to HR. Mental-health / substance-use /
HIV records are extra-sensitive and restricted to Doctor only. Mark extra_sensitive
true for those categories.

Return the label as structured output."""


def build_prompt(record: dict) -> str:
    subj = record.get("subject_name") or "organization-level (no individual subject)"
    return f"""\
Classify this clinic document.

Title        : {record['title']}
Document type : {record['document_type']}
Subject       : {subj}

--- DOCUMENT CONTENT ---
{record.get('content', '')}
--- END CONTENT ---

Assign the sensitivity tier, the full set of permitted receiver roles, whether it is
extra-sensitive, and the governing principle."""


def label_document(record: dict, model: str, sample: int = 0) -> dict:
    prompt = build_prompt(record)
    last_err = ""
    for attempt in range(1, PARSE_RETRIES + 2):
        try:
            lab, err = parse_structured(model, SYSTEM_PROMPT, prompt, DocLabel, MAX_TOKENS)
            if lab is None:
                last_err = err or "unparseable"; continue
            return {
                "title": record["title"],
                "model": model,
                "sample": sample,
                "sensitivity_tier": lab.sensitivity_tier,
                "permitted_receiver_roles": lab.permitted_receiver_roles,
                "extra_sensitive": lab.extra_sensitive,
                "governing_principle": lab.governing_principle,
                "ok": True,
                **sampling_note(model),
            }
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            if attempt <= PARSE_RETRIES:
                time.sleep(2 * attempt)
    return {"title": record["title"], "model": model, "sample": sample,
            "ok": False, "error": last_err}


# ---- cache (resumable, successes only) ------------------------------------

def cache_path(model: str) -> Path:
    # Model ids may carry ':' or '/' (fine-tunes, versioned names) which Windows
    # rejects in filenames. Existing Anthropic caches are unaffected.
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
    return CACHE_DIR / f"{safe}.jsonl"


def _read_records(model: str) -> list[dict]:
    """Every cached label line for `model`, oldest first. `sample` defaults to 0."""
    p = cache_path(model)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            r.setdefault("sample", 0)
            out.append(r)
    return out


def load_cached(model: str) -> dict[str, dict]:
    """
    title -> label, for sample 0 only. This is the single-draw view the headline
    experiment (run_labeler_eval) and the figures scored against before repeated
    sampling existed, so those results stay reproducible as samples accumulate.
    """
    return {r["title"]: r for r in _read_records(model) if r.get("sample", 0) == 0}


def load_all_samples(model: str) -> dict[str, list[dict]]:
    """title -> [label per draw], ordered by sample index. Used by run_variance_eval."""
    out: dict[str, list[dict]] = {}
    for r in _read_records(model):
        out.setdefault(r["title"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r.get("sample", 0))
    return out


def run_labeler(model: str, records: list[dict], limit: int | None = None,
                samples: int = 1, workers: int = WORKERS) -> dict[str, dict]:
    """
    Label every document `samples` times, skipping (title, sample) pairs already
    cached. Returns the sample-0 view for backwards compatibility; use
    load_all_samples(model) for the full set of draws.

    Calls are issued from a small thread pool — each is an independent request
    with no shared state, and the SDK already retries 429/5xx with backoff. Cache
    writes are serialized behind a lock so the JSONL stays one-record-per-line.
    """
    have = {(r["title"], r.get("sample", 0)) for r in _read_records(model) if r.get("ok", True)}
    todo = records if limit is None else records[:limit]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    pending = [(rec, k) for k in range(samples) for rec in todo
               if (rec["title"], k) not in have]
    if not pending:
        print(f"  [{model}] nothing to do — {len(have)} labels already cached")
        return load_cached(model)

    lock = threading.Lock()
    done = n_err = 0

    def work(item: tuple[dict, int]) -> None:
        nonlocal done, n_err
        rec, k = item
        res = label_document(rec, model, sample=k)
        with lock:
            done += 1
            if res["ok"]:
                with open(cache_path(model), "a", encoding="utf-8") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
                tier = res["sensitivity_tier"]
            else:
                n_err += 1
                tier = f"ERROR {res.get('error','')[:40]}"
            print(f"  [{model}] s{k} {done:>4}/{len(pending)} "
                  f"{rec['title'][:42]:<42} -> {tier}", flush=True)
        time.sleep(REQUEST_DELAY)

    print(f"  [{model}] {len(pending)} calls to make ({len(have)} cached), "
          f"{workers} workers")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, pending))

    total = len({(r["title"], r.get("sample", 0))
                 for r in _read_records(model) if r.get("ok", True)})
    print(f"  [{model}] done: {total} labels across {samples} sample(s) "
          f"({len(pending)} new calls, {n_err} errors)")
    return load_cached(model)
