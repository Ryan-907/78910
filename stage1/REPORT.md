# Paper III — Stage 1: Attribute Inventory and Tagger Audit

Vocabulary v1.0.0 · tagger v1.0.1 · artifacts v1.0.0
Corpus `data/dataset.json`, SHA-256 `49cdd9c89112f605…`, 105 documents.

Stage 1 produces the attribute inventory the eventual fifth gate check will read,
and establishes how far it can be trusted. The gate, the corpus, the labels, and
the assignment relation are unmodified; everything here is new code under
`stage1/` writing to `stage1/artifacts/`.

---

## 1. Vocabulary coverage

### 1.1 The PANOPTICON tagger cannot author this inventory

Two separate problems, the first structural.

**It is a verifier, not a tagger.** `pii_handler.match_pii(og_prompt, pii_values)`
takes a dict of known ground-truth PII values from a PANORAMA-Plus profile and
returns the subset that appears in the text. Its only caller, `fix_pii.py`, joins
on `Unique ID` to fetch that profile first. There is no open-text detection path:
the `email`, `birthday`, and `phone_number` regexes exist to *confirm* a value
already held, never to *find* one. Handed a clinic document, for which no value
dict exists, it returns `{}`. "Run the tagger over all 105 documents" is not an
executable instruction against this code.

**Its category schema has no clinical vocabulary.** The union of the six PANORAMA
pools is 33 categories, drawn from a consumer/social/government profile schema.
Nine map onto this corpus; 24 (Blood Type, Credit Score, Marital Status,
Social Media Handles, Nationality, …) have no referent in a clinic record.

| PANOPTICON category | → vocabulary entry |
|---|---|
| First Name, Last Name | `name` |
| Birth Date | `date_of_birth` |
| Address | `home_address` |
| Annual Salary | `salary` |
| Emergency Contact Name, Emergency Contact Phone | `emergency_contact` |
| Job Title | `job_title` |
| National ID | `ssn` (weak — see below) |

Nine of the sixteen vocabulary entries have **no PANOPTICON category at all**, and
they are exactly the ones carrying the Paper III argument:

> `medical_diagnosis`, `medical_medication`, `medical_history`, `mental_health`,
> `billing_code`, `insurance_info`, `medical_license`, `employment_contract`,
> `contract_terms`

Measured against the authored labels: **89 of 105 documents** carry at least one
authored type PANOPTICON has no category for; only **6** are fully covered.
Nominal coverage of authored (doc, type) pairs is 119/291 = 40.9%, but that is
carried almost entirely by `date_of_birth`, present on 95 of 105 documents.
Excluding it, coverage falls to 24/196 = **12%**.

The `National ID → ssn` mapping is weak even where it maps: `match_pii` compares
National ID by exact alphanumeric token, and every SSN in this corpus is masked
(`XXX-XX-4821`), which no PANORAMA profile value would equal.

**Decision taken:** a new clinic-domain tagger was written under `stage1/`, with
the generation-time `attributes` field brought in as an independent third source.
No PANOPTICON pattern is reused and PANOPTICON's code is not invoked. The mapping
above is preserved in `stage1/vocabulary.py` as a reconciliation record.

### 1.2 The controlled vocabulary

`stage1/vocabulary.py`, **v1.0.0, 16 entries**, versioned and additive-only.

| Family | Entries |
|---|---|
| identity | `name`, `date_of_birth`, `ssn`, `home_address`, `emergency_contact` |
| clinical | `medical_diagnosis`, `medical_medication`, `medical_history`, `mental_health` |
| financial | `billing_code`, `insurance_info` |
| employment | `salary`, `employment_contract`, `contract_terms`, `job_title`, `medical_license` |

It is a strict superset of the 14 `core.Agent.AttributeType` constants, so
`label.pii_attributes` values are valid vocabulary members with no translation
layer — which is what lets Stage 2's role permission sets and this inventory be
compared by plain set inclusion. `name` and `job_title` are the two additions,
both attested in the corpus.

Deliberately excluded, with reasons recorded in the module: `document_type` and
`document_date` (record metadata, not information types about a person); and
standalone `phone`/`email`, whose every corpus occurrence is clinic switchboard
or billing contact information rather than subject PII.

### 1.3 What the Stage 1 tagger cannot detect

One vocabulary entry is flagged undetectable in the general case:

- **`name`** — resolved only against the fixed 24-agent registry plus a titled
  provider pattern (`Dr. Firstname Lastname`). Open-world personal-name detection
  is out of scope for a regex tagger; a name outside the registry is a guaranteed
  miss. Declared in `vocabulary.UNDETECTABLE_BY_STAGE1`.

Every other entry is attempted, at declared confidence: eight rated `high`
(distinctive structural pattern), seven `medium` (dependent on a section heading
or a gazetteer). Two of the 37 rules never fire on this corpus — `license.state`
(subsumed by `license.labeled` here) and `history.status_post` (no `s/p` notation
in the corpus). Both are retained as generalizations, and their silence is
reported by `build_inventory`.

---

## 2. Attribute inventory

`python -m stage1.build_inventory` → `stage1/artifacts/inventory_v1.0.0.{json,csv}`
plus a per-detection CSV. The tagger sees **document content only** — never
`pii_attributes`, the tier, or the subject — so §3 compares two independent
sources rather than one source with itself.

**801 (document, type) pairs across 105 documents; mean 7.63 types per document;
no document tags empty.**

| information type | docs | % | | information type | docs | % |
|---|---:|---:|---|---|---:|---:|
| `date_of_birth` | 95 | 90.5% | | `billing_code` | 65 | 61.9% |
| `name` | 91 | 86.7% | | `job_title` | 62 | 59.0% |
| `home_address` | 85 | 81.0% | | `ssn` | 44 | 41.9% |
| `insurance_info` | 71 | 67.6% | | `medical_license` | 39 | 37.1% |
| `medical_diagnosis` | 70 | 66.7% | | `medical_history` | 27 | 25.7% |
| `medical_medication` | 65 | 61.9% | | `employment_contract` | 23 | 21.9% |
| | | | | `emergency_contact` | 22 | 21.0% |
| | | | | `salary` | 20 | 19.0% |
| | | | | `mental_health` | 19 | 18.1% |
| | | | | `contract_terms` | 3 | 2.9% |

Document identity: the corpus has no id field, so `doc_000`…`doc_104` are minted
from list position and each entry also records a content SHA-256. Reordering or
editing the corpus is therefore detectable rather than silent, and downstream
stages refuse to run against a corpus whose hash has moved.

---

## 3. Reconciliation: extracted vs. authored

`python -m stage1.reconcile` → `reconciliation_v1.0.0.{json,csv}` and a by-type CSV.

Three sources, not two:

| | source | what it is |
|---|---|---|
| **A** | `label.pii_attributes` | the authored spec, hand-written in `pipeline/doc_specs.py` |
| **B** | `stage1/tagger.py` | this stage's extractor, content only |
| **C** | `attributes[].information_type` | returned by the generating model, already value-validated against content by `pipeline/validate_dataset.py` |

C is not ground truth — it came from the same model that wrote the content — but
where B and C agree against A, the finding is not an artifact of the tagger.

### 3.1 Headline

| | |
|---|---:|
| Documents where authored == extracted **exactly** | **0 / 105** (0.0%) |
| Documents with types authored but not found | 10 / 105 |
| Documents with types found but not authored | **105 / 105** |
| Mean Jaccard(authored, extracted) | 0.325 |
| (doc, type) pairs — authored | 291 |
| (doc, type) pairs — extracted | 801 |
| (doc, type) pairs — generation model | 669 |
| **Authored but not found** | **10** |
| **Found but not authored** | **520** |
| — of which corroborated by the generation model | **348** |

The asymmetry is the result. The spec is very nearly satisfied — only 10 of 291
authored pairs go unconfirmed. What the spec does not do is *enumerate*: 520
(document, type) pairs are present in content and claimed by no label, and two
thirds of those are independently corroborated. `pii_attributes` behaves as a
statement of a document's purpose, not an inventory of its contents.

### 3.2 By information type

| type | authored | extracted | generation | A\B | B\A | corroborated |
|---|---:|---:|---:|---:|---:|---:|
| `name` | 0 | 91 | 30 | 0 | **91** | 26 |
| `date_of_birth` | 95 | 95 | 95 | 0 | 0 | 0 |
| `ssn` | 0 | 44 | 51 | 0 | **44** | **44** |
| `home_address` | 8 | 85 | 92 | 0 | **77** | **77** |
| `emergency_contact` | 5 | 22 | 28 | 0 | 17 | 17 |
| `medical_diagnosis` | 39 | 70 | 69 | 1 | 32 | 30 |
| `medical_medication` | 36 | 65 | 64 | 0 | 29 | 28 |
| `medical_history` | 21 | 27 | 38 | 5 | 11 | 10 |
| `mental_health` | 5 | 19 | 9 | 0 | 14 | 4 |
| `billing_code` | 18 | 65 | 70 | 3 | **50** | **49** |
| `insurance_info` | 27 | 71 | 71 | 0 | **44** | **44** |
| `salary` | 11 | 20 | 18 | 1 | 10 | 7 |
| `employment_contract` | 12 | 23 | 8 | 0 | 11 | 0 |
| `contract_terms` | 3 | 3 | 3 | 0 | 0 | 0 |
| `job_title` | 0 | 62 | 4 | 0 | **62** | 4 |
| `medical_license` | 11 | 39 | 19 | 0 | 28 | 8 |

Points worth carrying into the paper:

- **`ssn` is authored on zero documents and detected on 44, all 44 corroborated.**
  No label in the corpus mentions a Social Security Number; 44 documents print one.
- **`billing_code`: authored 18, found 65, 49 corroborated.** This is the paper's
  own worked example, measured. ICD-10 and CPT codes ride along on documents whose
  labels are silent about them — and `ATTRIBUTE_IMPLICATIONS` in `core/ci_policy.py`
  already records that `billing_code` implies `medical_diagnosis`.
- **`insurance_info`: authored 27, found 71, all 44 extras corroborated.**
- **`home_address`: authored 8, found 85.** Addresses appear in nearly every
  patient-facing document; eight labels say so.
- `date_of_birth` (95/95/95) and `contract_terms` (3/3/3) are the only two types
  in perfect three-way agreement.
- `employment_contract` shows 11 extras with **zero** corroboration — the single
  clearest candidate for tagger over-capture (the rule fires on the phrase
  "Employment Agreement" used as a document title). Flagged for the audit.
- `name` and `job_title` extras are inflated by provider details in signature
  blocks — a real information type in the document, but about the clinician rather
  than the subject. The vocabulary does not currently distinguish subject-linked
  from third-party attributes; see Limitations.

### 3.3 By sensitivity tier

| tier | docs | exact | A\B | B\A | mean Jaccard |
|---|---:|---:|---:|---:|---:|
| `clinical_standard` | 39 | 0 | 6 | 230 | 0.344 |
| `financial` | 25 | 0 | 3 | 135 | 0.352 |
| `employment` | 21 | 0 | 1 | 84 | 0.388 |
| `clinical_sensitive` | 10 | 0 | 0 | 60 | 0.374 |
| `internal` | 9 | 0 | 0 | 10 | 0.000 |
| `public` | 1 | 0 | 0 | 1 | 0.000 |

Under-specification is uniform across tiers — it is not a property of the
sensitive end of the corpus. `internal` and `public` show Jaccard 0.000 because
their authored sets are empty by construction; the 11 pairs found there are names
and job titles on schedules, memos, and the pamphlet.

### 3.4 By document type (highest B\A first)

| document type | docs | A\B | B\A | | document type | docs | A\B | B\A |
|---|---:|---:|---:|---|---|---:|---:|---:|
| `clinical_note` | 10 | 0 | 68 | | `billing_statement` | 6 | 1 | 25 |
| `insurance_claim` | 8 | 1 | 49 | | `employment_contract` | 5 | 0 | 19 |
| `lab_report` | 8 | 0 | 46 | | `explanation_of_benefits` | 4 | 1 | 15 |
| `prescription` | 8 | 0 | 43 | | `performance_review` | 4 | 0 | 15 |
| `referral_letter` | 6 | 3 | 35 | | `credentialing_file` | 3 | 0 | 14 |
| `mental_health_assessment` | 5 | 0 | 31 | | `contractor_agreement` | 3 | 0 | 8 |
| `insurance_verification` | 4 | 0 | 30 | | `meeting_agenda` | 3 | 0 | 4 |
| `radiology_report` | 5 | 0 | 29 | | `policy_memo` | 3 | 0 | 3 |
| `discharge_summary` | 5 | 3 | 28 | | `staff_schedule` | 3 | 0 | 3 |
| `salary_letter` | 6 | 1 | 28 | | `public_pamphlet` | 1 | 0 | 1 |
| `prior_authorization` | 5 | 0 | 26 | | | | | |

All 10 authored-but-not-found pairs sit in four document types:
`discharge_summary` (3 × `medical_history`), `referral_letter` (3 ×
`medical_history`), billing documents (3 × `billing_code`), and one
`salary_letter` (`salary`). These are candidate tagger misses, not necessarily
spec errors — §4 is what settles that.

**This section is a report, not a repair.** Neither side was corrected;
`data/dataset.json` is byte-identical to how it was found.

---

## 4. Tagger accuracy audit

The extracted inventory is about to become an enforcement input rather than a
measurement, so its error rate changes character.

> **Misses are the dangerous direction.** A false positive makes the future subset
> check fail closed: a flow is denied that should have been permitted — visible,
> annoying, and self-correcting, because someone complains. A miss makes it pass
> over information it never saw: the gate releases the document, the recipient
> holds an information type they have no business holding, and **the decision
> looks correct**. No error is raised, no log line is unusual, nothing surfaces.
> Per-category miss rate is the number to lead with; aggregate recall hides it,
> because a category the tagger never finds contributes only a handful of cells to
> a mostly-correct total.

This warning is reproduced in the review HTML, in `score_audit.py`'s output, and
in the `direction_note` field of the scores artifact.

### 4.1 Sampling procedure

`python -m stage1.sample_audit` — **seed 7926**, inherited from PANOPTICON's
`sample_review.py` so both papers' manual-review samples are drawn under the same
documented seed. 25 documents.

1. Quota per tier: every tier receives `min(3, tier size)`, censusing the small
   tiers (`public` holds 1 document, `internal` 9); the remaining budget is split
   in proportion to each tier's leftover documents by the largest-remainder
   method, ties broken by tier name so the result cannot depend on dict ordering.
2. Within a tier: shuffle the tier's document types and the documents within each,
   then round-robin one document per type until the quota is met — document-type
   coverage before a second document of any one type.
3. Final order by `doc_id`.

All draws come from `random.Random(7926)`; no global random state is touched.
Re-running reproduces the sample byte-for-byte (verified).

| tier | corpus | quota | drawn |
|---|---:|---:|---:|
| `clinical_standard` | 39 | 7 | 7 |
| `financial` | 25 | 5 | 5 |
| `employment` | 21 | 5 | 5 |
| `clinical_sensitive` | 10 | 4 | 4 |
| `internal` | 9 | 3 | 3 |
| `public` | 1 | 1 | 1 |

**All 6 populated tiers and all 21 document types are represented in 25 documents.**

### 4.2 The review packet

`stage1/artifacts/audit/`

| file | role |
|---|---|
| `audit_sample_v1.0.0.json` | sampling record — seed, procedure, quota, realized allocation, corpus hash |
| `audit_sheet_v1.0.0.csv` | **the answer sheet** — 400 rows |
| `audit_review_v1.0.0.html` | evidence view — full document text with every detection highlighted, plus a per-document 16-type table |

The sheet carries **one row per (document, information type)** — 25 × 16 = 400
rows — with `tagger_detected` prefilled. The annotator fills
`present_in_document` with `y` or `n`. That yields a complete confusion matrix
per category with no free-text parsing:

```
TP  detected=yes  present=y        FP  detected=yes  present=n
FN  detected=no   present=y        TN  detected=no   present=n
```

Of the 400 cells, 178 are prefilled `detected=yes`. The remaining 222 are where
misses are found — which is why the sheet enumerates all 16 types for every
document rather than only the detected ones. Recall is not computable from a
detections-only sheet.

### 4.3 Running the human pass

```
# 1. read the evidence view
stage1/artifacts/audit/audit_review_v1.0.0.html

# 2. fill present_in_document (y/n) for all 400 rows
stage1/artifacts/audit/audit_sheet_v1.0.0.csv

# 3. score
python -m stage1.score_audit
```

`score_audit.py` computes precision, recall, F1, and per-category miss rate, with
Wilson 95% intervals (several per-category cells are small enough that the normal
approximation would run past 0 or 1), breaks results down by tier, and attributes
every false positive back to the specific tagger rule that produced it — so a bad
rule can be identified rather than a whole type written off.

It **refuses to run on an incomplete sheet**, reporting outstanding rows per
document, and contains no ground truth of its own: it will not infer, impute, or
model a missing verdict. Substituting an LLM for the annotator would mean scoring
one extractor against another and reporting the result as accuracy. `sample_audit`
likewise refuses to overwrite a sheet that already carries annotations.

### 4.4 Results of the human pass

All 400 cells were annotated by the researcher. **Precision 0.994 (95% CI
[0.969, 0.999]), recall 1.000 (95% CI [0.979, 1.000]), miss rate 0.000 — on a
corpus five of the tagger's rules were revised against.** That qualifier belongs
in this sentence rather than further down: `insurance.member_id`,
`diagnosis.labeled`, `employment.agreement_title` and `medication.dose_form` were
tightened, and a `medical_history` block rule added, after inspecting output from
this corpus (§5.2). The figures are therefore optimistic relative to unseen
clinical text, and should be read as an upper bound on what this tagger would
achieve in the field.

| | |
|---|---:|
| TP | 177 |
| FP | 1 |
| FN | **0** |
| TN | 222 |
| precision | 0.994  [0.969, 0.999] |
| recall | 1.000  [0.979, 1.000] |
| miss rate | 0.000 |

**Zero misses across 177 present cells is the result that matters**, because a
miss is the direction that fails silently: an information type the tagger does
not report never enters the inventory, so the Stage 2 check cannot govern it, the
document is released, and nothing records that it happened. Within this sample,
across all 16 types, all 6 tiers and all 21 document types, the annotator found
nothing present that the tagger had not flagged.

The single false positive is `insurance_info` on `doc_008`, from
`insurance.carrier_plan` matching the bare word "Medicaid" in prose rather than
as the subject's coverage. It falls in `clinical_sensitive`, giving that tier
precision 0.971 against 1.000 in every other tier.

Per-type figures are supporting detail rather than headline, because **rare types
are underpowered**: `contract_terms` rests on a single present cell (recall CI
[0.21, 1.00]) and `emergency_contact` on four (CI [0.51, 1.00]). Every type
returned precision and recall of 1.000 except `insurance_info` (precision 0.933),
but for the rare types that reflects small support rather than demonstrated
reliability. The aggregate intervals are the defensible numbers.

**Version stamp.** The sheet was generated under vocabulary v1.0.0 and scored
under v1.2.0. This is valid rather than a mismatch: v1.1.0 and v1.2.0 changed
definition text only — `emergency_contact`'s subject-linkage, and the `job_title`
and `medical_license` ownership boundaries — and never added, renamed, or removed
an entry. The 16 types the sheet enumerates are the 16 types v1.2.0 defines.

---

## 5. Limitations

1. **No accuracy figures exist yet.** Everything in §2 and §3 is measured against
   the tagger's own output. Until §4's human pass is done, "extracted" means "what
   this tagger reports", not "what is present". The 520 found-not-authored pairs
   are an upper bound containing an unmeasured number of false positives; the 348
   corroborated by the generation model are the more defensible subset.

2. **The tagger is audited at 0.994 / 1.000, on a corpus it was partly fitted
   to.** This limitation has changed shape rather than gone away: it is no longer
   that the tagger is unmeasured, but that its measurement comes from the same
   corpus five of its rules were revised against, with wide per-category intervals
   for rare types (`contract_terms` n=1, CI [0.21, 1.00]; `emergency_contact`
   n=4). Gazetteers were authored from
   general clinical knowledge, but rules were revised after inspecting corpus
   output — over-capture fixes to `insurance.member_id`, `diagnosis.labeled`,
   `employment.agreement_title`, `medication.dose_form`, and a `medical_history`
   block rule added once it was clear the inline form reached only a minority of
   history sections. Reported precision/recall will therefore be optimistic
   relative to an unseen corpus of the same kind. Two known residual false
   positives were deliberately left in (facility addresses at `doc_076`,
   `doc_079`) rather than blocklisting specific buildings, which would have made
   the fitting worse.

3. **`name` is closed-world.** Detected only via the 24-agent registry plus a
   titled-provider pattern. Its 91-document count is a floor.

4. **The vocabulary does not distinguish subject-linked from third-party
   attributes.** A clinician's `name`, `job_title`, and `medical_license` in a
   signature block are counted the same as the subject's. This inflates those
   three types' found-not-authored counts and will matter in Stage 2, where "types
   the requester's role may receive" almost certainly means *about the subject*.
   Resolving it needs a vocabulary change (a subject-linkage axis), which is a
   deliberate v2.0.0 decision, not a Stage 1 patch.

5. **`mental_health` conflates finding with category.** `mental.category_marker`
   fires on statutory confidentiality boilerplate ("…protected under the Illinois
   MHDDCA…") and on a clinician's specialty ("Psychiatry") in HR and credentialing
   records, where no subject mental-health information is present. It is kept as a
   separate rule id precisely so the audit can score it apart from
   `mental.clinical_term` and `mental.icd_f_code`. This is the extra-sensitive
   type, so its precision matters more than most.

6. **`pii_basic` is unpopulated.** `SensitivityTier` defines 7 tiers; the corpus
   uses 6. The readme's "7 sensitivity tiers" is inaccurate. `public` (n=1) and
   `internal` (n=9) are small enough that their per-tier audit cells will not
   support interval estimates.

7. **Sample size.** 25 documents / 400 cells gives usable aggregate precision and
   recall, but per-category cells for rare types (`contract_terms`, present in 3
   documents corpus-wide) will be too small to estimate. `-n 35` is available if
   tighter per-category intervals are wanted.

8. **Two observations about the existing gate**, noted in passing and not acted on:
   `evaluate_document_flow` keys its assignment check off the module constant
   `ASSIGNMENT_REQUIRED_TIERS`, while `eval_flows.classify_flow` keys off the
   per-record `label.assignment_required` — they agree on this corpus, but they
   are different predicates and `label.assignment_required` is currently dead as
   far as the gate is concerned. And `ROLE_ATTRIBUTE_PERMISSIONS` in
   `core/ci_policy.py` is already a role → attribute-type table from the legacy
   attribute-level track; Stage 2 does not start from blank, though that table is
   incomplete (`IT Contractor` and `Patient` are empty sets, and `ssn`, `name`,
   `job_title`, `contract_terms` appear in no role's set).

---

## 6. Reproducing

```
cd "CI Sim"
python -m stage1.vocabulary          # print the vocabulary and PANOPTICON mapping
python -m stage1.build_inventory     # deliverable 2
python -m stage1.reconcile           # deliverable 3
python -m stage1.sample_audit        # deliverable 4a  (seed 7926)
python -m stage1.score_audit         # deliverable 4b  (after the human pass)
```

Standard library only, plus `pydantic` via the existing `core`/`world` imports —
no new dependencies. All artifacts are deterministic and carry no wall-clock
timestamp; re-running over an unchanged corpus reproduces them byte-for-byte,
which has been verified for the inventory and the audit sample. Every artifact
records `vocab_version`, and the inventory additionally records `tagger_version`
and the corpus SHA-256; `reconcile` and `sample_audit` abort if that hash no
longer matches.

### Changes to existing files

None. Stage 1 added `stage1/` and wrote nothing outside it. `data/dataset.json`
hashes to the same `49cdd9c8…` before and after every run in this stage;
`core/`, `world/`, `pipeline/`, and `evaluation/` were opened read-only.
(`git status` shows unrelated pre-existing drift in the working tree that
predates Stage 1 — `stage1/` is the only new path attributable to it.)
