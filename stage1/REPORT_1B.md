# Paper III — Stage 1b: Subject-Linkage Classification

Linkage **v1.2.0** · vocabulary **v1.2.0** · tagger v1.0.1 (unchanged)

> **Revised twice since first written.** Stage 1c reclassified
> `emergency_contact` as subject-linked (§5.3) and corrected §6.1's
> error-direction framing, which had the asymmetry backwards. Stage 1d then ran
> the human audit, which found a defect that had been suppressing a fifth of the
> inventory, fixed it, and remeasured — see **§1.5**, which is the methods result.
> **All figures below are v1.2.0, measured after the fix.** v1.1.0 figures are
> retained inline for comparison and their artifacts are kept intact.

Corpus `data/dataset.json`, SHA-256 `49cdd9c8…`, 105 documents.

Stands alongside `REPORT.md`, which it does not supersede. Stage 1's artifacts are
untouched and still regenerate byte-identically (verified).

---

## 0. One correction to the brief

The brief asks for classification of "the 801 detections". **801 is the count of
(document, information type) pairs, not detections.** The v1.0.0 inventory holds
**1,392 individual detections** across those 801 pairs. Per-occurrence
classification is what Stage 1b requires, so all 1,392 were classified, and
results are rolled up to the 801 pairs only where the pair is the right unit
(§4, the found-but-not-authored figure).

---

## 1. Method

No language model is used anywhere in this stage. Classification is deterministic
rules over the label's subject identity and the document's structure.

### 1.1 Ownership is resolved in two steps, which is what makes the inversion work

The classifier never asks "is this attribute the subject's?" directly. It asks
"whose attribute is this?" — yielding an ownership **role**
(`subject_of_record`, `staff`, `other_person`, `institution`) — and only then
resolves that role against the document's `subject_type`.

The employment inversion therefore falls out as a consequence rather than a
special case: `staff` resolves to `subject` when `subject_type` is `employee` or
`contractor`, and to `third_party` when it is `patient`. One table, one
resolution rule, no per-document handling.

### 1.2 Signals, in priority order

| # | signal | what it is | n |
|---|---|---|---:|
| 0 | `vocabulary_definition` | the entry is subject-linked by definition, so no positional evidence applies (v1.1.0: `emergency_contact`) | 22 |
| 1 | `field_label` | detection sits in the value of a labeled field whose label states ownership (`Patient Name:`, `Ordering Physician:`, `Prepared by:`) | 606 |
| 2 | `section` | nearest preceding section header states ownership (`PATIENT INFORMATION`, `PROVIDER ATTESTATION`, `FAMILY HISTORY`) | 397 |
| 3 | `name_match` | `name` only — compared against the document's subject after title/suffix normalization. A name that is not the subject's is third-party by definition | 133 |
| 4 | `type_default` | family default conditioned on `subject_type`, where no direct evidence exists | 129 |
| 5 | `region` | letterhead / signature block / confidentiality footer | 41 |
| 6 | `field_label_self` | the detection *is* the label (`job_title` matching the text "ATTENDING PHYSICIAN" in `ATTENDING PHYSICIAN: Dr. Nguyen`) | 36 |
| 7 | `provider_block` | a credential field inheriting the clinician its block is about | 22 |
| 8 | `unresolved` | → `ambiguous` | 6 |

The field-label table was built empirically: every label occurring three or more
times in the corpus was enumerated and assigned by hand. A label absent from the
table contributes **no** signal rather than a guessed one.

### 1.3 Provider blocks

Credential fields are deliberately given no fixed owner, because they are exactly
where the inversion bites — `NPI:` belongs to the signing clinician on a patient's
note and to the subject on a credentialing file. Instead they inherit from the
block they sit in:

```
PRESCRIBER INFORMATION
Physician: Dr. Patricia Nguyen, MD     <- staff-owned label opens the block
Medical License No.: IL-MD-082947      <- inherits the clinician
DEA Number: BN4827163                  <- inherits
NPI: 1234567890                        <- inherits
                                       <- blank line closes the block
```

A block continues only through credential fields, further staff labels, and
unlabeled continuation lines, capped at six lines. An earlier version closed only
on an explicitly subject-owned label, which let `Ordering Physician:` run through
`Exam Type:` and misclassify a patient's billing code two lines later; that was
caught in validation and fixed.

### 1.4 Two corrections made during validation

Both changed the headline result, so they are recorded rather than silently
absorbed:

1. **Detections sitting *on* a field label** were originally treated as
   unlabeled, pushing 35 occurrences into `type_default`.
2. **`NPI:` and `Medical License:` had no owner and no inheritance**, pushing a
   further 95 into `type_default`.

Together these made the corpus look far less structured than it is: the first
measurement put structural resolution of third-party detections at **29.2%**,
against **67.1%** after the fixes (**62.0%** after the later `emergency_contact`
reclassification shrank the third-party denominator). Had the first number been
reported, §5 would have recommended the opposite course.

The 130 figure above counts only what one diagnostic probe surfaced. Enumerating
the correction rounds properly — the two fixes plus every field label and section
header added alongside them — gives **203 affected occurrences**. Stage 1c draws a
seeded verification sample across all four mechanisms so the corrections are
independently checked rather than taken on trust; see
`stage1/verify_corrections.py`.

### 1.5 What the human audit found, and the fix

The Stage 1c pass (487 human judgements, all 226 filtered detections censused)
measured the v1.1.0 classifier and found it badly wrong in the dangerous
direction:

| | v1.1.0 |
|---|---:|
| precision on `third_party` | 0.730 (100/137) |
| precision on `organizational` | **0.303 (27/89)** |
| recall on `subject` | 0.776 (250/322) |
| **silent-release cases** | **66**, across 20 documents |

The silent releases included **HIV** and **AIDS** on `doc_008` and eighteen
`mental_health` detections across six `clinical_sensitive` documents —
`suicidal ideation`, `PHQ-9`, `depression`, `substance use disorder`. Each had
been filtered out of the inventory, where the fifth check could never have
governed it.

**Root cause.** `RIVERSIDE MEDICAL CLINIC` matched the ALL-CAPS section-header
pattern and was mapped to `OWNER_INSTITUTION` in `SECTION_OWNER`. Because
`Segments.section()` returns the nearest *preceding* header with no scope limit,
in any document where no later header intervened the masthead governed the entire
body, and every clinical detection beneath it resolved to institutional
ownership. **56 of the 66** silent releases traced to this single defect.

**Three fixes, all general rather than string-specific.**

1. **A masthead confers no ownership.** An organisation-name line names the
   document's *issuer*, not the subject of the content beneath it. Organisation
   headers were removed from `SECTION_OWNER` and a general `is_masthead()` guard
   added, matching any header naming a clinic, hospital, health system, medical
   group, associates, institute, LLC/Inc/LLP/PC. No literal string is blocklisted.
2. **Letterhead detection no longer fails on leading decoration.** v1.1.0 returned
   `letterhead_end = 0` for any document opening with a rule line — `doc_008`
   among them — so those documents had no letterhead region and the masthead fell
   into `body`. Leading rule and blank lines are now skipped.
3. **The letterhead region confers institutional ownership only when it is
   actually a masthead.** Fix 2 exposed a document (`doc_009`) opening with a
   statutory banner — "CONFIDENTIALITY NOTICE — 42 CFR PART 2 — SUBSTANCE ABUSE
   TREATMENT RECORDS" — rather than a clinic name. That block is about the
   patient's record, not the institution, and without this guard fix 2 would have
   newly filtered two of its detections.

**Remeasured against the same, unchanged human labels** — no re-annotation, since
the labels are ground truth independent of the classifier, which is what
withholding the key from the sheet bought:

| | v1.1.0 | v1.2.0 |
|---|---:|---:|
| precision on `third_party` | 0.730 (100/137) | 0.730 (100/137) |
| precision on `organizational` | 0.303 (27/89) | **0.900 (18/20)** |
| **precision on "filtered at all"** | **0.704 (159/226)** | **0.955 (150/157)** |
| recall on `subject` | 0.776 (250/322) | **0.963 (310/322)** [0.94, 0.98] |
| total misclassifications | 110 | **59** |
| **silent-release cases** | **66** | **6** |

All eighteen `mental_health` cases and both HIV/AIDS cases are retained. Of the
60 clinically critical silent releases, 59 are fixed; the one remaining is a
`home_address` on `doc_076` that is in fact the clinic's HR office address —
a known Stage 1 tagger false positive (`REPORT.md` §5.2) rather than a linkage
failure.

**Precision on "filtered at all" is the figure that matters for the gate.** The
`third_party` figure of 0.730 is misleading in isolation: 31 of its 37 errors are
`third_party` → `organizational`, a disagreement about *which* filtered class. For
the fifth check both classes remove the type identically, so those are not release
risks. Only **7 detections in the whole corpus are wrongly filtered**.

**Residual `organizational` error: 2 of 20**, both from the `region` signal —
`doc_076`'s HR office address (above) and an NPI on `doc_049` the annotator read
as a clinician's. No systematic pattern remains; the two are unrelated
single cases in different documents, not a rule failing repeatedly.

**Two definitional boundaries were settled rather than fitted** (see
`vocabulary.py` v1.2.0). A staffing headcount — "2 RN, 1 Billing Specialist" —
names no individual and is `organizational`; a title asserted of an identified
person remains `subject`/`third_party`. A Type 2 NPI belongs to the organisation,
a Type 1 to the clinician. Both are recorded in the entry definitions rather than
left implicit in code.

**One boundary is NOT resolved and is reported rather than encoded.** The
annotator marked bare job titles (`ATTENDING PHYSICIAN` as a field label) and
`NPI:` under `PROVIDER ATTESTATION` as `organizational`, where the classifier
says `third_party`. That accounts for 22 of the 31 `third_party` →
`organizational` disagreements. Encoding it would have meant fitting rules to the
labels being used to score them. It costs nothing in release risk — both classes
filter — so it is left open for Stage 2 to settle.

---

## 2. The split

**1,392 detections across 105 documents.**

| class | n | % | | v1.1.0 | v1.0 (pre-`emergency_contact`) |
|---|---:|---:|---|---:|---:|
| `subject` | **1,229** | **88.3%** | | 1,160 | 1,139 |
| `third_party` | **137** | **9.8%** | | 137 | 158 |
| `organizational` | **20** | **1.4%** | | 89 | 89 |
| `ambiguous` | **6** | **0.4%** | | 6 | 6 |

The `organizational` column is where the §1.5 defect lived: 69 detections moved
from `organizational` to `subject` once the masthead stopped conferring
institutional ownership. `third_party` is unchanged by the fix — the defect was
entirely in the institutional path.

`organizational` was introduced because the corpus needs it: 103 of 105 documents
open with a clinic letterhead carrying the institution's premises address and
switchboard, and 10 close with statutory confidentiality boilerplate. **Boundary:
`organizational` means the attribute belongs to the institution as an entity —
clinic address, facility NPI, main phone, tax ID, and statutory notices that
describe the document's handling rather than any person.** A staff member's own
attribute is `third_party`, not `organizational`, even on an institutional
document.

The 0.4% ambiguous rate is low, and that is a claim about this corpus rather than
about the problem. The corpus is machine-generated from a specification and is
consequently far more regular than clinical text in the field. §6 states this
plainly.

### 2.1 By information type

| type | n | subject | third_party | org | amb | % third-party |
|---|---:|---:|---:|---:|---:|---:|
| `medical_license` | 46 | 13 | **31** | 2 | 0 | **67.4%** |
| `job_title` | 102 | 46 | **50** | 6 | 0 | **49.0%** |
| `name` | 133 | 91 | **42** | 0 | 0 | **31.6%** |
| `employment_contract` | 39 | 29 | 4 | 6 | 0 | 10.3% |
| `medical_diagnosis` | 262 | 255 | 7 | 0 | 0 | 2.7% |
| `mental_health` | 99 | 91 | 2 | 1 | 5 | 2.0% |
| `medical_history` | 68 | 67 | 1 | 0 | 0 | 1.5% |
| `date_of_birth` | 95 | 95 | 0 | 0 | 0 | 0.0% |
| `ssn` | 44 | 44 | 0 | 0 | 0 | 0.0% |
| `home_address` | 87 | 85 | 0 | 2 | 0 | 0.0% |
| `emergency_contact` | 22 | **22** | 0 | 0 | 0 | 0.0% |
| `medical_medication` | 199 | 198 | 0 | 0 | 1 | 0.0% |
| `billing_code` | 91 | 91 | 0 | 0 | 0 | 0.0% |
| `insurance_info` | 78 | 78 | 0 | 0 | 0 | 0.0% |
| `salary` | 21 | 21 | 0 | 0 | 0 | 0.0% |
| `contract_terms` | 6 | 3 | 0 | 3 | 0 | 0.0% |

**Your expectation was right on two of three, and the apparent worst case turned
out to be a definitional error rather than contamination.** `job_title` (49.0%)
and `medical_license` (67.4%) are indeed heavily affected, and `name` (31.6%)
meaningfully so. `emergency_contact` measured 95.5% third-party on positional
evidence, which was the classifier being right about the mention and wrong about
the type; it is now subject-linked by definition (§5.3) and sits at 0.0%.
After that correction the three types you named are exactly the three affected
types.

Two findings worth carrying into the paper:

- **Clinical content is almost entirely subject-linked.** `medical_diagnosis`,
  `medical_medication`, `medical_history`, `billing_code`, and `insurance_info`
  are between 97% and 100% subject or organizational. The contamination is
  confined to the identity and employment families. This matters: the types that
  carry the Paper III argument are the ones least affected by the problem.
- **The seven third-party `medical_diagnosis` detections are all `FAMILY HISTORY`
  entries** — "coronary artery disease", "myocardial infarction", "Dementia" —
  which describe relatives, not the subject. A genuine CI distinction the section
  header exposes for free.

### 2.2 By sensitivity tier, employment reported separately

| tier | n | subject | third_party | org | amb |
|---|---:|---:|---:|---:|---:|
| `clinical_standard` | 658 | 569 | **89** | 0 | 0 |
| `financial` | 303 | 278 | 24 | 1 | 0 |
| `clinical_sensitive` | 225 | 214 | 9 | 2 | 0 |
| **`employment`** | **187** | **168** | **0** | 13 | **6** |
| `internal` | 18 | 0 | 15 | 3 | 0 |
| `public` | 1 | 0 | 0 | 1 | 0 |

**The employment tier carries zero third-party detections.** That is the
inversion working: on the 21 employment-tier documents the subject is staff, so
clinician names, job titles, licences, and salaries resolve to `subject`. If the
inversion had been mishandled, this cell would be the largest in the table rather
than empty.

Third-party contamination is concentrated in `clinical_standard` (89 of 137,
65%) — clinical notes, prescriptions, and lab reports, which carry provider
attribution blocks that HR documents do not.

By subject type: `patient` 122 third-party of 1,186; `employee` 0 of 163;
`contractor` 0 of 24; `organization` 15 of 19.

The `clinical_sensitive` row is the one to note: 39 detections were classified
`organizational` under v1.1.0 and 2 are under v1.2.0. That row was the §1.5
defect at its most damaging — the extra-sensitive tier, silently emptied.

---

## 3. Structural analysis — the decision-relevant result

Third-party detections were partitioned by the signal that identified them.
Three buckets, not two: `name_match` is decisive but is an identity comparison
against the label's subject rather than a positional cue, and folding it into
either "structural" or "prose" would misdescribe it.

**All 137 third-party detections:**

| resolution | n | % |
|---|---:|---:|
| structurally identifiable (field label, provider block, region, section) | 84 | 61.3% |
| identity comparison against the subject | 42 | 30.7% |
| left to a prose default | 11 | 8.0% |

**Restricted to the 95 documents that have an individual subject** — the only
documents where the distinction is operative, since an organization-subject
document has no subject for anything to be linked to:

| resolution | n | % |
|---|---:|---:|
| structurally identifiable | 80 | 65.6% |
| identity comparison | 42 | 34.4% |
| prose | **0** | **0.0%** |
| **separable without reading prose** | **122** | **100.0%** |

All 10 prose-residue detections sit on organization-subject documents — staff
schedules, meeting agendas, policy memos — where every person-attribute is
third-party by definition and no separation rule is needed. Two of those 10 are
Stage 1 tagger false positives rather than real attributes (`doc_100`:
`title.labeled` matching "Role-based access controls will be enforced";
`doc_101`: `employment.effective_date` matching a policy effective date).

### 3.1 Examples

**Structurally identifiable** — the overwhelming majority:

```
ATTENDING PHYSICIAN:   Dr. Susan Hargrove, MD      <- field_label_self (job_title)
Prescribing Physician: Dr. Sarah M. Nguyen, MD     <- field_label
Medical License:       IL-MD-048821                <- provider_block
NPI:                   1234567890                  <- provider_block
FAMILY HISTORY                                     <- section
  • Coronary artery disease (father)               <- third-party diagnosis
```

**Identity comparison** — resolved by comparing against `subject_name`:

```
Mr. John Smith presents today for a routine follow-up      -> subject
Dr. Patricia Holloway, MD — Internal Medicine              -> third_party
```

**Prose, irreducible** — all on documents with no individual subject:

```
NURSING STAFF:
  • Nurse Davis     Full Day    07:00 – 19:00       (staff_schedule, no subject)
Approved open positions: 2 RN, 1 Billing Specialist  (meeting_agenda, no subject)
```

### 3.2 The answer

**Predominantly structural. Build the filter.**

I am not hedging this. On every document where the subject/third-party
distinction is operative, third-party attributes are separable without reading
prose — 65.6% from explicit ownership labels and block structure, 34.4% from
comparing a name against the document's own subject field. The corpus attributes
clinician information positionally and consistently, because it was generated
from templates that do so.

A filter would catch: all provider attribution blocks, all signature and
attestation blocks, letterheads, confidentiality footers, family-history
sections, and every non-subject name. It would miss: third-party attributes
mentioned in running narrative with no label and no name adjacent to them —
of which this corpus contains none that the tagger detects.

The honest caveat on that 100% is in §6.1 and is important: the denominator is
the classifier's own output.

---

## 4. The corrected found-but-not-authored figure

Stage 1 reported **520** found-but-not-authored (document, type) pairs. Rolled up
from the per-occurrence classification:

| class | pairs | | v1.1.0 |
|---|---:|---|---:|
| `subject` | **459** | | 449 |
| `third_party` | **56** | | 57 |
| `organizational` | **4** | | 13 |
| `ambiguous` | **1** | | 1 |

**The corrected figure is 459** — an 11.7% reduction from 520. That is the number
to publish. It has moved twice: 433 before `emergency_contact` was reclassified
(§5.3), 449 after, and 459 after the §1.5 defect was fixed. Each move is a
measurement, not a revision of judgement.

Rollup rule: a pair counts as `subject` if **any** of its occurrences is
subject-linked. The future check governs whether a document carries a type about
the subject at all, so one subject-linked occurrence is enough. This is why
`name` rolls up to 91 subject / 0 third-party despite being 31.6% third-party at
the occurrence level — every document containing a clinician's name also contains
the subject's own.

Where the 61 non-subject pairs come from:

| type | subject | third_party | org |
|---|---:|---:|---:|
| `job_title` | 24 | **38** | 0 |
| `medical_license` | 10 | **16** | 2 |
| `emergency_contact` | 17 | 0 | 0 |
| `employment_contract` | 7 | 3 | 1 |
| `home_address` | 73 | 0 | 4 |
| `billing_code` | 46 | 0 | 4 |
| all others | 272 | 0 | 2 |

The Stage 1 headline claims survive intact. `ssn` 44 → **44 subject-linked**;
`insurance_info` 44 → **44**; `billing_code` 50 → **46 subject, 4 organizational**;
`medical_diagnosis` 32 → **32**. The 71-pair correction falls almost entirely on
`job_title` and `medical_license` — two of the three types the Stage 1 limitation
named.

---

## 5. Proposed v2.0.0 vocabulary change — specification only

Not implemented. The vocabulary file is untouched and still reads v1.0.0.

### 5.1 Recommendation: a per-detection linkage axis, not split entries

**The 16-entry vocabulary should not change.** Add `subject_linked` as a field on
each *detection* in the inventory schema, and put the filter on the left-hand
side of the Stage 2 check:

```
{ t : t ∈ types(d) ∧ subject_linked(t, d) }  ⊆  role_permissions[requester.role]
```

**Why not split entries into subject/third-party variants.** Stage 2 authors six
role permission sets against this vocabulary. Splitting even the four affected
entries takes the vocabulary from 16 to 20; splitting all of them takes it to 32.
Every role set then has to decide on each variant, and the third-party rows would
receive the same answer almost every time, so it is authoring overhead that buys
nothing. Worse, the split bakes the linkage decision into the *type identity*,
so a later correction to the classifier — and §6.1 says corrections are likely —
changes which vocabulary entry a detection belongs to, invalidating authored
permission sets. The boolean keeps classifier corrections orthogonal to authored
policy.

**The property that matters for Stage 2.** Filtering shrinks the left-hand set,
so relative to the unfiltered check it can only convert DENY → PERMIT — it
strictly removes false denials and can never introduce a new release. Relative to
the current four-check gate the fifth check remains monotone (PERMIT → DENY
only). Both properties hold under the boolean and are preserved by any later
improvement to the classifier, since a better classifier only moves detections
between filtered and unfiltered.

**Consequence for Stage 2 sequencing: role permission sets can be authored now.**
The vocabulary they are authored against is stable, and the linkage axis attaches
to detections rather than to types. There is no re-authoring risk. This is the
main practical finding of Stage 1b.

### 5.2 What does change

- **Inventory schema → v2.0.0** (not the vocabulary): each detection gains
  `subject_linked: bool` and `linkage_signal: str`. Keeping the signal is what
  lets a reviewer see *why* something was filtered.
- `stage1/vocabulary.py` gains no entries; its `VOCAB_VERSION` stays `1.0.0`.

### 5.3 The one entry that does need a definitional decision

**DECIDED — implemented in vocabulary v1.1.0.** `emergency_contact` measured
95.5% third-party, and under the recommendation above would have been filtered out
of nearly every document, so the gate would never govern it. Two readings were
defensible:

- *The mention is about Mary Smith* — her name and phone are third-party PII.
  This is what the classifier currently implements.
- *The fact that the subject has designated an emergency contact, and who it is,
  is a relational fact about the subject* — and it is recorded in the subject's
  chart precisely because it is theirs.

The second reading was adopted, on a stronger rationale than the one I gave:
under HIPAA the emergency contact recorded in a patient record forms part of the
**designated record set**, so it is PHI about the patient. Who the subject
designated is a relational fact about the subject.

Implemented as `SUBJECT_LINKED_BY_DEFINITION` in `stage1/vocabulary.py` and a
**v1.1.0** bump — a change to one entry's definition text, with no entry added,
renamed, or removed, so every inventory and permission set keyed against v1.0.0
remains valid. Detections of such a type bypass positional classification
entirely (signal `vocabulary_definition`).

Effect: all 22 occurrences move to `subject`; the overall split goes from
1,139/158 to **1,160/137**; and the corrected found-but-not-authored figure rises
from 433 to **449**. It remains the only entry where the classifier's
per-occurrence answer and the CI-relevant answer come apart — but see §6.7, which
is the cost of the decision.

`family_history` raises the same shape of question one level down —
"coronary artery disease (father)" is about a relative, but its presence in the
chart is a fact about the subject. It currently has no vocabulary entry of its
own and falls under `medical_diagnosis`; worth a sentence in the paper, not a
vocabulary change.

---

## 6. Limitations

### 6.1 The 100% separability figure is measured against the classifier's own output

A detection is counted `third_party` only because some rule said so, and those
rules are structural — so of course the third-party set resolves structurally. A
third-party attribute that no rule catches is silently classified `subject` and
never enters the numerator. §3's figure is therefore a statement about what the
classifier found, not about what is there.

**Correction to how this was originally framed.** Stage 1b called that invisible
false-`subject` case "the dangerous direction". It is not; it is the safe one.
The two directions are not symmetric:

- **False `subject`** — an extra type stays in the inventory. The gate governs
  something it need not, producing an **over-block**: a flow denied that should
  have been permitted. Visible, traceable, someone complains, it gets fixed.
- **False `third_party` / `organizational`** — the type leaves the inventory
  entirely, so the fifth check can never govern it, not incorrectly but *at all*.
  The document is released, the recipient holds an information type they should
  not, the decision looks perfectly correct, and nothing anywhere records that it
  happened. The subject's own address absorbed by a letterhead rule, their phone
  caught by a switchboard pattern, a staff member's own attribute on an
  employment-tier document misfiled as organizational.

So the priority quantity is **precision on the filtered classes**, not recall on
`subject`. This mirrors the Stage 1 tagger-miss asymmetry one layer up: in both
cases the dangerous error is the one that removes something from view.

**157 detections are filtered out under v1.2.0** (137 `third_party` + 20
`organizational`), down from 226 under v1.1.0. Every one is a candidate silent
release, and all 157 carry a human label.

Sizing the secondary exposure as well: of 1,229 `subject` classifications, **1,037
(84.4%) rest on direct evidence** (field label, section header, name comparison,
region, vocabulary definition) and **192 (15.6%) rest on a family default with no
direct evidence**. The default share rose from 10.3% because the masthead fix
removed a spurious section signal and those detections now fall through to the
family default — they are correctly classified, but on weaker evidence.

**This was no longer a hypothetical, and the measurement is now done.**
`stage1/sample_linkage_audit.py` produced a 487-row human pass censusing every
filtered detection corpus-wide; `stage1/score_linkage.py` scored it. The result
(§1.5) was 0.303 precision on `organizational` and 66 silent releases under
v1.1.0, against 0.900 and 6 under v1.2.0. The harness found a real defect that
review of the code had not, which is the argument for building it.

### 6.2 The corpus is unusually regular

It is machine-generated from `pipeline/doc_specs.py` templates, which attribute
clinician information positionally and consistently. Real clinical text mixes
attribution into narrative far more. The 0.4% ambiguous rate and the 100%
separability figure are properties of *this* corpus and should be reported as
such; neither would survive contact with field data unchanged.

### 6.3 Fitting

The field-label and section tables were built by enumerating labels attested in
this corpus, and two rounds of corrections (§1.4) were made after inspecting
classifier output. The tables will not generalize to documents using different
labels. This is the same fitting risk `REPORT.md` §5.2 records for the tagger,
and it compounds: Stage 1b's inputs are Stage 1's outputs.

### 6.4 The six ambiguous cases are a tagger category error, not a linkage failure

All six are `mental_health` on employment-tier documents where the trigger is a
clinician's specialty — "Medical License: IL-MD-55432 (Psychiatry)",
"Dr. Patel shall provide full-time psychiatric services", "42 CFR Part 2" in a
compliance clause. These are Dr. Patel's *job*, not her mental health. `REPORT.md`
§5.5 already flagged `mental.category_marker` as conflating category with
finding; Stage 1b confirms it from a second direction. Marking them `ambiguous`
rather than forcing a class is the honest outcome, but the real fix is in the
tagger, not the linkage classifier.

### 6.5 Name matching is closed-world and shallow

`name` detection was already registry-bound (`REPORT.md` §5.3). Matching adds
title/suffix normalization and a surname-only rule ("Mr. Lee presented…"), which
would misfire if two people in one document shared a surname. No such case occurs
in this corpus — `Dr. Sarah Chen` and patient `Michael Chen` never co-occur in a
document where the surname appears alone — but the rule is not safe in general.

### 6.6 Pair-level rollup hides occurrence-level contamination

§4's rollup marks a pair `subject` if any occurrence is subject-linked. That is
correct for the gate's purposes but means the corrected 433 figure does not
reflect that, e.g., 42 of 133 `name` occurrences are third-party. Both numbers
are reported; do not use them interchangeably.

### 6.7 `emergency_contact` creates a second data subject the architecture does not model

Reclassifying `emergency_contact` as subject-linked (§5.3) is correct for the
patient, and it has a consequence worth stating rather than absorbing. The
emergency contact — "Mary Smith (spouse) 555-0142" — is a real person with her own
privacy interest. Her name and phone number are now treated as PHI *about the
patient* and governed by the patient's permissions, which means a role permitted
to receive the patient's identity attributes receives Mary Smith's contact details
as a side effect. Nothing in the gate represents her interest.

This is not an implementation gap that a fifth check would close. The gate is
built on one subject per document: `label.subject_type` and `doc.agent` are
singular, the assignment relation keys on a single subject uid, and the Stage 2
check resolves permissions against one subject. Contextual Integrity carries no
such restriction — a flow has a subject, but a document can carry information
whose subjects differ, and the norms attaching to each may differ too. Family
history is the same shape one level down: "coronary artery disease (father)" is
about a relative, recorded because it bears on the patient.

Stated as a limitation, not modelled. Multi-subject documents would require the
label, the assignment relation, and the check to carry a subject per information
type rather than per document — a redesign well beyond Paper III's scope, and one
the corpus offers no way to validate.

### 6.8 The 0% prose residue is a property of this corpus, not of the method

§3 reports that no third-party detection on an individual-subject document
required a prose default. **That figure should not be read as evidence that
positional rules suffice for subject-linkage on clinical text.** It is a
consequence of how the corpus was built.

`data/dataset.json` was generated by a model from the templates in
`pipeline/doc_specs.py`, under a system prompt asking for documents that "match
the tone and format of real medical, billing, or HR documents" with short,
field-structured content. The result attributes third-party information
positionally and almost without exception: clinicians appear in
`ATTENDING PHYSICIAN:` fields, credentials in labelled blocks, signatures in
terminal attestation blocks. That regularity is what the classifier exploits, and
it is an artefact of generation.

Real clinical notes do not behave this way. Narrative references to other
clinicians run through the body text — "discussed with Dr. Okafor in cardiology",
"per the on-call resident", "patient's previous physician started her on
lisinopril" — as do references to relatives, employers, and external facilities,
carrying no field label, no section header, and no adjacent name the classifier
could anchor to. On such text the prose residue would be substantially non-zero,
and the structural share correspondingly lower.

What generalizes from Stage 1b is the *method* — resolve ownership to a role,
then resolve the role against the label's subject, so the employment inversion
falls out — and the finding that where structure exists it is highly informative.
What does not generalize is the 100%. Any deployment on natural clinical text
should expect a residue that positional rules cannot reach, and should treat that
residue the way Stage 1c treats the filtered classes: as the dangerous direction,
requiring human review rather than a default.

### 6.9 Annotation methods — how the human pass was run and what that does to the figures

For the paper's methods section.

**The instruction was directional, so filtered-class precision is conservative
against our own finding.** The review page told the annotator: *"When genuinely
torn, prefer `subject` or `ambiguous` over filtering."* That is the right
instruction — filtering is the direction that removes information from the
inventory silently — but it biases the labels toward `subject`, which
mechanically depresses measured precision on `third_party` and `organizational`.
The reported 0.900 and 0.955 are therefore lower bounds, not point estimates: a
neutral instruction would likely have scored the classifier higher. Reporting the
conservative number is the point.

**Single annotator, no adjudication.** All 487 judgements come from one reviewer,
so there is no inter-annotator agreement statistic and no second opinion on the
disputed boundaries. Where the annotator's reading diverges systematically from
the classifier's stated rules — bare job titles and attestation NPIs, 22 of the
31 `third_party` → `organizational` disagreements — it is not possible to say
from this data which reading is correct. Those were left unencoded (§1.5) rather
than fitted to a single reviewer's judgement.

**`ambiguous` was used once in 487 rows**, and all six of the classifier's own
`ambiguous` cases were resolved as `subject`. That rarity is a property of one
annotator working under an instruction that explicitly offered `subject` as the
safe choice, not evidence that the corpus contains almost no genuinely ambiguous
occurrences. §2's 0.4% classifier ambiguous rate and the annotator's 0.2% should
not be read as converging estimates of anything; they are two artefacts of the
same directional framing.

**Excel round-trip.** The pass was completed in Excel and saved as
`linkage_sheet_v1.1.0.xlsx`. Excel silently rewrote 25 `date_of_birth` values
into serial date numbers (`1960-12-04` → `22254`). The generated
`linkage_sheet_v1.1.0.csv` was **not** overwritten — it still carries zero
annotations and its original hash — so nothing needed restoring. Scoring joins on
`row_id` and reads only `true_class`, so no figure is affected; display values in
the error reports are taken from the key rather than the sheet. `.xlsx` is read
by `stage1/xlsx_reader.py`, standard library only (`zipfile` + `xml.etree`), so
no spreadsheet dependency was added.

**Re-scoring across a classifier revision.** The v1.2.0 re-score uses the *same*
labels with no re-annotation. Because a revision changes which detections are
filtered, and therefore which appear in that version's sheet, `row_id` is not
stable across versions; rows are matched on detection identity
(`doc_id`, `information_type`, `start`, `value`) instead. Every v1.2.0 filtered
detection has a label, so the census — and the exactness of the filtered-class
precision — survives the revision.

---

## 7. Reproducing

```
cd "CI Sim"
python -m stage1.build_inventory        # Stage 1
python -m stage1.reconcile              # Stage 1
python -m stage1.subject_linkage        # Stage 1b/1d classification (v1.2.0)
python -m stage1.sample_linkage_audit   # Stage 1c sheet
python -m stage1.verify_corrections     # Stage 1c correction check
# score the completed pass, v1.1.0 classifier (the baseline that found the defect)
python -m stage1.score_linkage --sheet stage1/artifacts/audit/linkage_sheet_v1.1.0.xlsx     --annotation-key stage1/artifacts/audit/linkage_key_v1.1.0.json --label v110
# re-score the SAME labels against the v1.2.0 classifier
python -m stage1.score_linkage --sheet stage1/artifacts/audit/linkage_sheet_v1.1.0.xlsx     --annotation-key stage1/artifacts/audit/linkage_key_v1.1.0.json     --classification-key stage1/artifacts/linkage_v1.2.0.json --label v120
```

Standard library only. Deterministic and timestamp-free; every artifact
reproduces byte-for-byte on re-run (verified). Each module aborts if the corpus
SHA-256 no longer matches the inventory's.

### Artifacts

v1.1.0 artifacts are retained alongside v1.2.0 — the before/after is a methods
result, not something to overwrite.

| file | contents |
|---|---|
| `artifacts/linkage_v1.2.0.{json,csv}` | current classification, all 1,392 detections |
| `artifacts/linkage_v1.1.0.{json,csv}` | superseded classification, retained for comparison |
| `artifacts/audit/linkage_sheet_v1.1.0.csv` | the generated sheet (0 annotations, unmodified) |
| `artifacts/audit/linkage_sheet_v1.1.0.xlsx` | **the human pass** — 487 judgements |
| `artifacts/audit/linkage_key_v1.1.0.json` | classifier calls withheld from the sheet |
| `artifacts/audit/linkage_sheet_v1.1.0_v110_{scores.json,errors.csv}` | v1.1.0 scores |
| `artifacts/audit/linkage_sheet_v1.1.0_v120_{scores.json,errors.csv}` | v1.2.0 scores, same labels |
| `artifacts/audit/correction_check_v1.1.0.csv` | 20-row verification of the §1.4 corrections (unfilled) |

### Changes to existing files

`stage1/vocabulary.py` is at **v1.2.0**. Across v1.1.0 and v1.2.0 no entry was
added, renamed, or removed — only three definitions changed
(`emergency_contact`, `job_title`, `medical_license`) — so inventories and role
permission sets keyed against v1.0.0 remain valid. Re-running `build_inventory`
and `reconcile` changes only the embedded vocabulary manifest and version stamp:
the extraction data is invariant at 801 (document, type) pairs, 1,392 detections,
520 found-but-not-authored, 10 authored-but-not-found, with the tagger untouched
at v1.0.1.

The corpus, labels, assignment relation, and gate are unmodified;
`data/dataset.json` still hashes to `49cdd9c8…`. The human annotations were not
altered. The 25-document tagger audit sheet and its seed (7926) are untouched.
