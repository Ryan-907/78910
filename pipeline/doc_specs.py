"""
Riverside Medical Clinic — Document Specification Matrix

Each entry in ALL_SPECS defines one document to be generated.
The spec is the ground-truth CI label; the generation pipeline
reads it, calls Claude to produce content, and saves the result.

Fields
------
document_type           : DocumentType constant
originating_context     : OriginatingContext constant
subject_type            : SubjectType constant
subject_name            : key into EXTENDED_NAME_REGISTRY (or None for org-level)
sensitivity_tier        : SensitivityTier constant
extra_sensitive         : bool
extra_sensitive_reason  : "mental_health" | "substance_abuse" | "hiv_aids" | "reproductive" | None
pii_attributes          : list[AttributeType] — explicitly present
implied_attributes      : list[AttributeType] — inferrable
permitted_receiver_roles: list[str]
assignment_required     : bool
governing_principle     : TransmissionPrinciple constant | None
date                    : ISO-8601 document date string
scenario_hint           : one-sentence description guiding generation
"""

from core.Agent import (
    AttributeType, DocumentType, SensitivityTier,
    OriginatingContext, TransmissionPrinciple, SubjectType,
)

# ---------------------------------------------------------------------------
# Helper builders — reduce repetition for common document patterns
# ---------------------------------------------------------------------------

def _clinical_note(subject, date, hint, extra_sensitive=False, extra_sensitive_reason=None):
    roles = ["Doctor"] if extra_sensitive else ["Doctor", "Nurse"]
    tier  = SensitivityTier.CLINICAL_SENSITIVE if extra_sensitive else SensitivityTier.CLINICAL_STANDARD
    piis  = [AttributeType.MEDICAL_DIAGNOSIS, AttributeType.MEDICAL_MEDICATION,
             AttributeType.MEDICAL_HISTORY, AttributeType.DATE_OF_BIRTH]
    return dict(
        document_type=DocumentType.CLINICAL_NOTE,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=tier,
        extra_sensitive=extra_sensitive, extra_sensitive_reason=extra_sensitive_reason,
        pii_attributes=piis, implied_attributes=[],
        permitted_receiver_roles=roles, assignment_required=True,
        governing_principle=(TransmissionPrinciple.TREATMENT_SENSITIVE if extra_sensitive
                             else TransmissionPrinciple.TREATMENT),
        scenario_hint=hint,
    )

def _prescription(subject, date, hint):
    return dict(
        document_type=DocumentType.PRESCRIPTION,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.MEDICAL_MEDICATION, AttributeType.DATE_OF_BIRTH,
                        AttributeType.MEDICAL_LICENSE],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        permitted_receiver_roles=["Doctor", "Nurse"], assignment_required=True,
        governing_principle=TransmissionPrinciple.TREATMENT,
        scenario_hint=hint,
    )

def _lab_report(subject, date, hint):
    return dict(
        document_type=DocumentType.LAB_REPORT,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.MEDICAL_DIAGNOSIS, AttributeType.MEDICAL_MEDICATION,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse"], assignment_required=True,
        governing_principle=TransmissionPrinciple.TREATMENT,
        scenario_hint=hint,
    )

def _radiology(subject, date, hint):
    return dict(
        document_type=DocumentType.RADIOLOGY_REPORT,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.MEDICAL_DIAGNOSIS, AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse"], assignment_required=True,
        governing_principle=TransmissionPrinciple.TREATMENT,
        scenario_hint=hint,
    )

def _discharge(subject, date, hint):
    return dict(
        document_type=DocumentType.DISCHARGE_SUMMARY,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.MEDICAL_DIAGNOSIS, AttributeType.MEDICAL_HISTORY,
                        AttributeType.DATE_OF_BIRTH, AttributeType.HOME_ADDRESS,
                        AttributeType.EMERGENCY_CONTACT],
        implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse"], assignment_required=True,
        governing_principle=TransmissionPrinciple.TREATMENT,
        scenario_hint=hint,
    )

def _mental_health(subject, date, hint, extra_sensitive_reason="mental_health"):
    return dict(
        document_type=DocumentType.MENTAL_HEALTH_ASSESSMENT,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.CLINICAL_SENSITIVE,
        extra_sensitive=True, extra_sensitive_reason=extra_sensitive_reason,
        pii_attributes=[AttributeType.MENTAL_HEALTH, AttributeType.MEDICAL_MEDICATION,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["Doctor"], assignment_required=True,
        governing_principle=TransmissionPrinciple.TREATMENT_SENSITIVE,
        scenario_hint=hint,
    )

def _referral(subject, date, hint):
    return dict(
        document_type=DocumentType.REFERRAL_LETTER,
        originating_context=OriginatingContext.MEDICAL,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.MEDICAL_DIAGNOSIS, AttributeType.MEDICAL_HISTORY,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["Doctor"], assignment_required=True,
        governing_principle=TransmissionPrinciple.TREATMENT,
        scenario_hint=hint,
    )

def _insurance_claim(subject, date, hint):
    return dict(
        document_type=DocumentType.INSURANCE_CLAIM,
        originating_context=OriginatingContext.ADMINISTRATIVE,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.FINANCIAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.BILLING_CODE, AttributeType.INSURANCE_INFO,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        permitted_receiver_roles=["Billing Specialist"], assignment_required=True,
        governing_principle=TransmissionPrinciple.BILLING,
        scenario_hint=hint,
    )

def _billing_statement(subject, date, hint):
    return dict(
        document_type=DocumentType.BILLING_STATEMENT,
        originating_context=OriginatingContext.ADMINISTRATIVE,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.FINANCIAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.BILLING_CODE, AttributeType.INSURANCE_INFO,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        permitted_receiver_roles=["Billing Specialist"], assignment_required=True,
        governing_principle=TransmissionPrinciple.BILLING,
        scenario_hint=hint,
    )

def _prior_auth(subject, date, hint, extra_sensitive=False, extra_sensitive_reason=None):
    roles = ["Doctor"] if extra_sensitive else ["Doctor", "Billing Specialist"]
    tier  = SensitivityTier.CLINICAL_SENSITIVE if extra_sensitive else SensitivityTier.FINANCIAL
    return dict(
        document_type=DocumentType.PRIOR_AUTHORIZATION,
        originating_context=OriginatingContext.ADMINISTRATIVE,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=tier,
        extra_sensitive=extra_sensitive, extra_sensitive_reason=extra_sensitive_reason,
        pii_attributes=[AttributeType.MEDICAL_DIAGNOSIS, AttributeType.MEDICAL_MEDICATION,
                        AttributeType.INSURANCE_INFO, AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=roles, assignment_required=True,
        governing_principle=(TransmissionPrinciple.TREATMENT_SENSITIVE if extra_sensitive
                             else TransmissionPrinciple.BILLING),
        scenario_hint=hint,
    )

def _eob(subject, date, hint):
    return dict(
        document_type=DocumentType.EXPLANATION_OF_BENEFITS,
        originating_context=OriginatingContext.ADMINISTRATIVE,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.FINANCIAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.BILLING_CODE, AttributeType.INSURANCE_INFO,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        permitted_receiver_roles=["Billing Specialist"], assignment_required=True,
        governing_principle=TransmissionPrinciple.BILLING,
        scenario_hint=hint,
    )

def _insurance_verify(subject, date, hint):
    return dict(
        document_type=DocumentType.INSURANCE_VERIFICATION,
        originating_context=OriginatingContext.ADMINISTRATIVE,
        subject_type=SubjectType.PATIENT,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.FINANCIAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.INSURANCE_INFO, AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["Billing Specialist", "Doctor", "Nurse"],
        assignment_required=True,
        governing_principle=TransmissionPrinciple.BILLING,
        scenario_hint=hint,
    )

def _salary_letter(subject, date, hint):
    return dict(
        document_type=DocumentType.SALARY_LETTER,
        originating_context=OriginatingContext.HR,
        subject_type=SubjectType.EMPLOYEE,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.SALARY, AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["HR Manager"], assignment_required=True,
        governing_principle=TransmissionPrinciple.HR_CONFIDENTIAL,
        scenario_hint=hint,
    )

def _employment_contract(subject, date, hint):
    return dict(
        document_type=DocumentType.EMPLOYMENT_CONTRACT,
        originating_context=OriginatingContext.HR,
        subject_type=SubjectType.EMPLOYEE,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.SALARY, AttributeType.EMPLOYMENT_CONTRACT,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["HR Manager"], assignment_required=True,
        governing_principle=TransmissionPrinciple.HR_CONFIDENTIAL,
        scenario_hint=hint,
    )

def _performance_review(subject, date, hint):
    return dict(
        document_type=DocumentType.PERFORMANCE_REVIEW,
        originating_context=OriginatingContext.HR,
        subject_type=SubjectType.EMPLOYEE,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.EMPLOYMENT_CONTRACT, AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["HR Manager"], assignment_required=True,
        governing_principle=TransmissionPrinciple.HR_CONFIDENTIAL,
        scenario_hint=hint,
    )

def _credentialing(subject, date, hint):
    return dict(
        document_type=DocumentType.CREDENTIALING_FILE,
        originating_context=OriginatingContext.HR,
        subject_type=SubjectType.EMPLOYEE,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.MEDICAL_LICENSE, AttributeType.EMPLOYMENT_CONTRACT,
                        AttributeType.DATE_OF_BIRTH],
        implied_attributes=[],
        permitted_receiver_roles=["HR Manager", "Doctor"], assignment_required=True,
        governing_principle=TransmissionPrinciple.HR_CONFIDENTIAL,
        scenario_hint=hint,
    )

def _contractor_agreement(subject, date, hint):
    return dict(
        document_type=DocumentType.CONTRACTOR_AGREEMENT,
        originating_context=OriginatingContext.HR,
        subject_type=SubjectType.CONTRACTOR,
        subject_name=subject, date=date,
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.CONTRACT_TERMS, AttributeType.DATE_OF_BIRTH,
                        AttributeType.HOME_ADDRESS],
        implied_attributes=[],
        permitted_receiver_roles=["HR Manager"], assignment_required=True,
        governing_principle=TransmissionPrinciple.HR_CONFIDENTIAL,
        scenario_hint=hint,
    )

def _staff_schedule(date, hint):
    return dict(
        document_type=DocumentType.STAFF_SCHEDULE,
        originating_context=OriginatingContext.INTERNAL,
        subject_type=SubjectType.ORGANIZATION,
        subject_name=None, date=date,
        sensitivity_tier=SensitivityTier.INTERNAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[], implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse", "Billing Specialist",
                                  "HR Manager", "IT Contractor"],
        assignment_required=False,
        governing_principle=TransmissionPrinciple.INTERNAL_OPS,
        scenario_hint=hint,
    )

def _meeting_agenda(date, hint):
    return dict(
        document_type=DocumentType.MEETING_AGENDA,
        originating_context=OriginatingContext.INTERNAL,
        subject_type=SubjectType.ORGANIZATION,
        subject_name=None, date=date,
        sensitivity_tier=SensitivityTier.INTERNAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[], implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse", "Billing Specialist",
                                  "HR Manager", "IT Contractor"],
        assignment_required=False,
        governing_principle=TransmissionPrinciple.INTERNAL_OPS,
        scenario_hint=hint,
    )

def _policy_memo(date, hint):
    return dict(
        document_type=DocumentType.POLICY_MEMO,
        originating_context=OriginatingContext.INTERNAL,
        subject_type=SubjectType.ORGANIZATION,
        subject_name=None, date=date,
        sensitivity_tier=SensitivityTier.INTERNAL,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[], implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse", "Billing Specialist",
                                  "HR Manager", "IT Contractor"],
        assignment_required=False,
        governing_principle=TransmissionPrinciple.INTERNAL_OPS,
        scenario_hint=hint,
    )

def _public_pamphlet(date, hint):
    return dict(
        document_type=DocumentType.PUBLIC_PAMPHLET,
        originating_context=OriginatingContext.PUBLIC,
        subject_type=SubjectType.ORGANIZATION,
        subject_name=None, date=date,
        sensitivity_tier=SensitivityTier.PUBLIC,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[], implied_attributes=[],
        permitted_receiver_roles=["Doctor", "Nurse", "Billing Specialist",
                                  "HR Manager", "IT Contractor", "Patient"],
        assignment_required=False,
        governing_principle=TransmissionPrinciple.PUBLIC_DISCLOSURE,
        scenario_hint=hint,
    )


# ---------------------------------------------------------------------------
# Spec matrix (~95 documents)
# ---------------------------------------------------------------------------

ALL_SPECS: list[dict] = [

    # -----------------------------------------------------------------------
    # CLINICAL NOTES (10)
    # -----------------------------------------------------------------------
    _clinical_note("John Smith",     "2026-01-15",
        "Routine diabetes follow-up; HbA1c stable; continue Metformin."),
    _clinical_note("Emily Brown",    "2026-01-20",
        "28-week prenatal visit; blood pressure elevated; monitored and resolved."),
    _clinical_note("Robert Lee",     "2026-01-22",
        "AFib management; INR in therapeutic range; continue Warfarin."),
    _clinical_note("James Carter",   "2026-02-05",
        "CKD Stage 3 follow-up; eGFR stable; dietary compliance discussed."),
    _clinical_note("Michael Chen",   "2026-02-12",
        "Hypertension and diabetes dual management; BP improved on Lisinopril."),
    _clinical_note("Linda Torres",   "2026-02-18",
        "Post-chemotherapy follow-up; Cycle 4 complete; Tamoxifen initiated."),
    _clinical_note("Patricia Moore", "2026-02-20",
        "Alzheimer's early-stage monitoring; cognitive assessment performed; caregiver present."),
    _clinical_note("Maria Gonzalez", "2026-02-03",
        "Depression follow-up; mood improved on Sertraline; CBT referral in progress.",
        extra_sensitive=True, extra_sensitive_reason="mental_health"),
    _clinical_note("David Park",     "2026-03-01",
        "HIV Stage 1 routine visit; viral load undetectable; CD4 count stable.",
        extra_sensitive=True, extra_sensitive_reason="hiv_aids"),
    _clinical_note("Sarah Wilson",   "2026-03-05",
        "OUD follow-up; Buprenorphine maintenance; urine screen negative; compliance good.",
        extra_sensitive=True, extra_sensitive_reason="substance_abuse"),

    # -----------------------------------------------------------------------
    # PRESCRIPTIONS (8)
    # -----------------------------------------------------------------------
    _prescription("John Smith",     "2026-01-15", "Metformin 500mg for Type 2 Diabetes; 60 tablets; 5 refills."),
    _prescription("Emily Brown",    "2026-01-20", "Prenatal vitamins with iron; dosage and refill instructions."),
    _prescription("Robert Lee",     "2026-01-22", "Warfarin 5mg for AFib anticoagulation; monthly INR monitoring note."),
    _prescription("James Carter",   "2026-02-05", "Lisinopril 10mg for CKD-related hypertension; renal dosing noted."),
    _prescription("Michael Chen",   "2026-02-12", "Lisinopril 20mg and Metformin 1000mg dual prescription renewal."),
    _prescription("Linda Torres",   "2026-02-18", "Tamoxifen 20mg post-chemotherapy hormonal therapy; 90-day supply."),
    _prescription("Patricia Moore", "2026-02-20", "Donepezil 10mg for Alzheimer's; caregiver administration instructions."),
    _prescription("Maria Gonzalez", "2026-02-03", "Sertraline 100mg continuation; 30-day supply; refill instructions."),

    # -----------------------------------------------------------------------
    # LAB REPORTS (8)
    # -----------------------------------------------------------------------
    _lab_report("John Smith",     "2026-01-15", "HbA1c 7.1%; fasting glucose 118 mg/dL; diabetes well-controlled."),
    _lab_report("Robert Lee",     "2026-01-22", "INR 2.4; within therapeutic range for AFib anticoagulation."),
    _lab_report("Emily Brown",    "2026-01-20", "Complete blood count; hemoglobin 11.2; iron supplementation recommended."),
    _lab_report("James Carter",   "2026-02-05", "eGFR 42 mL/min; creatinine 1.8; potassium 4.9; CKD Stage 3 stable."),
    _lab_report("Michael Chen",   "2026-02-12", "HbA1c 7.8%; lipid panel; LDL elevated; statin consideration noted."),
    _lab_report("Linda Torres",   "2026-02-18", "CBC post-chemotherapy; neutrophil count recovering; platelets normal."),
    _lab_report("Patricia Moore", "2026-02-20", "Comprehensive metabolic panel; liver enzymes normal; renal function stable."),
    _lab_report("David Park",     "2026-03-01", "CD4 count 680 cells/uL; viral load <50 copies/mL; HIV well-controlled."),

    # -----------------------------------------------------------------------
    # RADIOLOGY REPORTS (5)
    # -----------------------------------------------------------------------
    _radiology("Emily Brown",    "2026-01-18", "Obstetric ultrasound; fetal growth appropriate for 28 weeks; no anomalies."),
    _radiology("Linda Torres",   "2026-01-10", "Right breast MRI post-lumpectomy; no residual mass; clear margins confirmed."),
    _radiology("Robert Lee",     "2026-01-05", "Chest X-ray; mild cardiomegaly consistent with known AFib; no effusion."),
    _radiology("James Carter",   "2026-01-28", "Renal ultrasound; bilateral kidney size reduced consistent with CKD Stage 3."),
    _radiology("Patricia Moore", "2026-02-15", "Brain MRI; cortical atrophy pattern consistent with early Alzheimer's disease."),

    # -----------------------------------------------------------------------
    # DISCHARGE SUMMARIES (5)
    # -----------------------------------------------------------------------
    _discharge("Emily Brown",    "2026-01-20", "Discharged after 4-hour BP monitoring; gestational hypertension resolved."),
    _discharge("John Smith",     "2026-01-16", "Same-day discharge after hypoglycemia episode; glucose stabilized; education provided."),
    _discharge("Linda Torres",   "2026-02-19", "Post-chemo cycle 4 discharge; antiemetic regimen adjusted; follow-up in 3 weeks."),
    _discharge("Robert Lee",     "2026-01-08", "Admitted for AFib with RVR; rate controlled with IV metoprolol; discharged stable."),
    _discharge("Sarah Wilson",   "2026-03-10", "Brief inpatient detox observation; Buprenorphine initiated; outpatient MAT referral."),

    # -----------------------------------------------------------------------
    # MENTAL HEALTH ASSESSMENTS (5)
    # -----------------------------------------------------------------------
    _mental_health("Maria Gonzalez", "2026-02-03",
        "Recurrent MDD follow-up; PHQ-9 score 14; Sertraline dose maintained; CBT referral made.",
        extra_sensitive_reason="mental_health"),
    _mental_health("Sarah Wilson",   "2026-03-05",
        "OUD psychiatric co-assessment; anxiety symptoms noted; Buprenorphine maintenance continued.",
        extra_sensitive_reason="substance_abuse"),
    _mental_health("David Park",     "2026-03-01",
        "HIV-related depression screening; PHQ-9 score 9 (mild); watchful waiting; follow-up in 4 weeks.",
        extra_sensitive_reason="mental_health"),
    _mental_health("Patricia Moore", "2026-02-20",
        "Behavioral assessment for Alzheimer's patient; agitation and sleep disruption noted; plan adjusted.",
        extra_sensitive_reason="mental_health"),
    _mental_health("James Carter",   "2026-02-05",
        "Depression screening for chronic illness patient; PHQ-9 score 7; lifestyle counseling initiated.",
        extra_sensitive_reason="mental_health"),

    # -----------------------------------------------------------------------
    # REFERRAL LETTERS (6)
    # -----------------------------------------------------------------------
    _referral("John Smith",   "2026-01-15", "Referral to nephrology for diabetic nephropathy workup; CKD risk elevated."),
    _referral("Robert Lee",   "2026-01-22", "Referral to electrophysiology for AFib ablation evaluation."),
    _referral("Emily Brown",  "2026-01-20", "Referral to maternal-fetal medicine for gestational hypertension monitoring."),
    _referral("Linda Torres", "2026-02-18", "Referral to radiation oncology for adjuvant radiation therapy post-lumpectomy."),
    _referral("James Carter", "2026-02-05", "Referral to nephrology for CKD Stage 3 co-management and dialysis planning."),
    _referral("Michael Chen", "2026-02-12", "Referral to cardiology for hypertension-related cardiac workup."),

    # -----------------------------------------------------------------------
    # INSURANCE CLAIMS (8)
    # -----------------------------------------------------------------------
    _insurance_claim("John Smith",     "2026-01-15", "Office visit claim for T2DM follow-up; CPT 99213; ICD E11.9."),
    _insurance_claim("Emily Brown",    "2026-01-20", "Prenatal visit claim; CPT 59400; ICD Z34.32."),
    _insurance_claim("Robert Lee",     "2026-01-22", "AFib management claim; CPT 99214; ICD I48.11."),
    _insurance_claim("James Carter",   "2026-02-05", "CKD follow-up claim; CPT 99214; ICD N18.3."),
    _insurance_claim("Michael Chen",   "2026-02-12", "Dual-diagnosis visit claim; CPT 99213; ICD I10 and E11.9."),
    _insurance_claim("Linda Torres",   "2026-02-18", "Oncology visit claim; CPT 99215; ICD C50.911."),
    _insurance_claim("Patricia Moore", "2026-02-20", "Neurology visit claim; CPT 99215; ICD G30.0."),
    _insurance_claim("Maria Gonzalez", "2026-02-03", "Psychiatric visit claim; CPT 90837; ICD F33.1."),

    # -----------------------------------------------------------------------
    # BILLING STATEMENTS (6)
    # -----------------------------------------------------------------------
    _billing_statement("John Smith",     "2026-02-01", "Patient balance after BlueCross PPO processed diabetes visit claim."),
    _billing_statement("Emily Brown",    "2026-02-01", "Patient balance after Aetna HMO processed prenatal care claim."),
    _billing_statement("Robert Lee",     "2026-02-05", "Medicare Part B processed AFib visit; patient balance statement."),
    _billing_statement("James Carter",   "2026-02-15", "Medicare Part B processed CKD visit; co-pay balance due."),
    _billing_statement("Linda Torres",   "2026-03-01", "Aetna PPO processed oncology visit; balance after EOB applied."),
    _billing_statement("Patricia Moore", "2026-03-01", "Medicare processed Alzheimer's visit; supplemental insurance applied."),

    # -----------------------------------------------------------------------
    # PRIOR AUTHORIZATIONS (5)
    # -----------------------------------------------------------------------
    _prior_auth("John Smith",   "2026-01-10", "Prior auth for Metformin extended-release; clinical justification for brand."),
    _prior_auth("Robert Lee",   "2026-01-15", "Prior auth for Warfarin; INR monitoring protocol attached."),
    _prior_auth("Maria Gonzalez", "2026-02-10",
        "Prior auth for Sertraline continuation; psychiatric justification required.",
        extra_sensitive=True, extra_sensitive_reason="mental_health"),
    _prior_auth("Sarah Wilson", "2026-03-01",
        "Prior auth for Buprenorphine/Naloxone; SAMHSA waiver documentation attached.",
        extra_sensitive=True, extra_sensitive_reason="substance_abuse"),
    _prior_auth("Linda Torres", "2026-02-01", "Prior auth for Tamoxifen; oncology treatment protocol attached."),

    # -----------------------------------------------------------------------
    # EXPLANATIONS OF BENEFITS (4)
    # -----------------------------------------------------------------------
    _eob("John Smith",   "2026-02-10", "BlueCross PPO EOB for January diabetes visit; allowed amount and co-pay breakdown."),
    _eob("Emily Brown",  "2026-02-10", "Aetna HMO EOB for prenatal visit; global OB fee applied."),
    _eob("Robert Lee",   "2026-02-10", "Medicare EOB for AFib visit; Part B deductible applied."),
    _eob("James Carter", "2026-02-20", "Medicare EOB for CKD visit; co-insurance and deductible breakdown."),

    # -----------------------------------------------------------------------
    # INSURANCE VERIFICATIONS (4)
    # -----------------------------------------------------------------------
    _insurance_verify("John Smith",     "2026-01-14", "Pre-visit insurance eligibility check; BlueCross PPO active; co-pay confirmed."),
    _insurance_verify("Emily Brown",    "2026-01-19", "Pre-visit insurance check; Aetna HMO prenatal coverage verified."),
    _insurance_verify("Patricia Moore", "2026-02-19", "Medicare eligibility verification; Part A and B active; supplemental confirmed."),
    _insurance_verify("Michael Chen",   "2026-02-11", "United Health PPO eligibility check; specialist referral authorization confirmed."),

    # -----------------------------------------------------------------------
    # SALARY LETTERS (6)
    # -----------------------------------------------------------------------
    _salary_letter("Dr. Sarah Chen",    "2026-01-01", "Annual compensation notification; $215,000 base salary effective 2026-01-01."),
    _salary_letter("Dr. Marcus Webb",   "2026-01-01", "Annual compensation notification; $240,000 base salary effective 2026-01-01."),
    _salary_letter("Dr. Aisha Patel",   "2026-01-01", "Annual compensation notification; $195,000 base salary effective 2026-01-01."),
    _salary_letter("Dr. Kevin O'Brien", "2026-01-01", "Annual compensation notification; $260,000 base salary effective 2026-01-01."),
    _salary_letter("Nurse Patricia Davis", "2026-01-01", "Annual compensation notification; $72,000 effective 2026-01-01."),
    _salary_letter("Alice Johnson",     "2026-01-01", "Annual compensation notification; $55,000 effective 2026-01-01."),

    # -----------------------------------------------------------------------
    # EMPLOYMENT CONTRACTS (5)
    # -----------------------------------------------------------------------
    _employment_contract("Dr. Marcus Webb",   "2021-09-01", "Staff Cardiologist contract; $240,000; non-compete and NDA clauses."),
    _employment_contract("Dr. Aisha Patel",   "2022-03-01", "Staff Psychiatrist contract; $195,000; 42 CFR Part 2 obligations noted."),
    _employment_contract("Dr. Kevin O'Brien", "2020-07-01", "Staff Oncologist contract; $260,000; research obligations and IP clause."),
    _employment_contract("Nurse Lisa Kim",    "2023-08-01", "Staff RN contract; $74,000; psychiatric unit assignment."),
    _employment_contract("Jennifer Walsh",    "2024-01-15", "Billing Specialist contract; $52,000; HIPAA training requirement noted."),

    # -----------------------------------------------------------------------
    # PERFORMANCE REVIEWS (4)
    # -----------------------------------------------------------------------
    _performance_review("Dr. Sarah Chen",      "2026-01-15", "Annual review; exceeds expectations; patient satisfaction scores high."),
    _performance_review("Nurse Patricia Davis","2026-01-15", "Annual review; meets expectations; commended for patient advocacy."),
    _performance_review("Alice Johnson",       "2026-01-15", "Annual review; billing accuracy 99.2%; exceeds targets."),
    _performance_review("Nurse Tom Reyes",     "2026-01-15", "Annual review; meets expectations; overtime compliance noted."),

    # -----------------------------------------------------------------------
    # CREDENTIALING FILES (3)
    # -----------------------------------------------------------------------
    _credentialing("Dr. Sarah Chen",    "2026-01-01", "IL medical license renewal; DEA registration; board certification Internal Medicine."),
    _credentialing("Dr. Aisha Patel",   "2026-01-01", "IL psychiatric license; DEA Schedule III waiver; board certification Psychiatry."),
    _credentialing("Dr. Kevin O'Brien", "2026-01-01", "IL license; oncology board certification; clinical trial principal investigator credentials."),

    # -----------------------------------------------------------------------
    # CONTRACTOR AGREEMENTS (3)
    # -----------------------------------------------------------------------
    _contractor_agreement("Carol White",  "2026-01-01", "IT support contract; $95/hr; PHI prohibition clause; 2026 term."),
    _contractor_agreement("Frank Turner", "2026-01-01", "IT infrastructure contract; $88/hr; network monitoring scope; PHI prohibition."),
    dict(
        document_type=DocumentType.CONTRACTOR_AGREEMENT,
        originating_context=OriginatingContext.HR,
        subject_type=SubjectType.CONTRACTOR,
        subject_name="Carol White", date="2025-01-01",
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        extra_sensitive=False, extra_sensitive_reason=None,
        pii_attributes=[AttributeType.CONTRACT_TERMS, AttributeType.DATE_OF_BIRTH,
                        AttributeType.HOME_ADDRESS],
        implied_attributes=[],
        permitted_receiver_roles=["HR Manager"], assignment_required=True,
        governing_principle=TransmissionPrinciple.HR_CONFIDENTIAL,
        scenario_hint="Prior year IT contract 2025; rate $90/hr; scope of work addendum included.",
    ),

    # -----------------------------------------------------------------------
    # STAFF SCHEDULES (3)
    # -----------------------------------------------------------------------
    _staff_schedule("2026-06-16", "Weekly schedule; Dr. Chen AM, Dr. Webb PM; Nurse Davis full day."),
    _staff_schedule("2026-06-23", "Holiday week schedule; reduced staffing; on-call assignments noted."),
    _staff_schedule("2026-07-07", "Summer rotation; Nurse Mendez covering; IT maintenance window Tuesday."),

    # -----------------------------------------------------------------------
    # MEETING AGENDAS (3)
    # -----------------------------------------------------------------------
    _meeting_agenda("2026-01-10", "Monthly clinical staff meeting; quality metrics, incident reports, scheduling updates."),
    _meeting_agenda("2026-02-10", "HR quarterly review; benefits enrollment, policy updates, headcount planning."),
    _meeting_agenda("2026-03-10", "IT infrastructure review; EHR upgrade timeline, security audit findings."),

    # -----------------------------------------------------------------------
    # POLICY MEMOS (3)
    # -----------------------------------------------------------------------
    _policy_memo("2026-01-05", "Updated HIPAA minimum necessary policy; staff acknowledgment required by 2026-01-31."),
    _policy_memo("2026-02-01", "Remote access policy update; VPN required for all EHR access off-site."),
    _policy_memo("2026-03-01", "PHI breach response procedure update; 60-day notification window clarified."),

    # -----------------------------------------------------------------------
    # PUBLIC PAMPHLETS (3)
    # -----------------------------------------------------------------------
    _public_pamphlet("2026-01-01", "Patient rights and privacy notice; HIPAA Notice of Privacy Practices."),
    _public_pamphlet("2026-01-01", "New patient welcome guide; clinic services, hours, contact information."),
    _public_pamphlet("2026-01-01", "Billing and insurance FAQ; co-pay policy, accepted insurers, financial assistance."),
]


if __name__ == "__main__":
    from collections import Counter
    tiers  = Counter(s["sensitivity_tier"]  for s in ALL_SPECS)
    dtypes = Counter(s["document_type"]     for s in ALL_SPECS)
    print(f"Total specs: {len(ALL_SPECS)}\n")
    print("By sensitivity tier:")
    for k, v in sorted(tiers.items()):
        print(f"  {k:<25} {v}")
    print("\nBy document type:")
    for k, v in sorted(dtypes.items()):
        print(f"  {k:<30} {v}")
