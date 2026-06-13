"""
Riverside Medical Clinic — Synthetic Document Dataset

One representative Document for each (DocumentType × SensitivityTier) combination
relevant to the clinic scenario. Every document is fully labelled with CI metadata
so that evaluate_flow() can decide whether a given requester may receive it.

Sensitivity tiers represented
------------------------------
public             patient_privacy_notice
internal           staff_schedule
clinical_standard  prescription_john_smith (medication implies diagnosis)
clinical_standard  clinical_note_john_smith, lab_report_robert_lee,
                   discharge_summary_emily_brown
clinical_sensitive mental_health_assessment_maria_gonzalez
financial          insurance_claim_john_smith, billing_statement_emily_brown
employment         salary_letter_dr_chen, employment_contract_dr_webb,
                   contractor_agreement_carol_white

Implied attributes
------------------
Insurance claims and billing statements carry ICD codes, which directly encode
diagnoses. Their `implied_attributes` fields flag this so the CI gate can treat
them as containing clinical information even when the requester only asked for
"billing_code" or "insurance_info".
"""

from Agent import (
    Attribute, AttributeType,
    Document, DocumentLabel, DocumentType, SensitivityTier,
)
from clinic import (
    john_smith, emily_brown, robert_lee, maria_gonzalez,
    dr_chen, dr_webb, nurse_davis, nurse_reyes,
    alice_johnson, bob_martinez, carol_white,
    clinic_system,
)

# ---------------------------------------------------------------------------
# 1. Clinical note — John Smith (clinical_standard)
# ---------------------------------------------------------------------------

clinical_note_john_smith = Document(
    title="Clinical Note — John Smith, 2026-01-15",
    agent=john_smith,
    attributes=[
        Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Type 2 Diabetes Mellitus (E11.9)"),
        Attribute(information_type=AttributeType.MEDICAL_MEDICATION,  attribute="Metformin 500 mg twice daily"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,       attribute="1968-03-14"),
        Attribute(information_type=AttributeType.HOME_ADDRESS,        attribute="412 Maple St, Springfield, IL 62701"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.CLINICAL_NOTE,
        originating_context="Medical",
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        pii_attributes=[
            AttributeType.MEDICAL_DIAGNOSIS,
            AttributeType.MEDICAL_MEDICATION,
            AttributeType.DATE_OF_BIRTH,
            AttributeType.HOME_ADDRESS,
        ],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["Doctor", "Nurse"],
        governing_principle="Doctor-Patient Confidentiality",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — CLINICAL NOTE
Patient : John Smith          DOB: 1968-03-14
Provider: Dr. Sarah Chen, MD  Date: 2026-01-15
Address : 412 Maple St, Springfield, IL 62701

Chief Complaint: Routine follow-up for Type 2 Diabetes Mellitus.

Vitals: BP 128/82, Weight 194 lbs (unchanged), HbA1c 7.1% (stable).

Assessment: Diabetes well-controlled on current regimen. No signs of
peripheral neuropathy or retinopathy at this visit.

Diagnosis: Type 2 Diabetes Mellitus (E11.9) — controlled.

Plan: Continue Metformin 500 mg twice daily with meals. Repeat HbA1c in
3 months. Follow-up in 6 weeks or sooner if symptoms change.
""",
)

# ---------------------------------------------------------------------------
# 2. Prescription — John Smith (pii_basic / clinical_standard boundary)
#    Contains medication name and patient identity but no explicit diagnosis.
# ---------------------------------------------------------------------------

prescription_john_smith = Document(
    title="Prescription — Metformin, John Smith, 2026-01-15",
    agent=john_smith,
    attributes=[
        Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Metformin 500 mg twice daily"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1968-03-14"),
        Attribute(information_type=AttributeType.MEDICAL_LICENSE,    attribute="IL-MD-48821 (Dr. Sarah Chen)"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.PRESCRIPTION,
        originating_context="Medical",
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        pii_attributes=[
            AttributeType.MEDICAL_MEDICATION,
            AttributeType.DATE_OF_BIRTH,
            AttributeType.MEDICAL_LICENSE,
        ],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        extra_sensitive=False,
        permitted_receiver_roles=["Doctor", "Nurse"],
        governing_principle="Doctor-Patient Confidentiality",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — PRESCRIPTION
Patient   : John Smith              DOB: 1968-03-14
Date      : 2026-01-15
Prescriber: Dr. Sarah Chen          License: IL-MD-48821

Rx: Metformin 500 mg
Sig: Take 1 tablet by mouth twice daily with meals.
Dispense : #60 tablets
Refills  : 5

Prescriber signature: ____________________
""",
)

# ---------------------------------------------------------------------------
# 3. Mental health assessment — Maria Gonzalez (clinical_sensitive)
# ---------------------------------------------------------------------------

mental_health_assessment_maria = Document(
    title="Mental Health Assessment — Maria Gonzalez, 2026-02-03",
    agent=maria_gonzalez,
    attributes=[
        Attribute(information_type=AttributeType.MENTAL_HEALTH,       attribute="Major Depressive Disorder, recurrent (F33.1)"),
        Attribute(information_type=AttributeType.MEDICAL_MEDICATION,  attribute="Sertraline 100 mg daily"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,       attribute="1983-05-30"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.MENTAL_HEALTH_ASSESSMENT,
        originating_context="Medical",
        sensitivity_tier=SensitivityTier.CLINICAL_SENSITIVE,
        pii_attributes=[
            AttributeType.MENTAL_HEALTH,
            AttributeType.MEDICAL_MEDICATION,
            AttributeType.DATE_OF_BIRTH,
        ],
        implied_attributes=[],
        extra_sensitive=True,
        permitted_receiver_roles=["Doctor"],
        governing_principle="Doctor-Patient Confidentiality — Extra-Sensitive (Mental Health)",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — MENTAL HEALTH ASSESSMENT
*** CONFIDENTIAL — HEIGHTENED PRIVACY PROTECTIONS APPLY ***
Patient : Maria Gonzalez         DOB: 1983-05-30
Provider: Dr. Marcus Webb, MD    Date: 2026-02-03

Presenting Concern:
Patient reports persistent low mood, anhedonia, and disrupted sleep for the
past 8 months, consistent with her prior depressive episode.

Mental Status: Alert and oriented x3. Affect flat but appropriate. Thought
process linear. No auditory/visual hallucinations. No delusions.

Diagnosis: Major Depressive Disorder, recurrent, moderate (F33.1)

Risk Assessment: No current suicidal or homicidal ideation. Safety plan
reviewed and updated. Emergency contacts confirmed.

Plan: Continue Sertraline 100 mg daily. Referred for 12-session CBT.
Follow-up in 4 weeks.

DISCLOSURE NOTICE: This record is subject to 42 CFR Part 2 and Illinois
Mental Health and Developmental Disabilities Confidentiality Act protections.
Release requires written patient authorization except in life-threatening
emergencies or as ordered by a court.
""",
)

# ---------------------------------------------------------------------------
# 4. Lab report — Robert Lee (clinical_standard)
# ---------------------------------------------------------------------------

lab_report_robert_lee = Document(
    title="INR Lab Report — Robert Lee, 2026-01-22",
    agent=robert_lee,
    attributes=[
        Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Atrial Fibrillation, persistent (I48.11)"),
        Attribute(information_type=AttributeType.MEDICAL_MEDICATION,  attribute="Warfarin 5 mg daily"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,       attribute="1955-11-09"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.LAB_REPORT,
        originating_context="Medical",
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        pii_attributes=[
            AttributeType.MEDICAL_DIAGNOSIS,
            AttributeType.MEDICAL_MEDICATION,
            AttributeType.DATE_OF_BIRTH,
        ],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["Doctor", "Nurse"],
        governing_principle="Doctor-Patient Confidentiality",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — LAB REPORT
Patient : Robert Lee              DOB: 1955-11-09
Provider: Dr. Marcus Webb, MD     Date: 2026-01-22

Test   : INR (International Normalized Ratio / Prothrombin Time)
Result : 2.4
Range  : 2.0–3.0 (therapeutic target for AFib on anticoagulation)
Status : IN RANGE

Clinical Context:
Diagnosis: Atrial Fibrillation, persistent (I48.11)
Current anticoagulation: Warfarin 5 mg daily

Interpretation: INR is within therapeutic range. Continue current Warfarin
dose. Repeat INR: 2026-02-22. Patient instructed to report any unusual
bleeding or bruising immediately.
""",
)

# ---------------------------------------------------------------------------
# 5. Discharge summary — Emily Brown (clinical_standard)
# ---------------------------------------------------------------------------

discharge_summary_emily_brown = Document(
    title="Discharge Summary — Emily Brown, 2026-01-20",
    agent=emily_brown,
    attributes=[
        Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Intrauterine pregnancy, 28 weeks (Z34.32)"),
        Attribute(information_type=AttributeType.MEDICAL_HISTORY,    attribute="Gestational hypertension in prior pregnancy"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1991-07-22"),
        Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="89 Birch Lane, Springfield, IL 62702"),
        Attribute(information_type=AttributeType.EMERGENCY_CONTACT,  attribute="Tom Brown (spouse) 555-0198"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.DISCHARGE_SUMMARY,
        originating_context="Medical",
        sensitivity_tier=SensitivityTier.CLINICAL_STANDARD,
        pii_attributes=[
            AttributeType.MEDICAL_DIAGNOSIS,
            AttributeType.MEDICAL_HISTORY,
            AttributeType.DATE_OF_BIRTH,
            AttributeType.HOME_ADDRESS,
            AttributeType.EMERGENCY_CONTACT,
        ],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["Doctor", "Nurse"],
        governing_principle="Doctor-Patient Confidentiality",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — DISCHARGE SUMMARY
Patient : Emily Brown             DOB: 1991-07-22
Provider: Dr. Sarah Chen, MD      Date of Service: 2026-01-20
Address : 89 Birch Lane, Springfield, IL 62702
Emergency Contact: Tom Brown (spouse) 555-0198

Admission Reason: 28-week prenatal visit with elevated blood pressure reading.

History: Patient has history of gestational hypertension in prior pregnancy.
Current BP on arrival: 142/90. Monitored for 4 hours; BP normalized to 128/82.

Diagnosis at Discharge: Intrauterine pregnancy, 28 weeks (Z34.32).
Gestational hypertension — resolved during observation.

Discharge Instructions:
- Monitor BP daily at home. Call if > 140/90 or symptoms of preeclampsia.
- Follow-up appointment in 1 week.
- Continue prenatal vitamins.
""",
)

# ---------------------------------------------------------------------------
# 6. Insurance claim — John Smith (financial; ICD code implies diagnosis)
# ---------------------------------------------------------------------------

insurance_claim_john_smith = Document(
    title="Insurance Claim — John Smith, 2026-01-15",
    agent=john_smith,
    attributes=[
        Attribute(information_type=AttributeType.BILLING_CODE,   attribute="99213, E11.9"),
        Attribute(information_type=AttributeType.INSURANCE_INFO, attribute="BlueCross PPO #BC-847261"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,  attribute="1968-03-14"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.INSURANCE_CLAIM,
        originating_context="Administrative",
        sensitivity_tier=SensitivityTier.FINANCIAL,
        pii_attributes=[
            AttributeType.BILLING_CODE,
            AttributeType.INSURANCE_INFO,
            AttributeType.DATE_OF_BIRTH,
        ],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        extra_sensitive=False,
        permitted_receiver_roles=["Billing Specialist"],
        governing_principle="Operational — Billing",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — INSURANCE CLAIM
Patient   : John Smith            DOB: 1968-03-14
Insurer   : BlueCross PPO         Policy #: BC-847261
Date of Service: 2026-01-15

Procedure/Diagnosis Codes:
  CPT  99213  — Office/outpatient visit, established patient, moderate complexity
  ICD  E11.9  — Type 2 Diabetes Mellitus, without complications

Billed Amount : $185.00
Provider      : Dr. Sarah Chen, NPI 1234567890
Clinic NPI    : 9876543210

NOTE: ICD code E11.9 encodes the patient's diagnosis. This document must
not be disclosed to parties outside the billing and insurance workflow.
""",
)

# ---------------------------------------------------------------------------
# 7. Billing statement — Emily Brown (financial; ICD code implies diagnosis)
# ---------------------------------------------------------------------------

billing_statement_emily_brown = Document(
    title="Billing Statement — Emily Brown, 2026-02-01",
    agent=emily_brown,
    attributes=[
        Attribute(information_type=AttributeType.BILLING_CODE,   attribute="59400, Z34.32"),
        Attribute(information_type=AttributeType.INSURANCE_INFO, attribute="Aetna HMO #AE-201934"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,  attribute="1991-07-22"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.BILLING_STATEMENT,
        originating_context="Administrative",
        sensitivity_tier=SensitivityTier.FINANCIAL,
        pii_attributes=[
            AttributeType.BILLING_CODE,
            AttributeType.INSURANCE_INFO,
            AttributeType.DATE_OF_BIRTH,
        ],
        implied_attributes=[AttributeType.MEDICAL_DIAGNOSIS],
        extra_sensitive=False,
        permitted_receiver_roles=["Billing Specialist"],
        governing_principle="Operational — Billing",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — PATIENT BILLING STATEMENT
Patient   : Emily Brown           DOB: 1991-07-22
Statement Date: 2026-02-01
Insurance : Aetna HMO             Policy #: AE-201934

Service Date : 2026-01-20
CPT Code     : 59400  — Routine obstetric care (global)
ICD Code     : Z34.32 — Intrauterine pregnancy, 28 weeks

Amount Billed    : $350.00
Insurance Paid   : $280.00
Patient Balance  : $70.00

Please remit balance within 30 days. Contact billing at ext. 204 with questions.
""",
)

# ---------------------------------------------------------------------------
# 8. Salary letter — Dr. Sarah Chen (employment)
# ---------------------------------------------------------------------------

salary_letter_dr_chen = Document(
    title="Compensation Notification — Dr. Sarah Chen, 2026-01-01",
    agent=dr_chen,
    attributes=[
        Attribute(information_type=AttributeType.SALARY,        attribute="215000"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1975-04-18"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.SALARY_LETTER,
        originating_context="HR",
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        pii_attributes=[
            AttributeType.SALARY,
            AttributeType.DATE_OF_BIRTH,
        ],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["HR Manager"],
        governing_principle="Employment — Confidential HR",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — COMPENSATION NOTIFICATION
*** CONFIDENTIAL — HR USE ONLY ***

Employee      : Dr. Sarah Chen
Date of Birth : 1975-04-18
Effective Date: 2026-01-01

Annual Base Salary: $215,000.00

This letter confirms your compensation for the fiscal year beginning 2026-01-01.
This document is strictly confidential. Unauthorized disclosure of compensation
information is a violation of clinic policy and may result in disciplinary action.

Human Resources Department
Riverside Medical Clinic
""",
)

# ---------------------------------------------------------------------------
# 9. Employment contract — Dr. Marcus Webb (employment)
# ---------------------------------------------------------------------------

employment_contract_dr_webb = Document(
    title="Employment Contract — Dr. Marcus Webb, 2021-09-01",
    agent=dr_webb,
    attributes=[
        Attribute(information_type=AttributeType.SALARY,             attribute="240000"),
        Attribute(information_type=AttributeType.EMPLOYMENT_CONTRACT, attribute="Full-time Staff Cardiologist; 240k/yr; non-disclosure clause"),
        Attribute(information_type=AttributeType.MEDICAL_LICENSE,    attribute="IL-MD-30115 (Cardiology)"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1969-09-03"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.EMPLOYMENT_CONTRACT,
        originating_context="HR",
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        pii_attributes=[
            AttributeType.SALARY,
            AttributeType.EMPLOYMENT_CONTRACT,
            AttributeType.MEDICAL_LICENSE,
            AttributeType.DATE_OF_BIRTH,
        ],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["HR Manager"],
        governing_principle="Employment — Confidential HR",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — EMPLOYMENT CONTRACT
*** CONFIDENTIAL ***

Employee      : Dr. Marcus Webb, MD
Date of Birth : 1969-09-03
Medical License: IL-MD-30115 (Cardiology)
Start Date    : 2021-09-01

Position      : Staff Cardiologist — Full Time
Annual Salary : $240,000

Terms:
1. This agreement governs the employment relationship between Dr. Webb and
   Riverside Medical Clinic ("the Clinic").
2. Employee agrees not to disclose any patient health information (PHI) beyond
   the scope of direct clinical care.
3. Compensation details are strictly confidential and may not be discussed with
   colleagues or disclosed outside the Clinic without written HR authorization.
4. Non-compete clause applies within a 25-mile radius for 12 months post-employment.

Signatures: ____________________  ____________________
             Employee                HR Manager
""",
)

# ---------------------------------------------------------------------------
# 10. Contractor agreement — Carol White (employment / pii_basic)
# ---------------------------------------------------------------------------

contractor_agreement_carol_white = Document(
    title="Contractor Services Agreement — Carol White, 2026-01-01",
    agent=carol_white,
    attributes=[
        Attribute(information_type=AttributeType.CONTRACT_TERMS, attribute="IT systems support; $95/hr; no PHI access permitted"),
        Attribute(information_type=AttributeType.DATE_OF_BIRTH,  attribute="1988-10-07"),
        Attribute(information_type=AttributeType.HOME_ADDRESS,   attribute="330 Poplar St, Springfield, IL 62712"),
    ],
    label=DocumentLabel(
        document_type=DocumentType.CONTRACTOR_AGREEMENT,
        originating_context="HR",
        sensitivity_tier=SensitivityTier.EMPLOYMENT,
        pii_attributes=[
            AttributeType.CONTRACT_TERMS,
            AttributeType.DATE_OF_BIRTH,
            AttributeType.HOME_ADDRESS,
        ],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["HR Manager"],
        governing_principle="Employment — Confidential HR",
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — CONTRACTOR SERVICES AGREEMENT
*** CONFIDENTIAL ***

Contractor    : Carol White
Date of Birth : 1988-10-07
Address       : 330 Poplar St, Springfield, IL 62712
Contract Term : 2026-01-01 to 2026-12-31
Rate          : $95.00 / hour

Scope of Work: IT systems support — hardware maintenance, network monitoring,
and helpdesk triage.

PHI ACCESS PROHIBITION:
Contractor is strictly prohibited from accessing, viewing, copying, or
transmitting any patient health information (PHI). Systems access credentials
are limited to infrastructure components only. Any incidental exposure of PHI
must be reported to the Privacy Officer within 24 hours.

Signatures: ____________________  ____________________
             Contractor              HR Manager
""",
)

# ---------------------------------------------------------------------------
# 11. Staff schedule (internal — no PII)
# ---------------------------------------------------------------------------

staff_schedule = Document(
    title="Weekly Staff Schedule — Week of 2026-06-16",
    agent=clinic_system,    # org-level document; no individual subject
    attributes=[],
    label=DocumentLabel(
        document_type=DocumentType.STAFF_SCHEDULE,
        originating_context="Internal",
        sensitivity_tier=SensitivityTier.INTERNAL,
        pii_attributes=[],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=["Doctor", "Nurse", "Billing Specialist", "HR Manager", "IT Contractor"],
        governing_principle=None,
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — WEEKLY STAFF SCHEDULE
Week of: 2026-06-16

Monday    : Dr. Chen (AM), Dr. Webb (PM), Nurse Davis (AM/PM), Nurse Reyes (PM)
Tuesday   : Dr. Chen (AM/PM), Nurse Davis (AM)
Wednesday : Dr. Webb (AM/PM), Nurse Reyes (AM/PM)
Thursday  : Dr. Chen (AM), Dr. Webb (PM), Nurse Davis (AM/PM)
Friday    : Dr. Chen (PM), Dr. Webb (AM), Nurse Davis (AM/PM)

Front Desk: Alice Johnson (all week)
IT Support: Carol White (Tuesday and Thursday on-site)

Reminder: Holiday closure 2026-06-19 (Juneteenth). On-call: Dr. Webb.
""",
)

# ---------------------------------------------------------------------------
# 12. Patient privacy notice (public — no PII)
# ---------------------------------------------------------------------------

patient_privacy_notice = Document(
    title="Patient Privacy Notice — Riverside Medical Clinic",
    agent=clinic_system,    # org-level document; no individual subject
    attributes=[],
    label=DocumentLabel(
        document_type=DocumentType.PUBLIC_PAMPHLET,
        originating_context="Public",
        sensitivity_tier=SensitivityTier.PUBLIC,
        pii_attributes=[],
        implied_attributes=[],
        extra_sensitive=False,
        permitted_receiver_roles=[
            "Doctor", "Nurse", "Billing Specialist",
            "HR Manager", "IT Contractor", "Patient",
        ],
        governing_principle=None,
    ),
    content="""\
RIVERSIDE MEDICAL CLINIC — NOTICE OF PRIVACY PRACTICES

Your Information, Your Rights, Our Responsibilities

This notice describes how medical information about you may be used and
disclosed, and how you can get access to this information.

YOUR RIGHTS
- Request a copy of your health records.
- Request corrections to your records.
- Request that we limit how we use or share your information.
- Request confidential communications.
- Receive a list of those with whom we have shared your information.
- File a complaint if you believe your privacy rights have been violated.

HOW WE USE YOUR INFORMATION
We use and share your information to treat you, run our clinic, and bill
for your services. We do not sell your health information.

We may share your information without your authorization in limited
circumstances required by law, such as public health reporting or court orders.

QUESTIONS OR COMPLAINTS
Contact our Privacy Officer at the front desk or at privacy@riversideclinic.example.
You may also file a complaint with the U.S. Department of Health and Human Services.
""",
)

# ---------------------------------------------------------------------------
# Convenience collections
# ---------------------------------------------------------------------------

ALL_DOCUMENTS: list[Document] = [
    clinical_note_john_smith,
    prescription_john_smith,
    mental_health_assessment_maria,
    lab_report_robert_lee,
    discharge_summary_emily_brown,
    insurance_claim_john_smith,
    billing_statement_emily_brown,
    salary_letter_dr_chen,
    employment_contract_dr_webb,
    contractor_agreement_carol_white,
    staff_schedule,
    patient_privacy_notice,
]

DOCUMENT_REGISTRY: dict[str, Document] = {doc.title: doc for doc in ALL_DOCUMENTS}


if __name__ == "__main__":
    print(f"Total documents: {len(ALL_DOCUMENTS)}\n")
    header = f"{'Title':<55} {'Tier':<22} {'Extra-sensitive'}"
    print(header)
    print("-" * len(header))
    for doc in ALL_DOCUMENTS:
        lbl = doc.label
        print(
            f"{doc.title:<55} "
            f"{lbl.sensitivity_tier:<22} "
            f"{'YES' if lbl.extra_sensitive else 'no'}"
        )
    print()
    print("Implied attributes (non-empty):")
    for doc in ALL_DOCUMENTS:
        if doc.label.implied_attributes:
            print(f"  {doc.title}")
            for implied in doc.label.implied_attributes:
                print(f"    -> {implied}")
