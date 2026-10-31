# Retired experiments

Nothing here is deleted — it is parked out of the live path so the active
analysis stays legible. The live experiment is scoped to the **2,520-flow clinic
corpus** (105 documents x 24 agents) and to exactly two systems: the
deterministic gate and the LLMs that label documents for it.

## Why each block was retired

### `evaluation/` — the gate-vs-LLM comparison (NOT the whole HIPAA arm)
`hipaa_gate.py`, `run_gate_vs_llm.py` (+ `reports/gate_vs_llm_report.json`)

`hipaa_gate.gate_decision` was a regex policy hand-authored over PrivaCI's
free-text fields. Scoring it for *accuracy* against court-derived ground truth
and tabling that against LLM judges was a **category error**: it compares an
architecture against one particular hand-written policy. Under the thesis as
stated, the gate is faithful to P by construction — a wrong decision is a defect
in P, not evidence about the architecture. That table could only ever mislead.

**Only the gate side is retired.** The LLM-as-judge arm over the same 214 flows
(`hipaa_flows.py`, `llm_flow_judge.py`, `run_flow_judge_eval.py`,
`data/hipaa_flows.json`, `reports/flow_judge*`) is **live** — it is the only
place in the project where the label authority is a court rather than the
author. It is judge-only; the gate does not appear in it.

Caveat carried into the live arm: only 20 flows are `prohibit`, so leak-rate
differences between models (5 / 2 / 4) are not statistically separable. Report
direction, not ranking.

### `evaluation/` — 29-flow leakage / ablation arm
`leakage.py`, `run_leakage_eval.py`, `rescore_leakage.py`, `run_ablation.py`
(+ `reports/leakage_report.json`, `reports/ablation_report.json`)

A small end-to-end simulation: 29 denied flows, checking whether the LLM's prose
still leaked the withheld value. Result was 0/29 leaked with the gate vs 20/29
(69%) disclosed without it. A real finding, but at n=29 it is an anecdote next to
the 2,520-flow corpus, and it measures a different thing (model utterance, not
label quality). Retired for scope, not because it is wrong.

### `reporting/`
`simulation_report.py`, `visualize_results.py` (+ `reports/simulation_report.json`,
`figures/fig1_flow_distribution` … `fig6_ablation_comparison`)

Both read `leakage_report.json`, so they died with the 29-flow arm. Their figure
role is superseded by `evaluation/make_figures.py`.

### `legacy/`
`main.py`, `run_test.py`, `test_document_flows.py`, `documents.py` — the
pre-`agents_pool` clinic simulation. Imported `evaluation.leakage`; superseded by
the `pipeline/` + `evaluation/` track.

### `figures/`
`fig2_llm_judge_metrics.png`, `fig3_confusion_matrices.png` came from the HIPAA
judge arm. The rest came from `visualize_results.py`. Live figures renumbered to
fig1–fig3 in `reports/figures/`.

## One consequence to be aware of

Retiring the HIPAA arm removes the only **external** ground truth from the live
path. What remains is scored against human-authored labels in a synthetic corpus
— which is the correct baseline for "does the LLM reproduce the human's label,"
but means the *policy itself* is no longer independently validated. That is a
limitation to state explicitly rather than a bug to fix here.
