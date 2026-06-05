from __future__ import annotations
from pydantic import BaseModel, Field
from uuid import UUID, uuid4



class Attribute(BaseModel):  # Information about some entity or individual, this an isntance of t in T. T is the set of attributes in Agent.
    
    information_type: str | None = Field(description=( # May later become a list of possible categories, for simplicity. This is the only thing that really matters. The attribute itself is less important that what its value is, we can use the PII in panorama as the potential types!
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


class Document(BaseModel):

    title: str = Field(description="The document title")

    attributes: list[Attribute] = Field(default_factory=list, description="The attributes the document is concerned with")

    agent: Agent = Field(description="The Agent mentioned in the document")

    