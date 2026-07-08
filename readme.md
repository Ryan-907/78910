# CI-Sim: Contextual Integrity in an LLM Agentic System

A research simulation applying **Contextual Integrity (CI)** theory to LLM-based document retrieval. The system models a medical clinic — Riverside Medical Clinic — where an LLM acts as a document-retrieval assistant, and a deterministic CI policy gate sits inside the retrieval tool, between the model and the record store. The gate decides which information flows are appropriate without the LLM itself reasoning about privacy.

The core idea: the LLM is treated as **trust-equivalent to the human requester**, never more. If a flow would be inappropriate for the requester to receive directly, the model never receives it either — confidentiality becomes a structural property of the retrieval channel, independent of the model's alignment.

The codebase has two tracks:
- **Document-level track** (`pipeline/`, `evaluation/`, `reporting/`) — the current system. Uses Claude to generate a labeled document corpus and Claude (or any tool-calling model) as the retrieval agent. This is where all current results come from.
- **Legacy attribute-level track** (`legacy/`) — an earlier prototype using a single local Llama-3.1-8B model and a simpler `lookup_attribute()` tool. Superseded; kept for reference only.

---

## Theoretical Background

Contextual Integrity, introduced by Helen Nissenbaum and formalized by Barth et al. (2006), defines privacy not as secrecy but as **appropriate information flow**. A flow is appropriate when it matches the norms of the context in which the information originated.

For example, a patient's diagnosis shared with their treating physician under doctor-patient confidentiality is appropriate. That same diagnosis shared with a billing specialist is not — even if both are employees of the same clinic — because it violates the norms of the medical context.

The key insight this project exploits: the LLM does not need to reason about privacy. By treating the LLM as an **untrusted requester** and gating the retrieval tool with CI logic, the system enforces privacy at the infrastructure level regardless of what the model asks for or how it's prompted.

---

## Current Status

| Experiment | Result | Report |
|---|---|---|
| Dataset generation | 105 documents, 21 document types, 7 sensitivity tiers, 24 agents | `data/dataset.json` |
| Dataset validation | 0 consistency/content issues, 28 minor attribute-extraction issues | `reports/validation_report.json` |
| Gate verification | 2,520/2,520 (agent × document) flows match the CI spec exactly (0 FP, 0 FN) | `reports/gate_accuracy_report.json` |
| LLM leakage (gate active) | 0/29 sampled denied flows leaked restricted content | `reports/leakage_report.json` |
| Ablation (gate removed) | 20/29 (69.0%) of the same flows disclosed restricted content | `reports/ablation_report.json` |

The gate-verification number is **not** an accuracy claim — the ground-truth labels in `evaluation/eval_flows.py` are generated from the same role/assignment logic the gate itself enforces, so 100% is true by construction. It should be read as *implementation verification* (the policy engine faithfully implements its own spec), not as an experimental result. The genuinely experimental numbers are the leakage/ablation pair.

Combined view: `reports/simulation_report.json` and `reports/figures/fig1`–`fig6`.

---

## Architecture

```
pipeline/doc_specs.py          ~105-entry spec matrix (CI ground-truth labels)
        │
        ▼
pipeline/generate_dataset.py   calls Claude per spec → content + attributes
        │
        ▼
data/dataset.json              the generated corpus
        │
        ├──▶ pipeline/normalize_dataset.py   canonicalize attribute-type spelling
        └──▶ pipeline/validate_dataset.py    coverage / consistency / content checks
        │
        ▼
evaluation/eval_flows.py       builds all (agent × document) flows, F1–F6 taxonomy
        │
        ├──▶ evaluation/run_gate_eval.py      deterministic gate check (no LLM)
        │
        └──▶ evaluation/run_leakage_eval.py   samples denied flows, drives an LLM
                    │                          via tool use with the gate active
                    ▼
             evaluation/run_ablation.py       same flows, gate removed — baseline
                    │
                    ▼
             evaluation/rescore_leakage.py    re-applies leakage checkers to stored
                                               responses without new API calls
        │
        ▼
reports/*.json
        │
        ▼
reporting/simulation_report.py   merges gate + leakage reports
reporting/visualize_results.py   → reports/figures/*.png
```

The gate itself (`core/ci_policy.py::evaluate_document_flow`) sits inside the tool-call handling in `run_leakage_eval.py` / `run_ablation.py`: when the model calls `retrieve_document`, the gate evaluates the flow first, and the model receives either the document content or `"[CI DENIED: <reason>]"` — never the reason it was denied beyond that string, and never the raw data if denied.

---

## Package Reference

### `core/` — data model and policy engine (the backbone)

- **`Agent.py`** — `Attribute` (a `(information_type, value)` pair), `Role` (`role` + `context`), `KnowledgeState` (what one agent knows about another, and under what `transmission_principle`), `Agent`/`Employee`/`Patient`/`Contractor`, `Document`/`DocumentLabel` (sensitivity tier, originating context, permitted receiver roles, governing principle), `SensitivityTier`, `DocumentType`, `TransmissionPrinciple`. Every other package imports from here.
- **`ci_policy.py`** — the CI gate. `evaluate_flow()` (attribute-level, used by the legacy track) and `evaluate_document_flow()` (document-level, used by the current track) both do a two-level check: (1) does the receiver's role have blanket permission for this attribute/document type, then (2) is the receiver explicitly assigned to this subject via their `knowledge_base`. Also defines the policy tables (`ROLE_ATTRIBUTE_PERMISSIONS`, `ASSIGNMENT_REQUIRED`, `EXTRA_SENSITIVE`, `ATTRIBUTE_IMPLICATIONS`) and `derived_attributes()`, which surfaces information one attribute implies about another (e.g. an ICD billing code implies a diagnosis).

### `world/` — the simulated clinic population

- **`clinic.py`** — the original 11-agent roster (4 patients, 6 employees, 1 contractor), each with realistic attributes and knowledge-base entries reflecting real access norms. `NAME_REGISTRY`.
- **`agents_pool.py`** — extends `clinic.py` to 24 agents (more conditions, roles, and edge cases) for dataset-scale generation. `EXTENDED_NAME_REGISTRY`, `EXTENDED_ALL_AGENTS`.

### `pipeline/` — dataset generation and QA

- **`doc_specs.py`** — `ALL_SPECS`: one entry per document to generate, each carrying its CI ground-truth label (tier, context, permitted roles, PII/implied attributes) *before* any content exists.
- **`generate_dataset.py`** — calls Claude per spec to produce realistic document content + extracted attributes → `data/dataset.json`. Resumable (skips specs already present).
- **`preflight.py`** — a one-call smoke test to check imports and output format before committing to a full generation run. **Note:** this script has no `if __name__ == "__main__":` guard — importing it executes a live API call.
- **`normalize_dataset.py`** — the generation model returned attribute-type names in three different casing conventions; this canonicalizes them in place.
- **`validate_dataset.py`** — coverage (tier/type/subject distribution), consistency, content, and attribute-extraction checks → `reports/validation_report.json`.

### `evaluation/` — the current experimental track

- **`eval_flows.py`** — builds every (agent × document) flow and classifies it into the F1–F6 taxonomy below. This is the ground-truth source for gate verification, so its logic overlaps with the gate's own logic — see the caveat under Current Status.
- **`leakage.py`** — shared checkers: L1 (verbatim 4-gram match against document content), L2 (sensitive attribute values from the agent registry), L2-doc (sensitive attribute values from the document's own extracted attributes — catches paraphrased disclosures L1 misses). All exclude boilerplate and text already present in the requester's own message.
- **`run_gate_eval.py`** — runs the gate on all 2,520 flows, no LLM calls, computes TP/FP/TN/FN and accuracy/precision/recall/FPR/FNR.
- **`run_leakage_eval.py`** — stratified sample of denied flows (capped at `SAMPLE_SIZE = 40`, one per unique flow-type × tier × role cell — 29 in the current run), presented to an LLM via tool use with the gate active; checks whether the model's final response leaks content anyway.
- **`run_ablation.py`** — the identical sampled flows, gate removed, tool returns full content unconditionally — establishes the naive disclosure baseline.
- **`rescore_leakage.py`** — re-applies the leakage checkers to already-stored LLM responses. No new API calls; use this whenever the checker logic changes.

**Flow taxonomy (F1–F6):**

| Type | Meaning | Expected |
|---|---|---|
| F1 | Authorized access — right role, assigned to subject | PERMIT |
| F2 | Wrong role for the document type | DENY |
| F3 | Right role, wrong patient (no assignment) | DENY |
| F4 | Extra-sensitive escalation (mental health, HIV, SUD) | DENY |
| F5 | Public-tier document | PERMIT |
| F6 | Cross-context (e.g. doctor → HR salary letter) | DENY |

### `legacy/` — superseded attribute-level / local-Llama track

`documents.py` (11 hand-authored fixture documents), `main.py` (original interactive runner — 9 hardcoded scenarios + REPL, local `meta-llama/Llama-3.1-8B-Instruct` via HuggingFace `transformers`), `run_test.py` (6-scenario smoke test), `test_document_flows.py` (document-level version of the same idea). None of these are part of the published results. `main.py` and `run_test.py` require a CUDA GPU and gated HuggingFace access; `torch`/`transformers`/`accelerate` in `requirements.txt` exist only for this track.

### `reporting/` — combines and visualizes `evaluation/` outputs

- **`simulation_report.py`** — merges the gate and leakage reports into one summary, including a `LIMITATIONS` section describing what the metrics do and don't cover.
- **`visualize_results.py`** — matplotlib figures (flow distribution, gate confusion matrix, tier breakdown, leakage results, summary dashboard, ablation comparison) → `reports/figures/`.

---

## Repository Layout

```
core/ world/ pipeline/ evaluation/ legacy/ reporting/   code, by role
data/dataset.json                                       generated corpus (git-ignored)
reports/*.json, reports/figures/*.png                    every evaluation/reporting output
logs/generation_log.txt                                  append-only dataset-generation log
notes/                                                    human-authored write-ups, not generated
pyproject.toml                                            registers the six packages above for
                                                           editable install (see Setup)
```

---

## Setup and Usage

### Prerequisites

- Python 3.10+
- `ANTHROPIC_API_KEY` in a `.env` file at the repo root, for the document-level track (dataset generation, leakage/ablation evaluation)
- CUDA-capable GPU + HuggingFace access to `meta-llama/Llama-3.1-8B-Instruct`, **only** if running the `legacy/` track

### Installation

```bash
pip install -r requirements.txt
pip install -e .        # registers core/world/pipeline/evaluation/legacy/reporting as
                         # importable packages, so `from core.Agent import ...` resolves
                         # no matter which folder a script is run from
```

### Running

All commands are run from the repo root — every script resolves its data/report paths relative to the current working directory, not its own location.

**Generate and validate the dataset** (only needed to regenerate `data/dataset.json` from scratch):
```bash
python pipeline/preflight.py          # one API call, sanity-check output format
python pipeline/generate_dataset.py   # full generation run, resumable
python pipeline/normalize_dataset.py
python pipeline/validate_dataset.py
```

**Run the evaluation pipeline** (uses the existing `data/dataset.json`):
```bash
python evaluation/run_gate_eval.py       # deterministic, no API calls
python evaluation/run_leakage_eval.py    # samples ~40 denied flows, calls Claude
python evaluation/run_ablation.py        # same flows, gate removed
python evaluation/rescore_leakage.py     # re-score stored responses, no API calls
```

**Build the combined report and figures:**
```bash
python reporting/simulation_report.py
python reporting/visualize_results.py
```

**Legacy local-model track** (optional, requires GPU):
```bash
python legacy/run_test.py             # 6-scenario smoke test
python legacy/main.py                 # 9 scenarios + interactive REPL
python legacy/test_document_flows.py  # document-level version, DRY_RUN=True by default
```

---

## Known Limitations / Next Steps

- **Gate verification is circular** (see Current Status) — framed in any write-up as implementation verification, not an accuracy experiment.
- **No prompt-only baseline yet** — the comparison needed to support "structural enforcement beats instructing the model" (gate vs. CI policy given to the model in-prompt with an ungated tool).
- **No adversarial evaluation yet** — all sampled flows are polite, benign requests. The gate's value proposition is robustness under a manipulated model; this hasn't been tested against social engineering, prompt injection in document content, or role impersonation.
- **Small sample, single model** — `run_leakage_eval.py`/`run_ablation.py` currently sample 29 flows on one model (`claude-haiku-4-5`), no confidence intervals.
- **No downstream re-sharing enforcement** — `transmission_principle` is recorded on `KnowledgeState` but nothing currently prevents an authorized receiver from re-sharing what they legitimately received.
