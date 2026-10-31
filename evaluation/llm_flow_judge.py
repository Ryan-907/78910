"""
LLM-as-HIPAA-judge over the PrivaCI HIPAA flows.

Each flow (data/hipaa_flows.json) is shown to a model as its CI 5-tuple plus the
case narrative — WITHOUT the ground-truth label or the governing articles. The
model returns one of {permit, prohibit, not applicable}. Scoring against the
regulation-derived `norm_type` happens in run_flow_judge_eval.py.

This arm is JUDGE-ONLY and deliberately contains no gate. Its question is narrow:
on real court-adjudicated cases, does the model reproduce the legally-correct
access decision, and when it errs on a should-deny flow, what is the pattern?

The deterministic gate is NOT scored against this corpus. Doing so would compare
an architecture against one hand-authored policy — a category error; the gate is
faithful to its policy by construction, so a wrong decision is a defect in the
policy, not evidence about the architecture. (See retired/README.md.) This corpus
serves one purpose here: it is the only place in the project where the label
authority is a court rather than the author.

Models compared default to a capability ladder (Opus 4.8 / Sonnet 5 / Haiku 4.5).
Results are cached per (model, flow_id) so runs resume and never re-bill a flow.
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

CACHE_DIR = Path("reports/flow_judge")
MAX_TOKENS = 3072
REQUEST_DELAY = 0.3          # courtesy pause between successful calls
PARSE_RETRIES = 2            # retries on refusal / unparseable output (SDK already retries 429/5xx)
WORKERS = 4                  # concurrent requests per model; SDK retries 429/5xx on its own

LABELS = ("permit", "prohibit", "not applicable")


class FlowDecision(BaseModel):
    """Structured verdict the model must return."""
    decision: Literal["permit", "prohibit", "not applicable"]
    rationale: str


SYSTEM_PROMPT = """\
You are an expert on the U.S. HIPAA Privacy Rule (45 CFR Part 160 and Subparts A \
and E of Part 164). You will be shown a real-world information flow: who disclosed \
what health information to whom, for what purpose, and under what consent. Decide \
how the HIPAA Privacy Rule applies to THIS disclosure and return exactly one label:

- "permit": HIPAA affirmatively permits this disclosure — a provision allows it \
(with or without individual authorization).
- "prohibit": HIPAA prohibits this disclosure as described — it violates the \
Privacy Rule.
- "not applicable": HIPAA does not govern this flow — e.g. the sender is not a \
covered entity or business associate, or the information is not protected health \
information.

Decide only from the flow described. Do not assume facts that are not stated. \
Give a one- to three-sentence rationale naming the relevant HIPAA principle."""


def build_user_prompt(record: dict) -> str:
    consent = (record.get("consent_form") or "").strip() or "none stated"
    return f"""\
Information flow under review:

Sender (role)     : {record['sender']}  [{record.get('sender_role', '')}]
Recipient (role)  : {record['receiver']}  [{record.get('receiver_role', '')}]
Subject (role)    : {record['subject']}  [{record.get('subject_role', '')}]
Information type  : {record['message_type']}
Purpose           : {record.get('transmission_principle', '')}
Consent           : {consent}

Case narrative:
{record.get('case_content', '')}

How does the HIPAA Privacy Rule apply to this disclosure?"""


def judge_flow(record: dict, model: str) -> dict:
    """
    Ask `model` to classify one flow. Returns a result dict:
      {flow_id, model, decision, rationale, ok, error?}
    `decision` is one of LABELS on success, or "error" if the model could not
    produce a parseable verdict.
    """
    user_prompt = build_user_prompt(record)
    last_err = ""

    for attempt in range(1, PARSE_RETRIES + 2):
        try:
            verdict, err = parse_structured(
                model, SYSTEM_PROMPT, user_prompt, FlowDecision, MAX_TOKENS)
            if verdict is None:
                last_err = err or "unparseable"
                continue

            return {
                "flow_id":   record["flow_id"],
                "model":     model,
                "decision":  verdict.decision,
                "rationale": verdict.rationale,
                "ok":        True,
                **sampling_note(model),
            }
        except Exception as e:  # noqa: BLE001 — record and retry/emit
            last_err = f"{type(e).__name__}: {e}"
            if attempt <= PARSE_RETRIES:
                time.sleep(2 * attempt)

    return {
        "flow_id":  record["flow_id"],
        "model":    model,
        "decision": "error",
        "rationale": "",
        "ok":       False,
        "error":    last_err,
    }


# ---------------------------------------------------------------------------
# Cache helpers — one JSONL per model, keyed by flow_id (resumable, no re-billing)
# ---------------------------------------------------------------------------

def cache_path(model: str) -> Path:
    # Model ids may carry ':' or '/' which Windows rejects in filenames. Existing
    # Anthropic caches contain none of these and so keep their current paths.
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
    return CACHE_DIR / f"{safe}.jsonl"


def load_cached(model: str) -> dict[str, dict]:
    path = cache_path(model)
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["flow_id"]] = rec
    return out


def append_cached(model: str, result: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path(model), "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def run_model_over_flows(model: str, records: list[dict], limit: int | None = None,
                         workers: int = WORKERS) -> list[dict]:
    """
    Judge every flow with `model`, skipping any already cached. Returns the full
    result list (cached + new) for the flows considered.

    Calls are issued from a small thread pool — each is an independent request with
    no shared state — and cache writes are serialized behind a lock so the JSONL
    stays one record per line.
    """
    cached = load_cached(model)
    todo = records if limit is None else records[:limit]
    pending = [r for r in todo if r["flow_id"] not in cached]

    if not pending:
        print(f"  [{model}] nothing to do — {len(todo)} flows already cached")
        return [cached[r["flow_id"]] for r in todo]

    lock = threading.Lock()
    fresh: dict[str, dict] = {}
    done = 0

    def work(record: dict) -> None:
        nonlocal done
        result = judge_flow(record, model)
        with lock:
            done += 1
            if result["ok"]:
                append_cached(model, result)  # only cache successes — errors retry next run
            fresh[record["flow_id"]] = result
            flag = "" if result["ok"] else f"  [ERROR: {result.get('error', '')[:60]}]"
            print(f"  [{model}] {done:>3}/{len(pending)} {record['flow_id']} "
                  f"-> {result['decision']}{flag}", flush=True)
        time.sleep(REQUEST_DELAY)

    print(f"  [{model}] {len(pending)} calls to make ({len(cached)} cached), "
          f"{workers} workers")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, pending))

    results = [cached.get(r["flow_id"]) or fresh[r["flow_id"]] for r in todo]
    print(f"  [{model}] done: {len(results)} flows ({len(pending)} new API calls, "
          f"{len(results) - len(pending)} from cache)")
    return results
