from __future__ import annotations
from pydantic import BaseModel, Field
from json import dumps
from Agent import Agent, Role, Employee, Patient, Contractor, Attribute, KnowledgeState

'''
Potential problems: The paper mentions the ability to infer subsets of T from larger subsets of T (e.g. post code in address)
But here, we assume all attributes are discrete values. This is a design choice that may neeed to be changed later. 

Intuitively, an Agent can only send a Message with Attribute(s) that are known by the sending Agent.
A receiving Agents knowledge state is updated upon receipt of message. 

Roles are complex and indetermininate, it may be a good idea to define some "Active" role of senders and recievers, but this complexity
could wait until we get the basics down (e.g. we can assume a person is operating in their highest trust role in all situations, whatever
role that is for a given situation, but saying something like 'Flow is appropriate if [required reciever role] is in Agent.roles.) This
would be inappropriate in settings where a doctor, who can normally get health info, is a customer (and thus should likely not get that
info).  

The paper has it as PxR where we have (Agent, Role) in PotentialState. Thus, (Alice, MD) in p is active as a medical doctor.
While (Alice, Banking Customer) would not have those permissions.

A piece of information may be transmitted under some principle, thus the principle of transmission must be encoded in the message to 
ensure it is not shared if, say, the principle of transmission is confidentiality. 

FUNCTIONS TO ADD
contains(m:list[KnowledgeState],q: Agent,t: attribute) -> bool
incontext(p:agent,c:role.context) -> bool
derived_attributes(T: message/attributes) -> list[Attribute]

POLICIES
We need to define a list of Roles, Contexts, Hirearchies, every attribute type (e.g. height),
the computatio rules, and the norms (policies to check against)

SCENARIO
I must construct some business scenario (e.g. a financial advisor firm, hospital, etc.)
'''


        
class InformationFlow(BaseModel): # Defines some information flow based on contextual integrity. This is the primary class. 

    subject: Agent | None = Field (
        description=(
            "This describes the subject of the information contained in the relevant document"
            ), default = None
    )

    sender: Agent | None = Field(
        description=(
            "The person or entitity attempting to send the information"
        ), default=None
    )

    receiver: Agent | None = Field(
        description=(
            "The entity or person whom the information is being sent to"
        ), default = None
    )

    message_type: str | None = Field( #Derived from information_type in the Attribute class
        description=(
            "Describes acts such as grant/revoke-consent"
        ), default=None
    )

    transmission_principle: str | None = Field( 
        description=(
            "The principle for how the informatio is handled. e.g. if Alice tells Bob her age under the principle of "
            "confidentiality, then, in the future, Bob must not disclose Alice’s age."
        ), default=None
    )

class Organization(BaseModel):
    name: str
    employees: list[Employee] = Field(default_factory=list, description=("List of organizations active employees"))





















if __name__ == "__main__":
    ryan = Agent()
    print(f"Ryan knows {ryan.knowledge_base}")
    marim = Agent()
    marim_height = Attribute(information_type='height', attribute='130cm')
    marim.attributes.append(marim_height)
    marim_height = KnowledgeState(agent_id=marim.uid, known_attribute=marim_height, transmission_principle="Confidentiality")
    marim.knowledge_base.append(marim_height)

    marim.send_message(ryan, marim.knowledge_base)
    print(f"Ryan knows {[i.model_dump_json() for i in ryan.knowledge_base]}")
