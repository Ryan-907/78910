"""
Riverside Medical Clinic — Extended Agent Pool

Extends the original 11 agents from clinic.py with 13 additional agents
covering a broader range of conditions, roles, and edge cases needed for
large-scale dataset generation.

Exports
-------
EXTENDED_NAME_REGISTRY  : dict[str, Agent]   — all 24 agents by name
EXTENDED_ALL_AGENTS     : list[Agent]
EXTENDED_ALL_PATIENTS   : list[Patient]
EXTENDED_ALL_EMPLOYEES  : list[Employee]
EXTENDED_ALL_CONTRACTORS: list[Contractor]
clinic_system           : Agent sentinel
"""

from core.Agent import (
    Agent, Attribute, AttributeType, KnowledgeState, Role,
    Employee, Patient, Contractor,
)
from world.clinic import (
    # Original agents
    john_smith, emily_brown, robert_lee, maria_gonzalez,
    dr_chen, dr_webb, nurse_davis, nurse_reyes,
    alice_johnson, bob_martinez, carol_white,
    clinic_system,
    # Original roles
    DOCTOR_ROLE, NURSE_ROLE, BILLING_ROLE, HR_ROLE,
    IT_CONTRACTOR_ROLE, PATIENT_ROLE,
    # Maria Gonzalez's attributes (needed for dr_patel knowledge base)
    _mg_diagnosis,
    # Original registries (extended below)
    ALL_PATIENTS, ALL_EMPLOYEES, ALL_CONTRACTORS,
)

# ---------------------------------------------------------------------------
# Additional roles
# ---------------------------------------------------------------------------

FACILITIES_CONTRACTOR_ROLE = Role(role="Facilities Contractor", context="Administrative")

# ---------------------------------------------------------------------------
# New patients
# ---------------------------------------------------------------------------

# -- David Park (HIV, Stage 1 — extra-sensitive: hiv_aids) ------------------
david_park = Patient(name="David Park", active=True, role=PATIENT_ROLE)

_dp_dob        = Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1975-08-22")
_dp_ssn        = Attribute(information_type=AttributeType.SSN,                attribute="XXX-XX-7743")
_dp_address    = Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="601 Magnolia Dr, Springfield, IL 62714")
_dp_diagnosis  = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="HIV, Stage 1 (B20)")
_dp_medication = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Biktarvy 50mg/200mg/25mg once daily")
_dp_insurance  = Attribute(information_type=AttributeType.INSURANCE_INFO,     attribute="Medicaid #IL-2847601")
_dp_billing    = Attribute(information_type=AttributeType.BILLING_CODE,       attribute="99213, B20")

david_park.attributes.extend([
    _dp_dob, _dp_ssn, _dp_address, _dp_diagnosis,
    _dp_medication, _dp_insurance, _dp_billing,
])

# -- Sarah Wilson (Opioid Use Disorder — extra-sensitive: substance_abuse) --
sarah_wilson = Patient(name="Sarah Wilson", active=True, role=PATIENT_ROLE)

_sw_dob        = Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1989-03-15")
_sw_ssn        = Attribute(information_type=AttributeType.SSN,                attribute="XXX-XX-5518")
_sw_address    = Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="47 Chestnut Ave, Springfield, IL 62715")
_sw_diagnosis  = Attribute(information_type=AttributeType.MENTAL_HEALTH,      attribute="Opioid Use Disorder, moderate (F11.20)")
_sw_medication = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Buprenorphine/Naloxone 8mg/2mg sublingual twice daily")
_sw_insurance  = Attribute(information_type=AttributeType.INSURANCE_INFO,     attribute="BlueCross PPO #BC-921047")
_sw_billing    = Attribute(information_type=AttributeType.BILLING_CODE,       attribute="99214, F11.20")

sarah_wilson.attributes.extend([
    _sw_dob, _sw_ssn, _sw_address, _sw_diagnosis,
    _sw_medication, _sw_insurance, _sw_billing,
])

# -- James Carter (Chronic Kidney Disease Stage 3) --------------------------
james_carter = Patient(name="James Carter", active=True, role=PATIENT_ROLE)

_jc_dob        = Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1960-12-04")
_jc_ssn        = Attribute(information_type=AttributeType.SSN,                attribute="XXX-XX-3391")
_jc_address    = Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="88 Birchwood Ct, Springfield, IL 62716")
_jc_diagnosis  = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Chronic Kidney Disease, Stage 3 (N18.3)")
_jc_medication = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Lisinopril 10mg daily; dietary sodium restriction")
_jc_insurance  = Attribute(information_type=AttributeType.INSURANCE_INFO,     attribute="Medicare Part B #2FG8-KL4-NP91")
_jc_billing    = Attribute(information_type=AttributeType.BILLING_CODE,       attribute="99214, N18.3")
_jc_history    = Attribute(information_type=AttributeType.MEDICAL_HISTORY,    attribute="Type 2 Diabetes diagnosed 2012; hypertension since 2005")

james_carter.attributes.extend([
    _jc_dob, _jc_ssn, _jc_address, _jc_diagnosis,
    _jc_medication, _jc_insurance, _jc_billing, _jc_history,
])

# -- Linda Torres (Breast Cancer) -------------------------------------------
linda_torres = Patient(name="Linda Torres", active=True, role=PATIENT_ROLE)

_lt_dob        = Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1963-06-18")
_lt_ssn        = Attribute(information_type=AttributeType.SSN,                attribute="XXX-XX-8824")
_lt_address    = Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="220 Sycamore Blvd, Springfield, IL 62717")
_lt_diagnosis  = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Invasive ductal carcinoma, right breast (C50.911)")
_lt_medication = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Tamoxifen 20mg daily; Cycle 4 chemotherapy complete")
_lt_insurance  = Attribute(information_type=AttributeType.INSURANCE_INFO,     attribute="Aetna PPO #AE-837524")
_lt_billing    = Attribute(information_type=AttributeType.BILLING_CODE,       attribute="99215, C50.911")
_lt_history    = Attribute(information_type=AttributeType.MEDICAL_HISTORY,    attribute="BRCA1 positive; lumpectomy 2025-11-10; 4 cycles chemotherapy completed")
_lt_emergency  = Attribute(information_type=AttributeType.EMERGENCY_CONTACT,  attribute="Marco Torres (spouse) 555-0341")

linda_torres.attributes.extend([
    _lt_dob, _lt_ssn, _lt_address, _lt_diagnosis,
    _lt_medication, _lt_insurance, _lt_billing, _lt_history, _lt_emergency,
])

# -- Michael Chen (Hypertension + Type 2 Diabetes) -------------------------
michael_chen = Patient(name="Michael Chen", active=True, role=PATIENT_ROLE)

_mc_dob        = Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1958-09-27")
_mc_ssn        = Attribute(information_type=AttributeType.SSN,                attribute="XXX-XX-2267")
_mc_address    = Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="115 Walnut St, Springfield, IL 62718")
_mc_diagnosis  = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Essential hypertension (I10); Type 2 Diabetes Mellitus (E11.9)")
_mc_medication = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Lisinopril 20mg daily; Metformin 1000mg twice daily")
_mc_insurance  = Attribute(information_type=AttributeType.INSURANCE_INFO,     attribute="United Health PPO #UH-441230")
_mc_billing    = Attribute(information_type=AttributeType.BILLING_CODE,       attribute="99213, I10, E11.9")

michael_chen.attributes.extend([
    _mc_dob, _mc_ssn, _mc_address, _mc_diagnosis,
    _mc_medication, _mc_insurance, _mc_billing,
])

# -- Patricia Moore (Alzheimer's Disease) -----------------------------------
patricia_moore = Patient(name="Patricia Moore", active=True, role=PATIENT_ROLE)

_pm_dob        = Attribute(information_type=AttributeType.DATE_OF_BIRTH,      attribute="1942-01-30")
_pm_ssn        = Attribute(information_type=AttributeType.SSN,                attribute="XXX-XX-1183")
_pm_address    = Attribute(information_type=AttributeType.HOME_ADDRESS,       attribute="9 Linden Lane, Springfield, IL 62719")
_pm_diagnosis  = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS,  attribute="Alzheimer's disease, early onset (G30.0)")
_pm_medication = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Donepezil 10mg daily at bedtime")
_pm_insurance  = Attribute(information_type=AttributeType.INSURANCE_INFO,     attribute="Medicare Part A+B #3HJ2-MP6-QR44")
_pm_billing    = Attribute(information_type=AttributeType.BILLING_CODE,       attribute="99215, G30.0")
_pm_emergency  = Attribute(information_type=AttributeType.EMERGENCY_CONTACT,  attribute="Thomas Moore (son, legal guardian) 555-0267")

patricia_moore.attributes.extend([
    _pm_dob, _pm_ssn, _pm_address, _pm_diagnosis,
    _pm_medication, _pm_insurance, _pm_billing, _pm_emergency,
])

# ---------------------------------------------------------------------------
# New employees — Doctors
# ---------------------------------------------------------------------------

# -- Dr. Aisha Patel (Psychiatry; cares for David Park, Sarah Wilson, Maria Gonzalez)
dr_patel = Employee(name="Dr. Aisha Patel", salary=195_000.0, role=DOCTOR_ROLE)

_ap_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1978-11-14")
_ap_salary  = Attribute(information_type=AttributeType.SALARY,          attribute="195000")
_ap_license = Attribute(information_type=AttributeType.MEDICAL_LICENSE, attribute="IL-MD-55432 (Psychiatry)")
_ap_address = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="83 Hawthorn Rd, Springfield, IL 62720")

dr_patel.attributes.extend([_ap_dob, _ap_salary, _ap_license, _ap_address])

dr_patel.knowledge_base.extend([
    KnowledgeState(agent_id=david_park.uid,    known_attribute=_dp_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality — Extra-Sensitive"),
    KnowledgeState(agent_id=david_park.uid,    known_attribute=_dp_medication,
                   transmission_principle="Doctor-Patient Confidentiality — Extra-Sensitive"),
    KnowledgeState(agent_id=sarah_wilson.uid,  known_attribute=_sw_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality — Extra-Sensitive"),
    KnowledgeState(agent_id=sarah_wilson.uid,  known_attribute=_sw_medication,
                   transmission_principle="Doctor-Patient Confidentiality — Extra-Sensitive"),
    KnowledgeState(agent_id=maria_gonzalez.uid, known_attribute=_mg_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality — Extra-Sensitive"),
])

# -- Dr. Kevin O'Brien (Oncology; cares for Linda Torres) ------------------
dr_obrien = Employee(name="Dr. Kevin O'Brien", salary=260_000.0, role=DOCTOR_ROLE)

_ko_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1965-04-22")
_ko_salary  = Attribute(information_type=AttributeType.SALARY,          attribute="260000")
_ko_license = Attribute(information_type=AttributeType.MEDICAL_LICENSE, attribute="IL-MD-61209 (Oncology/Hematology)")
_ko_address = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="401 Aspen Way, Springfield, IL 62721")

dr_obrien.attributes.extend([_ko_dob, _ko_salary, _ko_license, _ko_address])

dr_obrien.knowledge_base.extend([
    KnowledgeState(agent_id=linda_torres.uid, known_attribute=_lt_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=linda_torres.uid, known_attribute=_lt_medication,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=linda_torres.uid, known_attribute=_lt_history,
                   transmission_principle="Doctor-Patient Confidentiality"),
])

# ---------------------------------------------------------------------------
# New employees — Nurses
# ---------------------------------------------------------------------------

# -- Nurse Lisa Kim (assists Dr. Patel; David Park & Sarah Wilson) ----------
nurse_kim = Employee(name="Nurse Lisa Kim", salary=74_000.0, role=NURSE_ROLE)

_lk_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1992-06-30")
_lk_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="74000")
_lk_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="56 Fern Ct, Springfield, IL 62722")

nurse_kim.attributes.extend([_lk_dob, _lk_salary, _lk_address])

nurse_kim.knowledge_base.extend([
    KnowledgeState(agent_id=david_park.uid,   known_attribute=_dp_medication,
                   transmission_principle="Need-to-Know — Nursing Care"),
    KnowledgeState(agent_id=sarah_wilson.uid, known_attribute=_sw_medication,
                   transmission_principle="Need-to-Know — Nursing Care"),
])

# -- Nurse Carlos Mendez (assists Dr. O'Brien; Linda Torres) ----------------
nurse_mendez = Employee(name="Nurse Carlos Mendez", salary=71_000.0, role=NURSE_ROLE)

_cm_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1988-09-11")
_cm_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="71000")
_cm_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="134 Grove St, Springfield, IL 62723")

nurse_mendez.attributes.extend([_cm_dob, _cm_salary, _cm_address])

nurse_mendez.knowledge_base.extend([
    KnowledgeState(agent_id=linda_torres.uid, known_attribute=_lt_medication,
                   transmission_principle="Need-to-Know — Nursing Care"),
])

# ---------------------------------------------------------------------------
# New employees — Administrative
# ---------------------------------------------------------------------------

# -- Jennifer Walsh (Billing Specialist #2) ---------------------------------
jennifer_walsh = Employee(name="Jennifer Walsh", salary=52_000.0, role=BILLING_ROLE)

_jw_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1984-02-28")
_jw_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="52000")
_jw_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="77 Cypress Dr, Springfield, IL 62724")

jennifer_walsh.attributes.extend([_jw_dob, _jw_salary, _jw_address])

jennifer_walsh.knowledge_base.extend([
    KnowledgeState(agent_id=james_carter.uid,   known_attribute=_jc_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=james_carter.uid,   known_attribute=_jc_insurance,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=michael_chen.uid,   known_attribute=_mc_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=michael_chen.uid,   known_attribute=_mc_insurance,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=linda_torres.uid,   known_attribute=_lt_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=linda_torres.uid,   known_attribute=_lt_insurance,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=patricia_moore.uid, known_attribute=_pm_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=patricia_moore.uid, known_attribute=_pm_insurance,
                   transmission_principle="Operational — Billing"),
])

# -- Richard Park (Deputy HR Manager) --------------------------------------
richard_park = Employee(name="Richard Park", salary=78_000.0, role=HR_ROLE)

_rp_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1976-07-19")
_rp_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="78000")
_rp_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="293 Maple Run, Springfield, IL 62725")

richard_park.attributes.extend([_rp_dob, _rp_salary, _rp_address])

richard_park.knowledge_base.extend([
    KnowledgeState(agent_id=dr_patel.uid,       known_attribute=_ap_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=dr_obrien.uid,      known_attribute=_ko_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=nurse_kim.uid,      known_attribute=_lk_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=nurse_mendez.uid,   known_attribute=_cm_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=jennifer_walsh.uid, known_attribute=_jw_salary,
                   transmission_principle="Employment — Confidential HR"),
])

# ---------------------------------------------------------------------------
# New contractors
# ---------------------------------------------------------------------------

frank_turner = Contractor(
    name="Frank Turner",
    hourly_rate=88.0,
    contract_start="2026-01-01",
    contract_end="2026-12-31",
    role=IT_CONTRACTOR_ROLE,
)

_ft_dob      = Attribute(information_type=AttributeType.DATE_OF_BIRTH,  attribute="1985-03-12")
_ft_contract = Attribute(information_type=AttributeType.CONTRACT_TERMS, attribute="IT infrastructure support; $88/hr; no PHI access permitted")
_ft_address  = Attribute(information_type=AttributeType.HOME_ADDRESS,   attribute="512 Birch Pl, Springfield, IL 62726")

frank_turner.attributes.extend([_ft_dob, _ft_contract, _ft_address])

# ---------------------------------------------------------------------------
# Extended collections and registries
# ---------------------------------------------------------------------------

NEW_PATIENTS    = [david_park, sarah_wilson, james_carter, linda_torres, michael_chen, patricia_moore]
NEW_EMPLOYEES   = [dr_patel, dr_obrien, nurse_kim, nurse_mendez, jennifer_walsh, richard_park]
NEW_CONTRACTORS = [frank_turner]

EXTENDED_ALL_PATIENTS    = ALL_PATIENTS    + NEW_PATIENTS
EXTENDED_ALL_EMPLOYEES   = ALL_EMPLOYEES   + NEW_EMPLOYEES
EXTENDED_ALL_CONTRACTORS = ALL_CONTRACTORS + NEW_CONTRACTORS
EXTENDED_ALL_AGENTS      = EXTENDED_ALL_PATIENTS + EXTENDED_ALL_EMPLOYEES + EXTENDED_ALL_CONTRACTORS

EXTENDED_NAME_REGISTRY: dict = {a.name: a for a in EXTENDED_ALL_AGENTS if a.name}


if __name__ == "__main__":
    print(f"Extended agent pool: {len(EXTENDED_ALL_AGENTS)} agents")
    print(f"  Patients    : {len(EXTENDED_ALL_PATIENTS)}")
    print(f"  Employees   : {len(EXTENDED_ALL_EMPLOYEES)}")
    print(f"  Contractors : {len(EXTENDED_ALL_CONTRACTORS)}")
    print()
    for a in EXTENDED_ALL_AGENTS:
        role = getattr(a, "role", "—")
        print(f"  {a.name:<30} {role}")
