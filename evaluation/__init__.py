"""
The live experimental track — two arms.

ARM 1 — LLM-as-labeler, 2,520-flow synthetic clinic corpus (internal ground truth)
  eval_flows.py         flow taxonomy (F1-F6); builds 2,520 (requester, document) flows
  run_gate_eval.py      enforcement invariant: gate applies policy P to labels L faithfully
  llm_labeler.py        LLM assigns document CI labels (tier, permitted roles, extra-sensitive)
  run_labeler_eval.py   LLM labels -> same gate -> induced violations, attributed to label field

ARM 2 — LLM-as-judge, 214 real HIPAA court cases (external ground truth)
  hipaa_flows.py        PrivaCI-Bench / GoldCoin loader
  llm_flow_judge.py     model decides permit/prohibit/not-applicable per flow
  run_flow_judge_eval.py  scored against court-derived norm_type

  The gate is deliberately ABSENT from arm 2. Scoring it there compares an
  architecture against one hand-authored policy — see retired/README.md.

  llm_client.py       shared Anthropic client + model ladder (both arms)
  make_figures.py     publication figures (fig1-3 arm 1, fig4-5 arm 2)

Retired experiments live in retired/ — see retired/README.md.
"""
