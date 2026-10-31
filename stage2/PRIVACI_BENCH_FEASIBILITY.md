# PrivaCI-Bench (HIPAA split) — feasibility assessment

**Assessment only. Nothing was run and nothing was built.** The decision is the
author's.

Source examined: `data/hipaa_flows.json` — 214 flows, the same artifact Paper II
used, derived from the GoldCoin HIPAA court cases via PrivaCI-Bench
(HKUST-KnowComp). All figures below come from reading that file, not from the
literature.

---

## 1. The headline finding

**PrivaCI-Bench cannot exercise the Paper III mechanism.** Every one of the 214
flows carries exactly one information type:

```
multiplicity of raw.information_type per flow:  {1: 214}
```

The Stage 2 result is a statement about documents that *bundle* information
types: over-delivery arises because a document admitted on the strength of its
type carries types the recipient may not receive, and unreachability arises when
no admitted role covers the whole bundle. Both are functions of bundle size `k`.
On this corpus `k` ranges 4–11 with mean 7.7. On PrivaCI-Bench `k = 1` for every
flow, and at `k = 1` the derivation in `stage2/generalization.py` degenerates:
the subset test `T ⊆ P(r)` reduces to simple membership, over-delivery from
bundling is structurally impossible, and unreachability reduces to "no admitted
role may receive this one type."

There is also no document layer at all — no `permitted_receiver_roles`, no
sensitivity tier, no assignment relation. Checks 3 and 4 of Algorithm 1 have
nothing to read. What remains testable is check 5 in isolation, which is a
different claim from the one Paper III makes.

**This is not a reason to dismiss the corpus.** It is a reason to be precise
about what running it would demonstrate.

## 2. What it *could* validate

One genuinely valuable thing: **whether the hand-authored role × type permission
sets agree with externally-derived norms.** That addresses the made-up-corpus
objection at the point where it bites hardest — the normative artifact — even
though it leaves the bundling result untested.

That is worth having. It is also a narrower claim than "the fifth check
generalizes," and the write-up would have to say so plainly.

## 3. What maps cleanly

Very little, and the shortfall is structural rather than a matter of effort.

| our field | PrivaCI-Bench counterpart | maps? |
|---|---|---|
| information type (16-entry controlled vocabulary) | `message_type`, **194 distinct free-text strings** over 214 flows, mean 6.1 words | **no** — one-off sentence fragments, e.g. *"Health insurance plan details, including coverage scope and claims experience"* |
| role (6 authored) | `receiver_role`, **140 distinct free-text strings** | **no** — and case-variant duplicates go unnormalised (`Law Enforcement` 8 / `Law enforcement` 7; `Legal Authority` 11 / `Legal authority` 6) |
| subject | `subject` / `subject_role`, free text | partially — subject identity exists but is not resolvable to an agent |
| transmission principle | `transmission_principle` / `purpose` | yes, conceptually |
| ground truth | `expected_permit` | **partially — see §4** |
| document, tier, permitted roles, assignment | — | **absent entirely** |

The role mismatch is the sharper problem. The top receiver roles are *Legal
Authority*, *Law Enforcement*, *Government agency*, *Legal Representative*,
*Defendant*. Only *Health care providers* (2 flows) resembles anything in our
six. Our vocabulary of roles is a clinic's internal staff; PrivaCI-Bench's is the
set of external parties a court had reason to rule about. They are not the same
population, and mapping one onto the other is not a normalisation task — it is a
fresh normative judgement about who counts as what.

## 4. The ground-truth label is thinner than 214 suggests

```
expected_permit:  None 107   True 87   False 20
norm_type:        not applicable 107   permit 87   prohibit 20
```

**Only 107 of 214 flows carry a usable label**, and of those only **20 are
negative**. Any conformance figure computed against this split rests on 20
prohibitions. That is enough to be suggestive and not enough to be a headline,
and it is worth knowing before rather than after.

## 5. Effort, honestly

The work is not large in engineering terms and is substantial in authorship
terms — which is the awkward shape, because the authorship is the part that
cannot be delegated.

| task | scale | who can do it |
|---|---|---|
| Load and normalise the 214 flows | trivial; already parsed in this repo | code |
| Map 194 free-text `message_type` strings → 16 vocabulary entries | 214 judgements | **author only** |
| Map 140 free-text `receiver_role` strings → 6 roles | 140 judgements, most with no honest target | **author only** |
| Decide what to do with unmappable flows | policy decision | **author only** |
| Run check 5 and score against `expected_permit` | trivial | code |
| Write up | — | — |

An indicative lexical probe — cue words only, no judgement about any flow — finds
**137 of 214 (64%) contain no surface cue for any of the 16 types**. That is a
rough upper bound on how much of the corpus is out of vocabulary, not a mapping;
the true figure could be better or worse once read properly. But it signals that a
majority of flows may have no honest target in a vocabulary that is **frozen** and
that Stage 2's permission sets are already authored against.

That is the trap to see coming. The two ways out are both costly:

- **Extend the vocabulary** to cover PrivaCI-Bench's types — which unfreezes
  v1.2.0 and forces re-authoring all 96 permission cells, invalidating the Stage 2
  measurements as they stand.
- **Restrict to the mappable subset** — perhaps 60–75 flows before the
  `expected_permit` filter, fewer after, with very few negatives — and report a
  conformance figure on a sample selected by our own ability to map it, which is
  a selection effect that would need stating prominently.

Neither is fatal. Both need deciding in advance, because the choice determines
what the resulting number means.

## 6. The mapping is itself a normative act

The load-bearing point. Deciding that *"Health insurance plan details, including
coverage scope and claims experience"* is `insurance_info` rather than
`billing_code`, or that *"Legal Authority"* is closer to `HR Manager` than to any
clinical role, is not data cleaning. It is the same kind of judgement the Stage 2
permission sets required, and Paper II's finding applies to it with equal force: a
model cannot author it.

So the external corpus does not remove the authorship burden — it **relocates and
roughly doubles** it. The permission sets took 96 decisions. This would take
~350 more, on material with no clinic context to anchor them, and every one of
them sits between the external ground truth and our result. An unfavourable
conformance figure could then always be attributed to the mapping rather than to
the policy, and a favourable one would be open to the same charge in reverse.

## 7. Recommendation for the decision

Three options, stated without preference:

1. **Don't run it.** Cite PrivaCI-Bench in related work, state plainly that the
   bundling mechanism it would need to test is absent from it (`k = 1` for all
   214 flows), and rest generalization on the derivation in
   `stage2/generalization.py`, which predicts the observed 67 unreachable
   documents to within one document under a null model that randomises bundle
   contents. Cheapest, and defensible as long as the `k = 1` fact is stated.

2. **Run it as a permission-set validation only**, scoped and labelled as such:
   not a test of the fifth check, but a check that the authored role × type norms
   agree with court-derived ones where both have an opinion. Requires the ~350
   mapping decisions and a pre-registered rule for unmappable flows.

3. **Find or construct a document-level external corpus.** The only option that
   tests the actual mechanism, and by far the most expensive. Worth noting that
   the property needed is narrow — documents with multiple typed attributes and
   role-scoped release rules — so a clinical-records benchmark may serve better
   than a CI benchmark.

**The one thing to avoid** is running option 2 and presenting it as option 3.
The `k = 1` finding makes that distinction easy to state and easy to lose.

---

*Assessed from `data/hipaa_flows.json` on the Stage 2 artifact set. No experiment
was run; no mapping was produced; no code was written for this corpus.*
