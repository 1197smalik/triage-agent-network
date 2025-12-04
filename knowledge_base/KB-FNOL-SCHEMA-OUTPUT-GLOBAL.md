# KB-FNOL-SCHEMA-OUTPUT-GLOBAL

## Purpose

Define the standardized internal FNOL input schema and the claim assessment output schema that the AI system must use.

These schemas should be used for:

- Converting unstructured workshop email FNOL into structured JSON.
- Producing consistent claim assessment outputs back to downstream systems.

---

## FNOL Internal Schema (Logical)

Top-level object: `FNOL`.

Fields:

- `source`
  - Origin of the FNOL (e.g. Workshop_Email).

- `workshop`
  - Workshop ID, name, email, and optional phone.

- `policy`
  - Policy ID, status, coverage type, add-ons, usage, and validity dates.

- `vehicle`
  - VIN, registration number, make, model, year, odometer.

- `incident`
  - Date, time, location, impact point, incident type, narrative, and third-party involvement flag.

- `documents`
  - Presence flags for police report, driver license, RC, estimate, and photo count.

- `cv_results`
  - CV-detected damaged parts, OCR results for identification, and any pre-existing damage signals.

The AI should normalize all inputs (email body text and attachments) into this FNOL schema before assessment.

---

## Claim Assessment Output Schema (Logical)

Top-level object: `claim_assessment`.

Fields:

- `claim_reference_id`
  - String identifier generated for the claim.

- `eligibility`
  - One of: Approved, Rejected, Review.

- `eligibility_reason`
  - Short text explaining the main reasoning behind eligibility.

- `coverage_applicable`
  - List of logical coverage labels:
    - OwnDamage
    - ThirdPartyLiability
    - Fire
    - Theft
    - Glass
    - None

- `excluded_reasons`
  - List of brief text reasons explaining exclusions or partial coverage.

- `required_followups`
  - List of actions needed to move the claim forward (e.g. request more photos, request police report).

- `fraud_risk_level`
  - One of: Low, Medium, High.

- `fraud_flags`
  - List of short strings describing fraud or anomaly signals (for human adjusters).

- `damage_summary`
  - Object describing the main impact area, overall severity, and a list of damaged parts with severity.

- `recommendation`
  - Contains:
    - `action`:
      - Proceed_With_Claim
      - Reject_Claim
      - Escalate_To_Human
    - `notes_for_handler`:
      - Human-readable guidance for the claim handler.

- `audit_log`
  - List of entries:
    - `rule_id`: references a KB rule that influenced a decision.
    - `decision_effect`: Approved / Rejected / Flagged / NoEffect.
    - `note`: short explanation of how the rule was applied.

---

## FNOL Acknowledgment Template (Logical)

When a FNOL is ingested, the system should be able to create an acknowledgment:

- Recipient: workshop email.
- Subject: includes the claim reference ID.
- Body: confirms receipt and lists missing or unclear items if any.

This template should be parameterized so that the AI can populate:

- Claim reference ID.
- Vehicle registration number.
- Policy ID (if known).
- Current status (Received, Incomplete, Under Review).
- Required follow-ups.

---

## Usage in the System

1. **Input side**
   - Workshop email + attachments are parsed into the `FNOL` schema.

2. **Assessment side**
   - The `FNOL` object is combined with KB rules via RAG.
   - The LLM applies rules and outputs a `claim_assessment` object.

3. **Downstream**
   - The `claim_assessment` object is used for:
     - Storing claim triage results.
     - Triggering emails or workflow transitions.
     - Providing structured input to adjuster tools or core systems.
