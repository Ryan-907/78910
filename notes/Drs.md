Drs.,
Hope you are well! 
Unfortunately, I have to do some travel for family reasons and cannot make the meeting Monday. I can still work while gone, I just cannot meet. 

That in mind, I wanted to share where the project stands. I have completed the dataset generation and both evaluation phases.

Dataset: 105 synthetic clinical documents across 21 document types and 6 sensitivity tiers, with a pool of 24 simulated agents (patients, physicians, nurses, billing, HR, IT, and external roles). Each document carries Contextual Integrity metadata encoding permitted receivers, transmission principles, and sensitivity flags.

Recall, the core idea is to use a gating mechanism to prevent information leakge based on CI theory.

Gate accuracy: 2,520 (requester, document) pairs evaluated across six CI flow types. The gate correctly classified all flows with zero false positives — no unauthorized access was permitted.

Phase 2 — LLM leakage: 29 sampled denied flows were presented to the LLM via tool use with the gate active. Zero true leakage was detected; the model respected all denials.

Ablation — no-gate baseline: The same 29 flows were run with the gate removed. The LLM disclosed restricted content in 69% of unauthorized requests. This is the finding I think carries the most weight: without the CI gate, the model has no concept of contextual appropriateness and retrieves freely for any requester.

I have attached the graphs here. 

As for what's left, if you are fine with this experiment, I can start writing. The main critique I anticipate has to do with labeling. I have some ideas on how to address that directly in the write-up rather than leaving it as a limitation.

Let me know what you guys think,
thanks.