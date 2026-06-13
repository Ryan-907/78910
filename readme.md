# CI-Sim: Contextual Integrity in an LLM Agentic System

A research simulation applying **Contextual Integrity (CI)** theory to LLM-based information retrieval. The system models a medical clinic where a local language model acts as an information retrieval agent, and CI norms are used to decide which information flows are appropriate or inappropriate — without the LLM itself reasoning about privacy.

This is a staged implementation. **Phase 1** (current) runs all information requests through the agent and logs every flow without enforcement. **Phase 2** will insert a CI policy gate inside the retrieval tool so that inappropriate flows are blocked before data is returned to the model.

---

## Theoretical Background

Contextual Integrity, introduced by Helen Nissenbaum and formalized by Barth et al. (2006), defines privacy not as secrecy but as **appropriate information flow**. A flow is appropriate when it matches the norms of the context in which the information originated.

For example, a patient's diagnosis shared with their treating physician under doctor-patient confidentiality is appropriate. That same diagnosis shared with a billing specialist is not — even if both are employees of the same clinic — because it violates the norms of the medical context.

The key insight this project exploits: the LLM does not need to reason about privacy. By treating the LLM as an **untrusted requester** and gating the retrieval tool with CI logic, the system enforces privacy at the infrastructure level regardless of what the model asks for.

---

## Architecture

```
User / Scenario
      │
      ▼
  main.py  ─── builds system prompt with requester context
      │         and injects tool schema into LLM
      │
      ▼
  Llama-3.1-8B-Instruct  (local, via HuggingFace pipeline)
      │
      │  returns JSON: { function, arguments }  or  { message }
      ▼
  run_agent()  ─── parses response, dispatches tool call
      │
      ▼
  lookup_attribute()      ←── Phase 2 will add CI gate here
      │
      ▼
  clinic.py / NAME_REGISTRY  ─── returns attribute value
      │
      ▼
  LLM receives tool result, returns final { message }
      │
      ▼
  log_flow()  ─── records InformationFlow to flow_log.json
```

---

## File Reference

### `Agent.py` — Core Data Models

Defines the fundamental building blocks of the simulation using Pydantic models.

**`Attribute`**
Represents a single piece of private information about a person. Has two fields:
- `information_type` — the category of data (e.g. `"medical_diagnosis"`, `"salary"`). This is the field CI policy checks against.
- `attribute` — the actual value (e.g. `"Type 2 Diabetes Mellitus (E11)"`).

**`AttributeType`**
A namespace class of string constants for every supported information type. Used throughout the codebase to avoid raw string literals:

```
medical_diagnosis, medical_medication, medical_history, mental_health,
billing_code, insurance_info, salary, ssn, date_of_birth,
home_address, emergency_contact, contract_terms, employment_contract, medical_license
```

`mental_health` is treated as extra-sensitive — a subset of medical data with stricter access norms.

**`Role`**
A `(role, context)` pair representing the capacity in which someone is acting. Examples: `Role(role="Doctor", context="Medical")`, `Role(role="Billing Specialist", context="Administrative")`. Context is important for CI — a doctor acting as a patient has different access rights than a doctor acting in a clinical role.

**`KnowledgeState`**
Represents one piece of information that an agent *knows about another agent*. Tracks:
- `agent_id` — whose information it is
- `known_attribute` — the `Attribute` instance
- `transmission_principle` — the norm under which it was received (e.g. `"Doctor-Patient Confidentiality"`, `"Need-to-Know — Nursing Care"`). This principle constrains how the information can be re-shared.

**`Agent`**
The base class for all participants. Has:
- `attributes` — private information *about* this agent
- `knowledge_base` — information this agent knows *about others*, each entry carrying the transmission principle under which it was received
- `roles` — list of `Role` instances the agent can act in
- `send_message()` / `update_knowledge_base()` — methods for simulating knowledge transfer between agents

**Subclasses:** `Employee` (adds `salary`, single active `role`), `Patient` (adds `active` status), `Contractor` (adds `hourly_rate`, `contract_start`, `contract_end`). A `Document` model is also defined for future use.

---

### `ci_policy.py` — Contextual Integrity Framework

Defines the CI primitives that the simulation is built on.

**`InformationFlow`**
The central model for representing a single information transfer event. Fields:
- `subject` — the person the information is *about*
- `sender` — who is transmitting it (currently `None` in Phase 1, since the clinic system is the implicit sender)
- `receiver` — who is requesting / receiving it
- `message_type` — the `AttributeType` string being transferred
- `transmission_principle` — the norm governing this flow (currently `None` in Phase 1)

Every completed request in the simulation is recorded as an `InformationFlow` and written to `flow_log.json`. In Phase 2, a policy function will evaluate an `InformationFlow` before data is released and return allow/deny.

**`Organization`**
A simple container with a `name` and a list of `Employee` instances. Used to define the clinic as an entity.

The file also contains extensive design notes (in the module docstring) about known limitations of the current model — particularly around role ambiguity and attribute inference — which inform the Phase 2 roadmap.

---

### `clinic.py` — Scenario Population

Instantiates the entire simulated world: all agents, their private attributes, their knowledge bases, and the clinic organization. This file is the "ground truth" — it defines what data exists and who legitimately knows what before any LLM requests are made.

**Roles defined:**

| Constant | Role | Context |
|---|---|---|
| `DOCTOR_ROLE` | Doctor | Medical |
| `NURSE_ROLE` | Nurse | Medical |
| `BILLING_ROLE` | Billing Specialist | Administrative |
| `HR_ROLE` | HR Manager | Administrative |
| `IT_CONTRACTOR_ROLE` | IT Contractor | Administrative |
| `PATIENT_ROLE` | Patient | Medical |

**Patients (4):**

| Name | Condition | Notable attributes |
|---|---|---|
| John Smith | Type 2 Diabetes | Metformin, BlueCross PPO |
| Emily Brown | Prenatal, 28 weeks | Gestational hypertension history |
| Robert Lee | Atrial Fibrillation | Warfarin, Medicare |
| Maria Gonzalez | Major Depressive Disorder | Extra-sensitive mental health record |

**Employees (6):**

| Name | Role | Assigned patients / scope |
|---|---|---|
| Dr. Sarah Chen | Doctor | John Smith, Emily Brown |
| Dr. Marcus Webb | Doctor | Robert Lee, Maria Gonzalez |
| Nurse Patricia Davis | Nurse | John Smith, Emily Brown (medications + basic vitals only) |
| Nurse Tom Reyes | Nurse | Robert Lee (medications only) |
| Alice Johnson | Billing Specialist | All patients (billing codes + insurance only — no diagnoses) |
| Bob Martinez | HR Manager | All employee salaries (no patient data) |

**Contractor (1):**

| Name | Role | PHI access |
|---|---|---|
| Carol White | IT Contractor | None — explicitly no patient data in knowledge base |

Knowledge base entries reflect real-world access norms. For example, Alice Johnson's knowledge base contains billing codes and insurance info for all patients, but zero clinical attributes — this is the boundary a CI gate will enforce in Phase 2.

**Exported for use by `main.py`:**
- `NAME_REGISTRY` — `dict[str, Agent]` keyed by full name, used for all lookups
- `ALL_PATIENTS`, `ALL_EMPLOYEES`, `ALL_CONTRACTORS` — typed lists
- `clinic` — the `Organization` instance

Run `clinic.py` directly to print a roster of all agents and their attributes.

---

### `main.py` — Simulation Runner

The entry point. Loads the model, runs pre-defined scenarios, then enters interactive mode.

**Model**

Loads `meta-llama/Llama-3.1-8B-Instruct` locally via HuggingFace `transformers`. The pipeline is configured with `return_full_text=False` so only newly generated tokens are returned, and `device_map="auto"` so it distributes across available GPUs automatically (intended for HPC use).

**`LlmResponse` schema**

The model is instructed to respond exclusively in JSON matching this Pydantic schema:

```python
class LlmResponse(BaseModel):
    message:   str | None   # final answer when no tool call needed
    function:  str | None   # tool name to call
    arguments: dict | None  # keyword arguments for the tool
```

Exactly one of `message` or `function` should be non-null per response.

**`lookup_attribute(subject_name, attribute_type) → str`**

The single tool exposed to the LLM. Takes a person's full name and an `AttributeType` string, looks up the value in `NAME_REGISTRY`, and returns the raw attribute string. In Phase 1 there is no access check — every valid request succeeds. This is where the CI gate will be inserted in Phase 2.

**`run_agent(generator, prompt_base, requester_name, subject_name, attribute_type) → str`**

The agentic loop. Runs up to 5 iterations:
1. Builds the message list (system prompt + user request + optional prior tool context)
2. Calls the generator
3. Extracts the JSON object from the raw output (handles markdown fences and surrounding text)
4. Parses into `LlmResponse`
5. If `function` is set, calls the tool and injects the result as context for the next iteration
6. If `message` is set, returns it as the final answer

**System prompt**

Injected per-request with the requester's name and role, the tool's JSON schema, and the `LlmResponse` JSON schema. Instructs the model never to fabricate values — it must always call `lookup_attribute`.

**Pre-defined scenarios (`SCENARIOS`)**

Nine hardcoded flows covering both appropriate and inappropriate access patterns:

| Flow | Expected verdict |
|---|---|
| Dr. Chen → John Smith diagnosis | Appropriate |
| Nurse Davis → John Smith medication | Appropriate |
| Alice Johnson → Emily Brown insurance | Appropriate |
| Bob Martinez → Dr. Chen salary | Appropriate |
| Alice Johnson → John Smith diagnosis | Inappropriate (billing accessing clinical) |
| Carol White → Maria Gonzalez mental health | Inappropriate (IT contractor, PHI) |
| Bob Martinez → John Smith diagnosis | Inappropriate (HR accessing patient data) |
| Dr. Chen → Robert Lee diagnosis | Questionable (not assigned doctor) |
| Nurse Reyes → Maria Gonzalez mental health | Inappropriate (outside assignment + extra-sensitive) |

Each result is logged via `log_flow()` and printed with a ✓ or ✗ icon.

**Interactive mode**

After the scenario batch, the program enters a REPL:

```
> Alice Johnson | John Smith | medical_diagnosis
```

Any name from `NAME_REGISTRY` and any `AttributeType` string are valid. Type `exit` to quit.

**`flow_log.json`**

Written on exit. Contains every flow event as a JSON object with requester, subject, attribute type, result, CI label, and the serialized `InformationFlow` model. This log is the primary artifact for Phase 2 analysis.

---

### `requirements.txt` — Dependencies

Key packages:

| Package | Purpose |
|---|---|
| `torch` | GPU tensor computation for local model inference |
| `transformers` | HuggingFace model loading and text-generation pipeline |
| `accelerate` | Multi-GPU / device-map support |
| `pydantic` | All data models and JSON schema generation |
| `anthropic` | Reserved for Phase 2 / alternative model experiments |

---

## Setup and Usage

### Prerequisites

- Python 3.10+
- CUDA-capable GPU (the model requires ~16 GB VRAM in bfloat16; tested on HPC with SLURM)
- HuggingFace account with access granted to `meta-llama/Llama-3.1-8B-Instruct`

### Installation

```bash
pip install -r requirements.txt
```

### Running

```bash
python main.py
```

The script will:
1. Download and load the model (first run takes several minutes; cached thereafter)
2. Run all 9 pre-defined scenarios and print results
3. Enter interactive mode for ad-hoc queries
4. Write `flow_log.json` on exit

### Interactive query format

```
> <requester full name> | <subject full name> | <attribute_type>
```

Valid attribute types: `medical_diagnosis`, `medical_medication`, `medical_history`, `mental_health`, `billing_code`, `insurance_info`, `salary`, `ssn`, `date_of_birth`, `home_address`, `emergency_contact`, `contract_terms`, `employment_contract`, `medical_license`

Valid names: any name listed in `clinic.py` (`Dr. Sarah Chen`, `John Smith`, `Alice Johnson`, etc.)

---

## Phase 2 Roadmap

The CI enforcement gate will be added inside `lookup_attribute()` in `main.py`. Before returning any data, it will:

1. Construct an `InformationFlow` with the requester's role and the requested `message_type`
2. Evaluate the flow against a set of CI norms (role-context rules, transmission principle constraints, sensitivity tiers)
3. Return the data if appropriate, or a denial message if not — the LLM receives only what CI permits

The LLM is never told *why* a request was denied, preserving the principle that privacy enforcement is structural rather than negotiated.
