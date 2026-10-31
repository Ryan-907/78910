# Paper III — Stage 2: The Fifth Conjoined Check

Vocabulary v1.2.0 (frozen) · linkage v1.2.0 · tagger v1.0.1 · gate extension v1.2.0
Corpus `data/dataset.json`, SHA-256 `49cdd9c8…`, 105 documents, 24 agents, 2,520 flows.

Stage 2 adds an information-type check to Algorithm 1:

```
{ t : t ∈ types(d) ∧ subject_linked(t,d) }  ⊆  role_permissions[role(r)]
```

Access becomes a three-term intersection:

```
A(agent) = D(role) ∩ D(assignment) ∩ D(information_types)
```

---

## 1. Provenance of the role permission sets

**The six permission sets were authored by the researcher. No model proposed,
ranked, defaulted, or confirmed any of the 96 decisions.** This is not a stylistic
preference. Paper II's central finding is that language models cannot author
normative policy — ACL conformance as low as 23%, self-agreement as low as 26% —
so a model-authored permission set would refute the paper it appears in.

The scaffold was built to make that authorship tractable without contaminating it.
`stage2/build_template.py` emitted a 16-row × 6-role template with **every cell
blank**: no recommended column, no default, no ordering implying a preference, and
no per-(role, type) statistic. Each row carried the v1.2.0 definition verbatim
(including the Stage 1d boundary rulings on headcount, Type 1 vs Type 2 NPI, and
emergency contact), the number of documents carrying the type as subject-linked,
the tiers those documents sit in, and two example values.

The impact preview was supplied **per information type and never per (role,
type)**. A per-cell count would have been the outcome of that cell's decision
rather than input to it.

`stage2/validate_permissions.py` then checked completeness (blanks and
unrecognised values both fail — a typo must never become a silent deny),
vocabulary membership in both directions, and the six roles, before writing
`role_permissions_v1.2.0.json`.

### The authored sets

|  | Doctor | Nurse | Billing | HR | IT | Patient |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `name` | ● | ● | ● | | | ● |
| `date_of_birth` | ● | ● | ● | | | ● |
| `ssn` | | | | | | ● |
| `home_address` | ● | ● | ● | | | ● |
| `emergency_contact` | ● | ● | | ● | | ● |
| `medical_diagnosis` | ● | ● | | | | ● |
| `medical_medication` | ● | ● | | | | ● |
| `medical_history` | ● | ● | | | | ● |
| `mental_health` *(extra-sensitive)* | ● | | | | | ● |
| `billing_code` | ● | ● | ● | | | ● |
| `insurance_info` | ● | ● | ● | | | ● |
| `salary` | ● | ● | ● | ● | | |
| `employment_contract` | ● | ● | ● | ● | ● | |
| `contract_terms` | ● | ● | ● | ● | ● | |
| `job_title` | ● | ● | ● | ● | ● | ● |
| `medical_license` | ● | ● | ● | ● | | ● |

Totals: Doctor 15, Nurse 14, Patient 13, Billing Specialist 10, HR Manager 6,
IT Contractor 3.

Validation surfaced one shape for confirmation, which the author confirmed as
intended: **`job_title` is permitted to every role**, so the fifth check never
fires on it. No type is permitted to no role.

---

## 2. Implementation

`stage2/extended_gate.py`. The existing gate is **not modified** —
`core.ci_policy.evaluate_document_flow` is imported and called, never edited — so
both can be run over the same flows and compared.

The fifth check runs only where the baseline returned PERMIT. That ordering makes
monotonicity true by construction; it is verified empirically regardless.

### Properties, verified rather than asserted

| property | how it is proven | result |
|---|---|---|
| **Monotone** | extended permit set ⊆ baseline permit set, over all 2,520 flows | **holds** — 259 ⊃ 178, strict, 0 violations |
| **Content-free** | every flow re-adjudicated with document content *and every attribute value* replaced by a poison string; decisions and reason strings must be byte-identical | **holds** — 2,520/2,520 identical |
| **Stateless** | full adjudication re-run in a seed-shuffled order; per-flow results must be identical | **holds** — 2,520/2,520 identical |

The content-free test is the substantive one. It does not merely inspect the code
path; it substitutes a string that would change any decision that read it, and
requires the output not to move. The gate reads category *names* on the label and
the precomputed subject-linked type set, and nothing else.

`adjudicate.py` stops rather than proceeding if monotonicity fails.

### Explainability

A denial from the fifth check names the type that triggered it:

```
Access denied: role 'Doctor' may not receive 'ssn' about John Smith
(carried by this 'clinical_note' record)
```

Without this the new failure mode — a document refused because of one attribute
among eleven — would be opaque exactly where opacity is most expensive.

---

## 3. Measurements

**Headline: 259 → 178 permitted flows. 81 flows converted PERMIT → DENY (31.3% of
the baseline permit set).**

### 3.1 Over-delivery closed — 81 flows

| information type | flows | sole cause in |
|---|---:|---:|
| `ssn` | 57 | **36** |
| `medical_diagnosis` | 24 | 2 |
| `medical_medication` | 18 | 0 |
| `date_of_birth` | 18 | 0 |
| `home_address` | 18 | 0 |
| `name` | 14 | 0 |
| `mental_health` | 7 | 0 |
| `emergency_contact` | 5 | 0 |
| `medical_history` | 4 | 0 |

By role: Billing Specialist 25, Doctor 24, HR Manager 18, Nurse 14.
By tier: financial 31, clinical_standard 25, employment 18, clinical_sensitive 7.

**`ssn` dominates, and its provenance is the point.** Stage 1 found `ssn`
authored on **zero** of the 105 labels while present in 44 documents, all 44
corroborated by the generating model's own extraction. Under the document-level
gate those 57 flows were released with no field in the schema even recording that
an SSN was travelling. The fifth check is the first mechanism in the pipeline that
can see them.

**The paper's motivating example reproduces exactly.** Insurance claims are
correctly released to Billing Specialists by the role check, and the ICD-10
diagnosis printed on them is now refused: 24 flows closed on `medical_diagnosis`,
concentrated on `insurance_claim` and `billing_statement`.

### 3.2 Over-blocks introduced — 0 measured, on a narrow scope

Over-blocks are norm violations too (Paper II §III-D) and are reported separately
here, never netted against §3.1.

They are **measured, not asserted**: the fifth check was re-run with subject
linkage taken from the Stage 1c *human labels* instead of the classifier, on the
25 fully-audited documents where every detection carries a label. Flows that flip
back to PERMIT under ground truth are denials caused by linkage error rather than
by the authored policy.

| | |
|---|---:|
| scope | 25 documents, 600 flows, 16 of them denied by check 5 |
| documents where human and classifier type sets differ | 5 of 25 |
| **over-blocks introduced** | **0** (0.00%) |
| flows the classifier let through that ground truth would refuse | 0 |

**The detector was proved capable of firing.** A synthetic correction removing
`ssn` from the audited documents makes it report 6 over-blocks, so the measured 0
is a property of the data, not of a measurement that cannot detect anything.

The five real disagreements fall on `job_title` (3 documents), `name` (1), and
`medical_medication` (1). None changes a decision: `job_title` is permitted to
every role so it is never decisive; the `name` difference is a removal on a
document where no flow was denied on `name`; the `medical_medication` difference
is an addition on a document no in-scope flow reached.

**This is a real result with narrow support.** 600 of 2,520 flows, 16 check-5
denials. It says the linkage error rate has no policy consequence *on this scope*;
it does not establish that for the other 1,920 flows, where no ground truth
exists. See §5.

### 3.3 Denial overlap — 2,342 denials

| classification | flows |
|---|---:|
| role-only | 1,054 |
| both role and attribute | 840 |
| attribute and another check | 219 |
| other check only | 148 |
| **attribute-only** | **81** |

The attribute-only set is exactly the 81 flows of §3.1 — role, context, and
assignment all pass, and only the information-type check refuses them. It is what
the new check uniquely catches, and it is disjoint from everything the existing
gate could reach.

#### Ablation: `permitted_receiver_roles` removed entirely

Rather than assert that the role field and the attribute check do different work,
the role field was removed (every role permitted on every document, in memory
only) and the corpus re-adjudicated.

| | with role field | without |
|---|---:|---:|
| permits, 4 checks | 259 | **427** |
| permits, 5 checks | 178 | **278** |

**The role field uniquely blocks 100 flows** that the attribute check does not
catch — by tier: `internal` 90, `financial` 7, `clinical_standard` 3.

That 90 is the informative number. Internal-tier documents (staff schedules,
meeting agendas, policy memos) carry almost no subject-linked information types,
so the attribute check has nothing to test and passes them freely; only the role
field keeps them from IT Contractors and Patients. **The two fields are not
redundant and neither subsumes the other**: the role field governs documents by
what they *are*, the attribute check governs them by what they *contain*, and a
document with no contents to govern is invisible to the second.

### 3.4 Unreachable documents — 67 of 105

Documents whose own `permitted_receiver_roles` are *all* refused by the fifth
check, and which are therefore reachable by nobody.

| blocked on | documents |
|---|---:|
| `ssn` alone | 22 |
| `date_of_birth`, `home_address`, `name` | 12 |
| `medical_diagnosis`, `medical_medication`, `ssn` | 7 |
| `medical_diagnosis`, `ssn` | 5 |
| `mental_health`, `ssn` | 3 |
| `emergency_contact` + 4 clinical types + `ssn` | 3 |
| `medical_diagnosis`, `medical_medication` | 3 |
| `date_of_birth`, `home_address` | 3 |
| (nine further combinations) | 9 |

By tier: financial 24, clinical_standard 18, employment 18, clinical_sensitive 7.
By document type: `insurance_claim` 8, `clinical_note` 7, `lab_report` 6,
`billing_statement` 6, `salary_letter` 6, `mental_health_assessment` 5,
`employment_contract` 5.

22 are blocked solely by `ssn`; the remaining 45 by combinations.

**This is the most consequential result in Stage 2, and it is not a bug.** Every
one of these documents is refused because its label admits only roles that cannot
lawfully receive everything the document contains. `doc_047`, an insurance claim,
admits only Billing Specialist, and carries `emergency_contact`,
`medical_diagnosis`, `medical_history`, `medical_medication`, and `ssn` — five
types that role may not receive.

The gate can only release or refuse a document whole. The fifth check does not
create that limitation; it makes it *visible*. Paper III's own framing anticipated
this — *"no access-control list fixes this, because the label has no vocabulary
for 'this document minus the diagnosis'"* — and the measurement is the
consequence stated precisely: **under a correct information-type policy, 64% of
this corpus should not exist in its current form.** The remedy is redaction or
document decomposition, neither of which a gate that never reads content can
perform.

Reachable documents fall from 87 to 27.

---

## 4. What each field is doing

Bringing §3.3 together, on the same 2,520 flows:

| mechanism | flows it blocks that nothing else does |
|---|---:|
| `permitted_receiver_roles` | 100 (90 of them `internal`-tier) |
| information-type check | 81 (all attribute-only) |
| both together | 840 |

The tiering, role list, and assignment relation are unchanged from Paper II; the
only new input is `pii_attributes`, a field the schema already carried and that
Paper II's Table IV filed under Records — provenance only, never consulted at
decision time. Paper III makes the gate read a field it already recorded.

---

## 5. Limitations

1. **Over-blocks are measured on 600 of 2,520 flows.** Ground truth exists only
   for the 25 fully-audited documents. The measured 0 is real and the detector is
   proved capable of firing, but 16 check-5 denials in scope is thin support. The
   remaining 1,920 flows have no ground-truth linkage.

2. **The tagger is audited at 0.994 / 1.000, on a corpus it was partly fitted
   to.** The 400-cell pass is complete (`REPORT.md` §4.4): precision 0.994
   [0.969, 0.999], recall 1.000 [0.979, 1.000], **zero misses across 177 present
   cells** — but five of the tagger's rules were revised against this corpus
   (`insurance.member_id`, `diagnosis.labeled`, `employment.agreement_title`,
   `medication.dose_form`, and an added `medical_history` block rule), so those
   figures are an upper bound rather than a field estimate. The qualifier travels
   with the number wherever it appears.

   The limitation has therefore changed shape rather than gone away. What it
   bounds is now known: a tagger miss becomes a silent release that no Stage 2
   measurement can see, because the type never enters the inventory at all — and
   the audit found none, within a sample where rare types are underpowered
   (`contract_terms` n=1, CI [0.21, 1.00]; `emergency_contact` n=4). The single
   false positive — `insurance_info` on `doc_008`, the gazetteer matching
   "Medicaid" in prose — is the class of error that becomes an over-block.

3. **Linkage error is not zero even where measured.** Stage 1d: precision on
   "filtered at all" 0.955, recall on `subject` 0.963, six silent releases
   corpus-wide, and those figures are lower bounds because the annotator was
   instructed to prefer `subject` when torn. Single annotator, no adjudication.

4. **The permission sets are one author's judgement.** There is no second
   authority and no inter-rater measurement on them. That is the correct provenance
   for this paper — the argument is that a *human* must author them, not that this
   particular human is right — but it means the 81 closed flows and 67 unreachable
   documents are consequences of one normative reading, not of a validated one.

5. **The unreachable-document result depends on the corpus being
   specification-first.** Labels were authored before content, and Stage 1 found
   `pii_attributes` describes a document's *purpose* rather than its *contents*
   (0 of 105 documents matched exactly; 520 found-but-not-authored pairs, 459
   subject-linked). A corpus whose labels were derived from content would show
   fewer unreachable documents. The finding is about a real and common failure
   mode, but its magnitude here is partly an artefact of how the corpus was built.

6. **`job_title` permitted to every role** means the check never fires on it,
   confirmed as intended. Its 24 documents and 23 flows are unaffected by design.

7. **Documents with no subject-linked types pass the check trivially** — this is
   why the role-field ablation exposes 90 `internal`-tier flows. The fifth check
   provides no protection where the linkage layer found nothing, whether because
   nothing is there or because nothing was detected.

---

## 6. Reproducing

```
cd "CI Sim"
python -m stage2.build_template          # 2a: blank template + impact preview
python -m stage2.validate_permissions --template stage2/artifacts/permission_template_v1.2.0.xlsx
python -m stage2.extended_gate           # property verification
python -m stage2.adjudicate              # 2b: re-adjudication + measurements
```

Standard library only. Deterministic and timestamp-free; all artifacts reproduce
byte-for-byte on re-run (verified). Every module aborts if the corpus SHA-256, the
vocabulary version, or the linkage version has moved — the vocabulary is frozen and
a change means re-authoring the permission sets.

### Artifacts

| file | contents |
|---|---|
| `artifacts/permission_template_v1.2.0.{csv,xlsx}` | the blank template, and the authored version |
| `artifacts/role_permissions_v1.2.0.json` | the validated sets |
| `artifacts/validation_report_v1.2.0.json` | every validation check and its result |
| `artifacts/impact_preview_v1.2.0.{json,csv}` | per-type impact, authoring input |
| `artifacts/adjudication_v1.2.0.csv` | all 2,520 flows under both gates |
| `artifacts/adjudication_v1.2.0.json` | summary, property proofs, all four measurements |
| `artifacts/over_delivery_v1.2.0.csv` | the 81 closed flows |
| `artifacts/unreachable_documents_v1.2.0.csv` | the 67 unreachable documents |

### Changes to existing files

None. Stage 2 added `stage2/` and wrote nothing outside it. `core/ci_policy.py`
is unmodified — the extended gate calls it. The corpus, labels, assignment
relation, vocabulary, and all Stage 1 artifacts are untouched;
`data/dataset.json` still hashes to `49cdd9c8…`.
