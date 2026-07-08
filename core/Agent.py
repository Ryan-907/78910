from __future__ import annotations
from pydantic import BaseModel, Field
from uuid import UUID, uuid4



class Attribute(BaseModel):  # Information about some entity or individual, this an isntance of t in T. T is the set of attributes in Agent.
    
    information_type: str | None = Field(description=( # May later become a list of possible categories, for simplicity. This is the only thing that really matters. The attribute itself is less important than what its value is.
        "Type of information (e.g. health)"
    ), default= None)

    attribute: str  | None = Field(description=( 
        "The attribute itself, probably from some document about some Agent"
    ), default=None)




class Role(BaseModel): # Defines agent roles in context, could be latent or apart of Agent, revisit later. 
    
    role: str = Field(description=(
        "The roles title (e.g. 'Doctor')"
    ))

    context: str = Field(description=(
        "The context in which the role exists (e.g. 'Medical Field')"
    ))




class KnowledgeState(BaseModel): # Knowledge of some particular attribute about some particualr agent. Some t know about q.
    
    agent_id: UUID = Field(description=(
        "UID of the agent about whom the attribute is known"
    ))

    known_attribute: Attribute = Field(description=(
        "The attribute known about the Agent"
    ))

    transmission_principle: str = Field(description=(
        "The principle for how the informatio is handled. e.g. if Alice tells Bob her age under the principle of "
        "confidentiality, then, in the future, Bob must not disclose Alice’s age."
    ))




class Agent(BaseModel): # Some agent that may be subject, seder, or receiver

    uid: UUID = Field(alias='id', default_factory=uuid4)

    name: str | None = Field(default=None, description="Human-readable name of the agent")

    attributes: list[Attribute] = Field(default_factory=list, description=( # t about p
        "List of Attributes about the Agent"
        ))
     
    knowledge_base: list[KnowledgeState] = Field(default_factory=list, description=( # Each item in the list represets the (p,q,t) tripple. Some t known about q by p, where p is the Agent instance that may or may not be q. 
        "List of attributes known about other agents."
        ))
    
    roles: list[Role] | None = Field(default_factory=list, description=( # May be changed to a limited list of potential roles, roles may be a class to create. 
        "List of roles the agent could be acting in"
    ))

    def update_knowledge_base(self, knowledge: list[KnowledgeState]) -> None: # Updates Knowledge base based on received message.
        self.knowledge_base.extend(knowledge)

    def send_message(self, p2: Agent, content: list[KnowledgeState]):
        p2.update_knowledge_base(content)

    def in_role(self, role):
        return role in self.roles




class AttributeType:
    MEDICAL_DIAGNOSIS   = "medical_diagnosis"
    MEDICAL_MEDICATION  = "medical_medication"
    MEDICAL_HISTORY     = "medical_history"
    MENTAL_HEALTH       = "mental_health"       # extra-sensitive subset of medical
    BILLING_CODE        = "billing_code"
    INSURANCE_INFO      = "insurance_info"
    SALARY              = "salary"
    SSN                 = "ssn"
    DATE_OF_BIRTH       = "date_of_birth"
    HOME_ADDRESS        = "home_address"
    EMERGENCY_CONTACT   = "emergency_contact"
    CONTRACT_TERMS      = "contract_terms"
    EMPLOYMENT_CONTRACT = "employment_contract"
    MEDICAL_LICENSE     = "medical_license"


class Employee(Agent):

    salary: float = Field(description="The yearly salary of the employee concerned")

    role: Role = Field(description="The role the employee is active in with the organization")


class Patient(Agent):

    active: bool = Field(description="True if the patient is current; False if former")

    role: Role = Field(description="The patient's role (typically Role(role='Patient', context='Medical'))")


class Contractor(Agent):

    hourly_rate: float = Field(description="Contractor's hourly billing rate")

    contract_start: str = Field(description="ISO-8601 start date of the contract")

    contract_end: str = Field(description="ISO-8601 end date of the contract")

    role: Role = Field(description="The role the contractor is active in with the organization")


class OriginatingContext:
    MEDICAL        = "Medical"
    ADMINISTRATIVE = "Administrative"
    HR             = "HR"
    LEGAL          = "Legal"
    PUBLIC         = "Public"
    INTERNAL       = "Internal"


class TransmissionPrinciple:
    TREATMENT           = "Doctor-Patient Confidentiality"
    TREATMENT_SENSITIVE = "Doctor-Patient Confidentiality — Extra-Sensitive"
    NURSING_CARE        = "Need-to-Know — Nursing Care"
    BILLING             = "Operational — Billing"
    HR_CONFIDENTIAL     = "Employment — Confidential HR"
    PUBLIC_DISCLOSURE   = "Public Disclosure"
    INTERNAL_OPS        = "Internal Operations"
    LEGAL               = "Legal Hold"


class SubjectType:
    PATIENT      = "patient"
    EMPLOYEE     = "employee"
    CONTRACTOR   = "contractor"
    ORGANIZATION = "organization"


class DocumentType:
    """String constants for every supported record kind."""
    # Clinical
    CLINICAL_NOTE             = "clinical_note"
    PRESCRIPTION              = "prescription"
    LAB_REPORT                = "lab_report"
    RADIOLOGY_REPORT          = "radiology_report"
    DISCHARGE_SUMMARY         = "discharge_summary"
    MENTAL_HEALTH_ASSESSMENT  = "mental_health_assessment"
    REFERRAL_LETTER           = "referral_letter"
    # Billing / Insurance
    INSURANCE_CLAIM           = "insurance_claim"
    BILLING_STATEMENT         = "billing_statement"
    EXPLANATION_OF_BENEFITS   = "explanation_of_benefits"
    PRIOR_AUTHORIZATION       = "prior_authorization"
    INSURANCE_VERIFICATION    = "insurance_verification"
    # HR / Employment
    EMPLOYMENT_CONTRACT       = "employment_contract"
    SALARY_LETTER             = "salary_letter"
    PERFORMANCE_REVIEW        = "performance_review"
    CREDENTIALING_FILE        = "credentialing_file"
    CONTRACTOR_AGREEMENT      = "contractor_agreement"
    # Operational / Benign
    STAFF_SCHEDULE            = "staff_schedule"
    MEETING_AGENDA            = "meeting_agenda"
    POLICY_MEMO               = "policy_memo"
    PUBLIC_PAMPHLET           = "public_pamphlet"


class SensitivityTier:
    """
    Ordered tiers from least to most protected.
    The tier determines which transmission principles apply and which roles
    may ever be a permitted receiver.
    """
    PUBLIC             = "public"             # No private info; freely shareable
    INTERNAL           = "internal"           # Org-internal; not private, not public
    PII_BASIC          = "pii_basic"          # Name, DOB, address — identifiable only
    CLINICAL_STANDARD  = "clinical_standard"  # Diagnosis, meds, history
    CLINICAL_SENSITIVE = "clinical_sensitive" # Mental health, substance abuse, HIV, reproductive
    FINANCIAL          = "financial"          # Billing codes, insurance numbers, salary
    EMPLOYMENT         = "employment"         # Contracts, HR records


class DocumentLabel(BaseModel):
    """
    CI metadata attached to every Document.
    Encodes where the document came from, what it contains, and who
    may legitimately receive it — the three things evaluate_flow() needs.
    """
    document_type: str = Field(
        description="DocumentType constant identifying the record kind"
    )
    originating_context: str = Field(
        description="CI context in which this document was created "
                    "(e.g. 'Medical', 'Administrative', 'HR', 'Public', 'Internal')"
    )
    sensitivity_tier: str = Field(
        description="SensitivityTier constant governing applicable transmission principles"
    )
    subject_type: str = Field(
        default=SubjectType.PATIENT,
        description="SubjectType constant — patient, employee, contractor, or organization"
    )
    pii_attributes: list[str] = Field(
        default_factory=list,
        description="AttributeType constants explicitly present in the document"
    )
    implied_attributes: list[str] = Field(
        default_factory=list,
        description="AttributeType constants inferable from the document "
                    "(e.g. ICD billing codes imply medical_diagnosis)"
    )
    extra_sensitive: bool = Field(
        default=False,
        description="True for mental health, substance abuse, HIV/AIDS, and reproductive records"
    )
    extra_sensitive_reason: str | None = Field(
        default=None,
        description="mental_health | substance_abuse | hiv_aids | reproductive | None"
    )
    permitted_receiver_roles: list[str] = Field(
        default_factory=list,
        description="Role names that may legitimately receive this document"
    )
    assignment_required: bool = Field(
        default=True,
        description="Whether the gate must confirm the receiver holds this subject in their knowledge base"
    )
    governing_principle: str | None = Field(
        default=None,
        description="TransmissionPrinciple constant governing this document's flow"
    )


class Document(BaseModel):
    """
    A clinic record (note, claim, contract, etc.) carrying Attributes about an Agent.

    - label   : CI metadata — sensitivity tier, originating context, permitted receivers
    - content : synthetic free-text used when building the training dataset
    derived_attributes() in ci_policy can be run over .attributes to surface
    implied sensitive types (e.g. a billing doc implying a diagnosis via ICD codes)
    before any information flow is evaluated.
    """
    title: str = Field(description="Human-readable record title")
    attributes: list[Attribute] = Field(
        default_factory=list,
        description="Attributes explicitly present in this document"
    )
    agent: Agent | None = Field(
        default=None,
        description="The subject Agent this document concerns; None for org-level documents (schedules, notices)"
    )
    label: DocumentLabel = Field(description="CI label: sensitivity, context, permitted flows")
    content: str | None = Field(
        default=None,
        description="Synthetic document text — populated during dataset generation"
    )

    