# Role Permission Rationale — vocabulary v1.2.0

**Provenance.** The 96 permission decisions were authored by the researcher; no
model proposed, ranked, or defaulted any of them. The justifying prose was
drafted with model assistance and has been reviewed and edited by the author.
The authoritative record of *what* was decided is
`role_permissions_v1.2.0.json`; this file explains, it does not decide.

Lines flagged **`INERT ON THIS CORPUS`** mark decisions the gate never exercises
here — because the role check already excludes that role, or because no flow
carries the type — so they are unconstrained by any measurement.

---

**Decisions:** 96 (16 types × 6 roles) · **Source:**
`permission_template_v1.2.0.xlsx` · **Validated:** 96/96, no blanks, no
unrecognised values
**Corpus:** 105 documents, 24 agents, 2,520 flows · **Baseline permits** 259 →
**extended** 178

Legend: **P** = permit, **·** = deny.

---

## 1. `name`

> Personal name of a natural person (patient, employee, contractor, or named
> provider).

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | · | · | **P** |

Subject-linked in **91** documents · permitted flows carrying it: **105** ·
flows closed: **14** (sole cause in 0)
Tiers: clinical_standard 39, financial 25, employment 17, clinical_sensitive 10

**Rationale:**

>
> The three roles with a care or billing relationship to an identified patient
> cannot perform their function without the patient's name. Patient receives their own name trivially.
>
> HR Manager and IT Contractor are denied because neither has a basis for
> learning *which* individual a clinical or financial record concerns. The IT
> Contractor denial is the stronger of the two and is consistent with the
> contractor agreements in this corpus, which state "no PHI access permitted" as
> an explicit term. HR Manager's denial is narrower: HR documents
> have staff as their subject and are governed by the same cell, so the effect is
> that HR may not learn patient identities from clinical records, not that HR may
> never see a name.
>
> **INERT ON THIS CORPUS — Patient.** No document in this corpus admits `Patient`
> in `permitted_receiver_roles` alongside `name`, and no patient agent holds a
> knowledge-base entry, so this permit is never exercised.

---

## 2. `date_of_birth`

> A person's date of birth, in any format.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | · | · | **P** |

Subject-linked in **95** documents (the most of any type) · permitted flows:
**109** · flows closed: **18** (sole cause in 0)
Tiers: clinical_standard 39, financial 25, employment 21, clinical_sensitive 10

**Rationale:**

> Date of birth is the primary disambiguator in clinical and billing practice —
> the field that distinguishes two patients of the same name — and is a required
> element on most payer claim forms. Denying it to Doctor, Nurse, or Billing
> Specialist would make correct patient identification harder rather than safer.
>
> It tracks `name` exactly across all six roles, which is coherent: both are
> identity-family types whose function is to establish *who*, and a role that may
> learn the name has no additional protection from being denied the birth date.
>
> Worth noting for the discussion: DOB is a HIPAA Safe Harbor identifier, so
> permitting it to three roles is a substantive disclosure decision rather than a
> formality, even though it reveals nothing clinical.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 3. `ssn` — the only fully-locked type

> Social Security Number, whole or partially masked.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| · | · | · | · | · | **P** |

Subject-linked in **44** documents · permitted flows: **57** · **flows closed:
57 (sole cause in 36)** — the largest single contributor to over-delivery closed
Tiers: financial 19, clinical_standard 18, clinical_sensitive 7

**Rationale:**

> 
>
> **Why denied to every clinical and administrative role.** An SSN supports no
> clinical task. It does not identify a patient within a practice (the MRN and DOB
> do that), it is not required to render treatment, and it is not needed to code a
> claim. Under the HIPAA minimum-necessary standard at 45 CFR 164.502(b), a
> covered entity must limit disclosure to the minimum necessary to accomplish the
> purpose — and for every role here, the minimum necessary excludes the SSN. That
> the treatment exemption at 164.502(b)(2)(i) lifts minimum-necessary for
> treatment disclosures does not change the analysis: the exemption permits
> disclosure of what treatment requires, and treatment does not require an SSN.
> The exemption removes a ceiling; it does not create a need.
>
> The deny to Billing Specialist deserves separate defence, because billing is
> where an SSN most plausibly belongs. Modern payer claims key on the member
> identifier, not the SSN; `insurance_info` is permitted to Billing Specialist and
> carries exactly that. The SSN's presence on these documents is an artifact of
> form design rather than a billing requirement.
>
> **Why permitted to Patient.** The subject's own SSN is theirs. Denying it would
> make the type unreachable by anyone, which is a coherent policy but a different
> one — it would say the SSN should not be in the record at all, which is arguably
> true but is not a decision an access gate can express.
>
> **Consequences, stated because they are large.** This single row closes 57 of
> the 81 over-delivered flows and is the sole cause in 36. It also renders 22
> documents unreachable on its own and contributes to 30 of the 33 documents with
> bundle size ≥ 9 (`stage2/generalization.py`). No patient agent holds a
> knowledge-base entry in this corpus, so `Patient` is never an admitted role on
> those documents and the single permit never fires.
>
> The row is therefore doing something unusual: it is a policy statement whose
> practical effect on this corpus is to make 44 documents undeliverable to
> anybody. That is the correct outcome if the premise holds — an SSN printed on a
> clinical note is over-collection, and the remedy is to stop printing it, not to
> widen who may receive it. The author should confirm that reading is intended,
> because the alternative framing (that the fifth check is too blunt here) leads
> to a different paper.
>
> **INERT ON THIS CORPUS — Patient**, for the reason given above.

---

## 4. `home_address`

> Residential street address of a person. Excludes the clinic's own premises
> address.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | · | · | **P** |

Subject-linked in **85** documents · permitted flows: **97** · flows closed:
**18** (sole cause in 0)
Tiers: clinical_standard 32, financial 23, employment 21, clinical_sensitive 9

**Rationale:**

>
> Address supports functions all three permitted roles perform: care coordination
> and follow-up for clinicians, statement delivery and eligibility verification
> for billing. It is also a Safe Harbor identifier, so the decision is substantive
> — but the operational need is real and continuous rather than occasional.
>
> Tracking `name` and `date_of_birth` across all six roles keeps the identity
> family internally consistent: a role that may learn who the subject is and when
> they were born gains little additional exposure from knowing where they live,
> and the three fields travel together on every form in this corpus.
>
> The v1.2.0 definition's exclusion of the clinic's premises address matters
> operationally rather than normatively — it is what keeps the letterhead on 103
> of 105 documents from registering as the subject's address — but it is the
> reason this row governs 85 documents rather than effectively all of them.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 5. `emergency_contact` — permitted to HR, denied to Billing

> The subject's designated emergency or guardian contact — the identity of the
> person the subject nominated, with or without a phone number. This is an
> attribute OF THE SUBJECT: under HIPAA the emergency contact recorded in a
> patient record forms part of the designated record set, and is therefore PHI
> about the patient. Who the subject designated is a relational fact about the
> subject, not merely a record about the contact. Always subject-linked; see
> SUBJECT_LINKED_BY_DEFINITION.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | · | **P** | · | **P** |

Subject-linked in **22** documents · permitted flows: **32** · flows closed:
**5** (sole cause in 0)
Tiers: clinical_standard 16, financial 5, clinical_sensitive 1

**Rationale:**

>
> This is the second unconventional row, and the asymmetry is the whole point:
> **permitted to HR Manager, denied to Billing Specialist** — the only type in the
> table where HR is trusted with something billing is not.
>
> **Why HR.** An emergency contact is the one identity-family field whose purpose
> is symmetric across the clinical and employment contexts. Employers hold
> emergency contacts for staff as a matter of ordinary duty-of-care and
> occupational-safety practice; it is arguably the most routine record HR keeps.
> Because the employment tier inverts the subject (Stage 1b §1.1), the HR cell
> governs *staff* emergency contacts on employment-tier documents, which is
> precisely the case where HR's need is strongest.
>
> **Why not Billing.** Billing has no corresponding function. A claim is
> adjudicated against the subscriber and the payer; who the patient nominated to
> be called in a crisis bears on none of it. Under minimum-necessary this fails
> cleanly, and it fails in the direction the standard is designed to catch —
> information that arrives because it happens to be printed on a form the role
> legitimately receives, rather than because the role needs it.
>
> **The second-subject problem, restated.** The v1.2.0 definition resolves the
> type as the subject's attribute on designated-record-set grounds, and that is
> right for the patient. It also means the contact — a real third party who never
> consented to anything — has their name and phone number governed entirely by the
> *patient's* permissions. A role permitted the patient's identity attributes
> receives the contact's details as a side effect, and nothing in the gate
> represents that person's interest. `REPORT_1B.md` §6.7 records this as a stated
> limitation rather than a modelled one, because the gate assumes one subject per
> document while Contextual Integrity does not require that.
>
> **INERT ON THIS CORPUS — HR Manager, Patient.** No document admitting HR Manager
> carries `emergency_contact` as subject-linked, so the HR permit — the most
> distinctive decision in this row — is never exercised on this corpus. It rests
> entirely on the reasoning above and on no measurement, which is exactly why it
> warrants review.

---

## 6. `medical_diagnosis`

> A current or working clinical diagnosis, stated in words or encoded as a
> diagnostic code.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | · | · | · | **P** |

Subject-linked in **70** documents · permitted flows: **85** · **flows closed:
24** (sole cause in 2)
Tiers: clinical_standard 37, financial 24, clinical_sensitive 9

**Rationale:**

>
> Diagnosis is the paradigm case of treatment information: Doctor and Nurse
> receive it under the treatment exemption at 45 CFR 164.502(b)(2)(i), which lifts
> minimum-necessary for disclosures for treatment purposes precisely because
> clinicians cannot know in advance which clinical facts will matter.
>
> **The Billing Specialist denial is the paper's motivating example, made
> operational.** A Billing Specialist correctly receives an insurance claim under
> the role check — that is what `permitted_receiver_roles` is for — and the
> diagnosis printed on it travels with the document. This cell is what separates
> the two. The result: 24 flows closed, concentrated on `insurance_claim` and
> `billing_statement`.
>
> The obvious objection is that billing *requires* diagnostic information, since
> payers adjudicate on medical necessity. The answer is the type boundary:
> `billing_code` is permitted to Billing Specialist and carries the ICD-10 code
> that supports adjudication. What is denied is the diagnosis stated as a clinical
> fact. Whether that boundary survives contact with the `E11.9` collision is an
> open question — see §17.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 7. `medical_medication`

> A prescribed or administered drug, typically with dose and frequency.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | · | · | · | **P** |

Subject-linked in **64** documents · permitted flows: **77** · flows closed:
**18** (sole cause in 0)
Tiers: clinical_standard 36, financial 18, clinical_sensitive 10

**Rationale:**
>
> Tracks `medical_diagnosis` exactly, and for the same reason: medication is
> treatment information, covered by the treatment exemption for clinicians and
> outside minimum-necessary for everyone else.
>
> Medication also carries diagnostic inference, often more sharply than a
> diagnosis code — an antiretroviral regimen discloses HIV status, buprenorphine
> discloses opioid use disorder — so permitting it more widely than
> `medical_diagnosis` would be incoherent. Both appear in this corpus:
> `Biktarvy` on `doc_008`, `Buprenorphine/Naloxone` on the substance-use records.
> A policy that denied diagnosis to Billing but permitted medication would leak
> the diagnosis through the drug name.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 8. `medical_history`

> Past conditions, procedures, or clinical events, as distinct from the current
> presenting diagnosis.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | · | · | · | **P** |

Subject-linked in **27** documents · permitted flows: **33** · flows closed:
**4** (sole cause in 0)
Tiers: clinical_standard 19, clinical_sensitive 4, financial 4

**Rationale:**

>
> Follows the clinical family. Past conditions inform current care — comorbidities
> drive contraindications and dosing — so the treatment exemption applies to
> clinicians with the same force as for current diagnosis, and the same
> minimum-necessary analysis excludes the administrative roles.
>
> Distinguishing history from current diagnosis is a clinical convenience rather
> than a privacy boundary: a past psychiatric admission is no less sensitive for
> being past, and in some respects more so, because it is less likely to be
> clinically relevant and therefore harder to justify under minimum-necessary. The
> decisions being identical across the two types reflects that the distinction
> does not do normative work here.
>
> One boundary the linkage layer resolves rather than this table: `FAMILY HISTORY`
> sections describe relatives, and Stage 1b classifies those as third-party, so
> they never reach this check.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 9. `mental_health` *(extra-sensitive)*

> Psychiatric or substance-use diagnosis, assessment instrument score, or
> treatment detail. The extra-sensitive subset of the clinical family.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | · | · | · | · | **P** |

Subject-linked in **19** documents · permitted flows: **22** · flows closed:
**7** (sole cause in 0)
Tiers: clinical_sensitive 10, clinical_standard 4, employment 4, financial 1

**Rationale:**

>
> The only clinical type where Doctor and Nurse diverge, which is the substantive
> decision in this row.
>
> Heightened protection reflects statute rather than preference: 42 CFR Part 2
> governs substance-use-disorder records with consent requirements stricter than
> HIPAA's, and the Illinois MHDDCA (740 ILCS 110) governs mental-health records in
> this corpus's jurisdiction. Both appear in the documents themselves as
> confidentiality notices. The existing gate already encodes this at the document
> level — `extra_sensitive=True` restricts `permitted_receiver_roles` to Doctor on
> `mental_health_assessment` records — so denying Nurse here aligns the
> attribute-level policy with the document-level one already in force.
>
> The reason the alignment matters is leakage across document types. The 19
> documents carrying subject-linked mental-health information are not confined to
> the `clinical_sensitive` tier: 4 are `clinical_standard`, 4 `employment`, 1
> `financial`. Those documents are *not* restricted to Doctor by
> `permitted_receiver_roles`, so without this cell a Nurse or Billing Specialist
> would receive psychiatric information carried incidentally on an ordinary
> clinical note or a claim. This row is what closes that path — 7 flows.
>
> The Nurse denial has a real cost, and it should be acknowledged rather than
> assumed away: a nurse administering psychiatric medication has a genuine
> clinical need. On this corpus the cost is 7 flows; in deployment it would be a
> live operational objection, and the honest answer is that a role-scoped policy
> cannot express "the nurse on this patient's psychiatric care team but not
> others" — that is what the assignment check does, and it is a separate term in
> the conjunction.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 10. `billing_code`

> A procedure or diagnosis code used for billing — CPT, HCPCS, or ICD-10.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | · | · | **P** |

Subject-linked in **65** documents · permitted flows: **81** · **flows closed:
0**
Tiers: clinical_standard 34, financial 22, clinical_sensitive 9

**Rationale:**

>
> Billing Specialist's core working material: a claim cannot be prepared,
> submitted, or reconciled without the procedure and diagnosis codes. Clinicians
> receive it because they generate it and must verify it before attestation.
>
> **Zero flows closed** — every role admitted alongside this type on this corpus
> may already receive it. The cell does no work here, which is the correct outcome
> for a type whose distribution matches its permission set.
>
> The uncomfortable part is the relationship to `medical_diagnosis`. An ICD-10
> code *is* a diagnosis in encoded form — `core/ci_policy.py` has recorded exactly
> that in `ATTRIBUTE_IMPLICATIONS` since Paper II, where `billing_code` implies
> `medical_diagnosis`. Permitting `billing_code` to Billing Specialist while
> denying `medical_diagnosis` therefore draws a line that the vocabulary can
> express but the values cannot always sustain. See §17.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 11. `insurance_info`

> Payer identity, plan type, and/or member, policy, or group identifier.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | · | · | **P** |

Subject-linked in **71** documents · permitted flows: **91** · **flows closed:
0**
Tiers: clinical_standard 36, financial 25, clinical_sensitive 10

**Rationale:**

>
> Eligibility verification, prior authorisation, and claim submission all require
> the payer and member identifier; clinicians need coverage status to know what
> can be ordered. Permitting it to Billing Specialist is what makes the `ssn`
> denial coherent — the member ID is the identifier billing actually needs, so
> denying the SSN removes something redundant rather than something load-bearing.
>
> **Zero flows closed**, as for `billing_code`.
>
> Note for the write-up: coverage type can itself disclose clinical information —
> Medicaid, Medicare Part A vs B, or a specialty pharmacy plan each narrow the
> population. The type is treated as financial here, which is standard, but it is
> not inference-free. This corpus's single tagger false positive is also in this
> type: `insurance.carrier_plan` matching the bare word "Medicaid" in prose on
> `doc_008`.
>
> **INERT ON THIS CORPUS — Patient**, as for `name`.

---

## 12. `salary`

> An individual's compensation figure — annual salary, base pay, or contractor
> hourly rate.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | **P** | · | · |

Subject-linked in **20** documents · permitted flows: **17** · **flows closed:
0**
Tiers: employment 20 (exclusively)

**Rationale:**

>
> HR Manager is the substantive permit: compensation administration is the
> function. IT Contractor is denied consistently with the no-PHI-and-no-personnel
> posture of the contractor agreements. Patient is denied because a patient has no
> standing to receive staff compensation, and the employment inversion means this
> cell governs staff subjects.
>
> **The Doctor, Nurse, and Billing permits are the ones to scrutinise.** All three
> are **INERT ON THIS CORPUS** for Nurse and Billing Specialist — no document
> admitting those roles carries subject-linked `salary` — and in practice the role
> check already excludes clinicians from `salary_letter` and `performance_review`
> records, so the fifth check never reaches them. **Zero flows closed.**
>
> That inertness is exactly why these cells need review. They are unconstrained by
> any measurement in this corpus: three permits that assert clinicians may receive
> staff compensation figures, resting on the role check to prevent it. If
> `permitted_receiver_roles` were ever widened — or if a compensation figure
> appeared on a document clinicians may receive — these cells would become live
> and would permit something the author may not intend. A deny would have been the
> defence-in-depth choice and costs nothing on this corpus.

---

## 13. `employment_contract`

> The existence, identifier, or terms of an employment agreement.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | **P** | **P** | · |

Subject-linked in **17** documents · permitted flows: **17** · **flows closed:
0**
Tiers: employment 16, financial 1

**Rationale:**
>
> Permitted to all five staff roles and denied only to Patient. The reading that
> makes this coherent: the existence and basic terms of an employment relationship
> are ordinary organisational facts among colleagues — who is employed, in what
> capacity, from when — rather than confidential personal information. The
> confidential part is the compensation figure, which `salary` governs separately
> and more tightly.
>
> Patient is denied because a patient has no standing in the clinic's employment
> relationships.
>
> **INERT ON THIS CORPUS — IT Contractor**: no document admitting IT Contractor
> carries subject-linked `employment_contract`. **Zero flows closed** overall.
>
> Worth the author's attention: the definition covers "the existence, identifier,
> **or terms**" of an agreement, and "terms" can extend to matters closer to
> `salary` than to a job title — probationary status, notice periods,
> restrictive covenants. The broad permit is defensible for existence and
> identifier and harder to defend for terms. Narrowing the definition is not
> available (v1.2.0 is frozen), so this should be noted as a scope question for a
> future version rather than patched.

---

## 14. `contract_terms`

> Terms of a non-employee contractor engagement — scope, rate, restrictions.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | **P** | **P** | · |

Subject-linked in **2** documents · **permitted flows: 0** · flows closed: **0**
Tiers: employment 2

**Rationale:**

> Mirrors `employment_contract`: the terms of a vendor engagement — scope of
> services, rate, the PHI-prohibition clause — are operational facts staff may
> need in order to work with a contractor, and the contractor is party to their
> own agreement. Patient is denied for the same standing reason.
>
> **INERT ON THIS CORPUS IN FULL.** This type is subject-linked in only 2
> documents and carried by **zero** permitted flows, so no cell in this row is
> exercised by any of the 2,520 flows under either gate. The entire row is a
> normative statement with no measurement behind it — four permits to roles the
> corpus never tests, for a type the corpus barely contains.
>
> This is the weakest-supported row in the table and should be read as such. It
> costs nothing here and constrains nothing here; its only effect would be in a
> deployment with more contractor documentation.

---

## 15. `job_title`

> A person's occupational role or position within the organization. OWNERSHIP
> BOUNDARY (v1.2.0): a title is subject- or third-party-linked only where it is
> asserted OF AN IDENTIFIED INDIVIDUAL — 'Position: Staff Psychiatrist' on that
> clinician's own contract, or 'Attending Physician: Dr. Nguyen' naming a specific
> clinician. A STAFFING HEADCOUNT ('2 RN, 1 Billing Specialist', 'Medical
> Assistant: 1 per shift') names no individual and identifies no one; it is a
> resource count rather than personal information about a person, and is
> organizational.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | **P** | **P** | **P** |

Subject-linked in **24** documents · permitted flows: **23** · **flows closed:
0**
Tiers: employment 20, clinical_standard 3, financial 1

**Rationale:**


>
> **The only type permitted to every role, so the fifth check never fires on it.**
> Validation surfaced this for confirmation and the author confirmed it as
> intended.
>
> The reasoning: a job title is the least sensitive attribute in the vocabulary. A
> clinician's role is displayed on their badge, printed in signature blocks, and
> disclosed to every patient they treat; concealing it would impede care
> coordination while protecting nothing. The v1.2.0 boundary ruling already
> removes the case that might have justified restriction — staffing headcounts,
> which could disclose operational capacity — by classifying those as
> organisational before this check sees them.
>
> A universally-permitted type is a reasonable thing for a vocabulary to contain;
> it marks the floor. But it is worth stating in the write-up that one of the 16
> types is inert by construction, so the effective vocabulary for the fifth check
> is 15.
>
> **INERT ON THIS CORPUS — IT Contractor, Patient** specifically; and the row as a
> whole never fires.

---

## 16. `medical_license`

> A clinician credential identifier — state medical license, NPI, or DEA
> registration number. OWNERSHIP BOUNDARY (v1.2.0): an NPI is syntactically
> identical whether individual or organisational, so ownership follows the entity
> the credential is asserted of. A Type 1 NPI belongs to the individual clinician
> and is third-party on a patient record (subject on that clinician's own
> employment record). A Type 2 NPI belongs to the organisation — 'Facility NPI:',
> 'Group NPI:', or an attribution block opened on the practice rather than a
> person — and is organizational.

| Doctor | Nurse | Billing | HR | IT | Patient |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **P** | **P** | **P** | **P** | · | **P** |

Subject-linked in **13** documents · permitted flows: **13** · **flows closed:
0**
Tiers: employment 11, financial 2

**Rationale:**

> **This row resolves the false-denial case that motivated Stage 1b.** A doctor's
> signature block on an insurance claim causes the document to carry
> `medical_license`; had Billing Specialist been denied it, the gate would have
> refused the claim *because a doctor signed it* — a bug wearing the costume of a
> privacy control. Permitting it prevents that, and it is independently correct:
> NPI and state licence numbers are published in public registries (NPPES,
> state medical boards), so they are not confidential at all.
>
> Only 13 documents carry it as subject-linked, against 39 where the tagger
> detects it — the difference is the Stage 1b/1d linkage layer correctly
> attributing most occurrences to the signing clinician as third-party rather than
> to the document's subject. The 13 remaining are credentialing files and salary
> letters where the clinician *is* the subject.
>
> IT Contractor is denied, consistently with the no-PHI posture, though the
> public-registry argument makes this the least consequential denial in the table.
>
> **INERT ON THIS CORPUS — Nurse, Patient.** **Zero flows closed.**

---

## 17. Accepted limitation — the `E11.9` collision

The same value appears as an example under two types with different Billing
Specialist permissions:

| type | example value | Billing Specialist |
|---|---|:-:|
| `billing_code` | `ICD-10 E11.9` | **permit** |
| `medical_diagnosis` | `Type 2 Diabetes Mellitus (E11.9)` | **deny** |

The two types are separated **by context, not by value**. `E11.9` reaches
`billing_code` when it appears under a billing label or in a claim line item, and
`medical_diagnosis` when it appears in an assessment or diagnosis section. The
tagger's rules (`billing.icd_labeled`, `billing.cpt_line_item` versus
`diagnosis.icd_nonpsych`, `diagnosis.labeled`) implement that separation
positionally.

**This is recorded as an accepted limitation, not a resolved question.**

What it means in practice: a Billing Specialist denied `medical_diagnosis` may
still receive the identical ICD-10 code through `billing_code`, and an ICD-10 code
is a diagnosis in encoded form. `core/ci_policy.py` has said so since Paper II —
`ATTRIBUTE_IMPLICATIONS` records that `billing_code` implies
`medical_diagnosis` — and the fifth check does not consult that table. The 24
flows closed on `medical_diagnosis` therefore close a *stated* diagnosis while
leaving the *encoded* one open on the same documents.

Three honest observations:

1. **The boundary is defensible operationally.** Billing genuinely needs the code
   and genuinely does not need the clinical narrative, and a policy that denied
   both would make claims processing impossible. The distinction is not arbitrary.
2. **It is not defensible informationally.** Anyone with an ICD-10 lookup can
   recover the diagnosis from the code. The protection is procedural, not
   semantic.
3. **Closing it is out of scope here and should be named as future work.** It
   would require either propagating `ATTRIBUTE_IMPLICATIONS` through the fifth
   check — so that permitting `billing_code` implies permitting
   `medical_diagnosis`, which would make the two cells inconsistent and force
   re-authoring — or splitting `billing_code` into procedure and diagnosis codes,
   which changes the frozen vocabulary.

The limitation should appear in the paper alongside the `medical_diagnosis`
result rather than only in this file, because it bounds what the 24 closed flows
actually achieve.

---

*Decisions: `stage2/artifacts/role_permissions_v1.2.0.json` (authoritative).
Figures: `impact_preview_v1.2.0.json`, `adjudication_v1.2.0.json`,
`generalization_v1.2.0.json`. Rationale prose: drafted with model assistance,
reviewed and edited by the author.*
