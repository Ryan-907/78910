"""
Riverside Medical Clinic — scenario population.

Instantiates all agents (doctors, nurses, billing, HR, IT contractor, patients)
with realistic private attributes and initial knowledge states.

Import `clinic` (Organization) or individual agents for use in the simulation.
"""

from core.Agent import (
    Agent, Attribute, AttributeType, KnowledgeState, Role,
    Employee, Patient, Contractor,
)
from core.ci_policy import Organization

# ---------------------------------------------------------------------------
# Standard roles
# ---------------------------------------------------------------------------

DOCTOR_ROLE       = Role(role="Doctor",            context="Medical")
NURSE_ROLE        = Role(role="Nurse",             context="Medical")
BILLING_ROLE      = Role(role="Billing Specialist", context="Administrative")
HR_ROLE           = Role(role="HR Manager",        context="Administrative")
IT_CONTRACTOR_ROLE = Role(role="IT Contractor",    context="Administrative")
PATIENT_ROLE      = Role(role="Patient",           context="Medical")

# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

# -- John Smith (Type 2 Diabetes) -------------------------------------------
john_smith = Patient(name="John Smith", active=True, role=PATIENT_ROLE)

_js_dob         = Attribute(information_type=AttributeType.DATE_OF_BIRTH,     attribute="1968-03-14")
_js_ssn         = Attribute(information_type=AttributeType.SSN,               attribute="XXX-XX-4821")
_js_address     = Attribute(information_type=AttributeType.HOME_ADDRESS,      attribute="412 Maple St, Springfield, IL 62701")
_js_diagnosis   = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS, attribute="Type 2 Diabetes Mellitus (E11)")
_js_medication  = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Metformin 500 mg twice daily")
_js_history     = Attribute(information_type=AttributeType.MEDICAL_HISTORY,   attribute="Hypertension diagnosed 2015; prediabetes since 2018")
_js_insurance   = Attribute(information_type=AttributeType.INSURANCE_INFO,    attribute="BlueCross PPO #BC-847261")
_js_emergency   = Attribute(information_type=AttributeType.EMERGENCY_CONTACT, attribute="Mary Smith (spouse) 555-0142")
_js_billing     = Attribute(information_type=AttributeType.BILLING_CODE,      attribute="99213, E11.9")

john_smith.attributes.extend([
    _js_dob, _js_ssn, _js_address, _js_diagnosis,
    _js_medication, _js_history, _js_insurance, _js_emergency, _js_billing,
])

# -- Emily Brown (Prenatal care) --------------------------------------------
emily_brown = Patient(name="Emily Brown", active=True, role=PATIENT_ROLE)

_eb_dob         = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1991-07-22")
_eb_ssn         = Attribute(information_type=AttributeType.SSN,             attribute="XXX-XX-3307")
_eb_address     = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="89 Birch Lane, Springfield, IL 62702")
_eb_diagnosis   = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS, attribute="Intrauterine pregnancy, 28 weeks (Z34.32)")
_eb_history     = Attribute(information_type=AttributeType.MEDICAL_HISTORY, attribute="Gestational hypertension in prior pregnancy")
_eb_insurance   = Attribute(information_type=AttributeType.INSURANCE_INFO,  attribute="Aetna HMO #AE-201934")
_eb_billing     = Attribute(information_type=AttributeType.BILLING_CODE,    attribute="59400, Z34.32")

emily_brown.attributes.extend([
    _eb_dob, _eb_ssn, _eb_address, _eb_diagnosis,
    _eb_history, _eb_insurance, _eb_billing,
])

# -- Robert Lee (Atrial Fibrillation) ---------------------------------------
robert_lee = Patient(name="Robert Lee", active=True, role=PATIENT_ROLE)

_rl_dob         = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1955-11-09")
_rl_ssn         = Attribute(information_type=AttributeType.SSN,             attribute="XXX-XX-6614")
_rl_address     = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="230 Oak Ave, Springfield, IL 62703")
_rl_diagnosis   = Attribute(information_type=AttributeType.MEDICAL_DIAGNOSIS, attribute="Atrial Fibrillation, persistent (I48.11)")
_rl_medication  = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Warfarin 5 mg daily; INR monitored monthly")
_rl_insurance   = Attribute(information_type=AttributeType.INSURANCE_INFO,  attribute="Medicare Part B #1EG4-TE5-MK72")
_rl_billing     = Attribute(information_type=AttributeType.BILLING_CODE,    attribute="99214, I48.11")

robert_lee.attributes.extend([
    _rl_dob, _rl_ssn, _rl_address, _rl_diagnosis,
    _rl_medication, _rl_insurance, _rl_billing,
])

# -- Maria Gonzalez (Major Depressive Disorder — extra-sensitive) -----------
maria_gonzalez = Patient(name="Maria Gonzalez", active=True, role=PATIENT_ROLE)

_mg_dob         = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1983-05-30")
_mg_ssn         = Attribute(information_type=AttributeType.SSN,             attribute="XXX-XX-9052")
_mg_address     = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="15 Elm Court, Springfield, IL 62704")
_mg_diagnosis   = Attribute(information_type=AttributeType.MENTAL_HEALTH,   attribute="Major Depressive Disorder, recurrent (F33.1)")
_mg_medication  = Attribute(information_type=AttributeType.MEDICAL_MEDICATION, attribute="Sertraline 100 mg daily")
_mg_insurance   = Attribute(information_type=AttributeType.INSURANCE_INFO,  attribute="United Health PPO #UH-558812")
_mg_billing     = Attribute(information_type=AttributeType.BILLING_CODE,    attribute="90837, F33.1")

maria_gonzalez.attributes.extend([
    _mg_dob, _mg_ssn, _mg_address, _mg_diagnosis,
    _mg_medication, _mg_insurance, _mg_billing,
])

# ---------------------------------------------------------------------------
# Employees — Doctors
# ---------------------------------------------------------------------------

# -- Dr. Sarah Chen (Internal Medicine; cares for John Smith & Emily Brown) -
dr_chen = Employee(name="Dr. Sarah Chen", salary=215_000.0, role=DOCTOR_ROLE)

_sc_dob         = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1975-04-18")
_sc_salary      = Attribute(information_type=AttributeType.SALARY,          attribute="215000")
_sc_license     = Attribute(information_type=AttributeType.MEDICAL_LICENSE, attribute="IL-MD-48821 (Internal Medicine)")
_sc_address     = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="304 Willow Rd, Springfield, IL 62706")

dr_chen.attributes.extend([_sc_dob, _sc_salary, _sc_license, _sc_address])

# Dr. Chen's knowledge about her patients
dr_chen.knowledge_base.extend([
    KnowledgeState(agent_id=john_smith.uid, known_attribute=_js_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=john_smith.uid, known_attribute=_js_medication,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=john_smith.uid, known_attribute=_js_history,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=emily_brown.uid, known_attribute=_eb_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=emily_brown.uid, known_attribute=_eb_history,
                   transmission_principle="Doctor-Patient Confidentiality"),
])

# -- Dr. Marcus Webb (Cardiology + Psychiatry referrals; cares for Robert Lee & Maria Gonzalez) --
dr_webb = Employee(name="Dr. Marcus Webb", salary=240_000.0, role=DOCTOR_ROLE)

_mw_dob         = Attribute(information_type=AttributeType.DATE_OF_BIRTH,   attribute="1969-09-03")
_mw_salary      = Attribute(information_type=AttributeType.SALARY,          attribute="240000")
_mw_license     = Attribute(information_type=AttributeType.MEDICAL_LICENSE, attribute="IL-MD-30115 (Cardiology)")
_mw_address     = Attribute(information_type=AttributeType.HOME_ADDRESS,    attribute="57 Pine St, Springfield, IL 62707")

dr_webb.attributes.extend([_mw_dob, _mw_salary, _mw_license, _mw_address])

dr_webb.knowledge_base.extend([
    KnowledgeState(agent_id=robert_lee.uid, known_attribute=_rl_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=robert_lee.uid, known_attribute=_rl_medication,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=maria_gonzalez.uid, known_attribute=_mg_diagnosis,
                   transmission_principle="Doctor-Patient Confidentiality"),
    KnowledgeState(agent_id=maria_gonzalez.uid, known_attribute=_mg_medication,
                   transmission_principle="Doctor-Patient Confidentiality"),
])

# ---------------------------------------------------------------------------
# Employees — Nurses
# ---------------------------------------------------------------------------

# -- Nurse Patricia Davis (assists Dr. Chen; John Smith & Emily Brown) ------
nurse_davis = Employee(name="Nurse Patricia Davis", salary=72_000.0, role=NURSE_ROLE)

_pd_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1985-12-01")
_pd_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="72000")
_pd_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="19 Cedar Blvd, Springfield, IL 62708")

nurse_davis.attributes.extend([_pd_dob, _pd_salary, _pd_address])

# Nurses know medications and basic vitals, but not full diagnosis history
nurse_davis.knowledge_base.extend([
    KnowledgeState(agent_id=john_smith.uid, known_attribute=_js_medication,
                   transmission_principle="Need-to-Know — Nursing Care"),
    KnowledgeState(agent_id=emily_brown.uid, known_attribute=_eb_diagnosis,
                   transmission_principle="Need-to-Know — Nursing Care"),
])

# -- Nurse Tom Reyes (assists Dr. Webb; Robert Lee) -------------------------
nurse_reyes = Employee(name="Nurse Tom Reyes", salary=68_000.0, role=NURSE_ROLE)

_tr_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1990-02-14")
_tr_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="68000")
_tr_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="72 Spruce Ave, Springfield, IL 62709")

nurse_reyes.attributes.extend([_tr_dob, _tr_salary, _tr_address])

nurse_reyes.knowledge_base.extend([
    KnowledgeState(agent_id=robert_lee.uid, known_attribute=_rl_medication,
                   transmission_principle="Need-to-Know — Nursing Care"),
])

# ---------------------------------------------------------------------------
# Employees — Administrative
# ---------------------------------------------------------------------------

# -- Alice Johnson (Billing Specialist) -------------------------------------
alice_johnson = Employee(name="Alice Johnson", salary=55_000.0, role=BILLING_ROLE)

_aj_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1980-08-19")
_aj_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="55000")
_aj_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="88 Ash Lane, Springfield, IL 62710")

alice_johnson.attributes.extend([_aj_dob, _aj_salary, _aj_address])

# Billing knows billing codes and insurance — NOT clinical diagnoses
alice_johnson.knowledge_base.extend([
    KnowledgeState(agent_id=john_smith.uid,    known_attribute=_js_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=john_smith.uid,    known_attribute=_js_insurance,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=emily_brown.uid,   known_attribute=_eb_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=emily_brown.uid,   known_attribute=_eb_insurance,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=robert_lee.uid,    known_attribute=_rl_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=robert_lee.uid,    known_attribute=_rl_insurance,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=maria_gonzalez.uid, known_attribute=_mg_billing,
                   transmission_principle="Operational — Billing"),
    KnowledgeState(agent_id=maria_gonzalez.uid, known_attribute=_mg_insurance,
                   transmission_principle="Operational — Billing"),
])

# -- Bob Martinez (HR Manager) ----------------------------------------------
bob_martinez = Employee(name="Bob Martinez", salary=85_000.0, role=HR_ROLE)

_bm_dob     = Attribute(information_type=AttributeType.DATE_OF_BIRTH, attribute="1972-06-25")
_bm_salary  = Attribute(information_type=AttributeType.SALARY,        attribute="85000")
_bm_address = Attribute(information_type=AttributeType.HOME_ADDRESS,  attribute="201 Redwood Dr, Springfield, IL 62711")

bob_martinez.attributes.extend([_bm_dob, _bm_salary, _bm_address])

# HR knows all employee salaries and employment contracts
bob_martinez.knowledge_base.extend([
    KnowledgeState(agent_id=dr_chen.uid,    known_attribute=_sc_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=dr_webb.uid,    known_attribute=_mw_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=nurse_davis.uid, known_attribute=_pd_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=nurse_reyes.uid, known_attribute=_tr_salary,
                   transmission_principle="Employment — Confidential HR"),
    KnowledgeState(agent_id=alice_johnson.uid, known_attribute=_aj_salary,
                   transmission_principle="Employment — Confidential HR"),
])

# ---------------------------------------------------------------------------
# Contractor — IT
# ---------------------------------------------------------------------------

carol_white = Contractor(
    name="Carol White",
    hourly_rate=95.0,
    contract_start="2026-01-01",
    contract_end="2026-12-31",
    role=IT_CONTRACTOR_ROLE,
)

_cw_dob      = Attribute(information_type=AttributeType.DATE_OF_BIRTH,    attribute="1988-10-07")
_cw_contract = Attribute(information_type=AttributeType.CONTRACT_TERMS,   attribute="IT systems support; 95/hr; no PHI access permitted")
_cw_address  = Attribute(information_type=AttributeType.HOME_ADDRESS,     attribute="330 Poplar St, Springfield, IL 62712")

carol_white.attributes.extend([_cw_dob, _cw_contract, _cw_address])

# Carol has no patient knowledge — this is enforced by CI policy
# (no knowledge_base entries for patient data)

# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

clinic = Organization(
    name="Riverside Medical Clinic",
    employees=[dr_chen, dr_webb, nurse_davis, nurse_reyes, alice_johnson, bob_martinez],
)

# Convenience collections used by the simulation layer
ALL_PATIENTS    = [john_smith, emily_brown, robert_lee, maria_gonzalez]
ALL_EMPLOYEES   = clinic.employees
ALL_CONTRACTORS = [carol_white]
ALL_AGENTS      = [*ALL_PATIENTS, *ALL_EMPLOYEES, *ALL_CONTRACTORS]

# Index agents by UID and by name for fast lookup
AGENT_REGISTRY: dict = {str(a.uid): a for a in ALL_AGENTS}
NAME_REGISTRY:  dict = {a.name: a for a in ALL_AGENTS if a.name}


# Sentinel agent representing the clinic's own records system.
# Used as the `sender` in every InformationFlow — the system is what
# physically releases data to a requester, regardless of who originated it.
clinic_system = Agent(name="Riverside Medical Clinic Records System", roles=[])


if __name__ == "__main__":
    print(f"Clinic: {clinic.name}")
    print(f"  Employees : {len(ALL_EMPLOYEES)}")
    print(f"  Patients  : {len(ALL_PATIENTS)}")
    print(f"  Contractors: {len(ALL_CONTRACTORS)}")
    print()
    for agent in ALL_AGENTS:
        role_label = getattr(agent, "role", "—")
        print(f"  {type(agent).__name__} [{agent.uid}]  role={role_label}")
        for attr in agent.attributes:
            print(f"      attr: {attr.information_type} = {attr.attribute}")
        if agent.knowledge_base:
            print(f"      knows {len(agent.knowledge_base)} attribute(s) about others")
