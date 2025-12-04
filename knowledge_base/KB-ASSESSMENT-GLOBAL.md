# KB-ASSESSMENT-GLOBAL

## Purpose

Provide policy-driven rules for assessing motor claims based on FNOL, policy metadata, incident details, and supporting evidence.

---

## Assessment Stages

The AI assessment should proceed in these stages:

1. **Policy applicability**
2. **Incident legitimacy**
3. **Driver authorization and legality**
4. **Incident–damage causality**
5. **Evidence sufficiency**
6. **Liability reference (own vs third party)**
7. **Final decision: Approved / Rejected / Review**

---

## Stage 1 – Policy Applicability

Checks:

- Policy status at incident date:
  - Active → continue.
  - Expired / Suspended → reject on policy grounds.
- Incident date inside policy validity period.
- Coverage type alignment:
  - Incident cause and impacted coverage must be consistent with coverage type (TPL / OD / COMP / FT / GC).

If policy is not applicable, the claim should be marked **Rejected** with reason referencing policy state.

---

## Stage 2 – Incident Legitimacy

The AI validates incident data:

- Presence of incident date, location, description, and type.
- Impact point identified (Front / Rear / Left / Right / Multiple / Unknown).
- Third-party involvement flag.

Claims without minimum incident data should be set to **Review** with a request for clarification or completion.

---

## Stage 3 – Driver Authorization and Legality

Key checks:

- Driving license:
  - Valid vs expired.
  - Category appropriate for vehicle type.
- Alcohol or substance use:
  - If declared over legal limit or confirmed → critical exclusion.
- Vehicle usage vs policy usage:
  - If vehicle used commercially but policy is private, OD might be excluded.

Critical driver-related breaches normally trigger rejection of OD benefits and possibly other covers as per insurer configuration.

---

## Stage 4 – Incident–Damage Causality

The AI should:

- Use CV results to identify main damage areas and severity.
- Compare incident description and impact point to detected damage.

Examples:

- Reported “rear-end collision”:
  - Expected damaged parts:
    - Rear bumper, trunk, tail lights, rear quarter panels.
- Reported “side impact on driver side”:
  - Expected damaged parts:
    - Driver door, adjacent pillars, fender on that side.

If detected damage is inconsistent with the described incident, the claim should be set to **Review** and a causality inconsistency flag should be recorded.

---

## Stage 5 – Evidence Sufficiency

Evidence sufficiency checks:

- Minimum number of photos present (e.g. at least 6).
- At least one overall view and one close-up of main damage.
- Documents:
  - Estimate present for repairable damage.
  - Police report present for:
    - Theft
    - Serious third-party bodily injury or legal requirements.

If evidence is incomplete but not clearly fraudulent, status should be **Review** with requested follow-ups listed.

---

## Stage 6 – Liability Reference

Simplified global logic:

- If third-party involvement is indicated:
  - Third-party liability coverage (TPL / COMP) may respond.
  - Police report is strongly recommended or mandatory.
- If no third-party involvement:
  - Own damage coverage rules apply (OD / COMP).

The AI does not make a legally binding liability determination but provides a suggested classification based on available data.

---

## Stage 7 – Final Decision Logic

The AI should output a final decision:

- **Approved**
  - All mandatory conditions satisfied.
  - No critical exclusions triggered.
  - Evidence sufficient for a standard claim.

- **Rejected**
  - One or more critical exclusions applied (e.g. policy inactive, known intentional damage, confirmed drunk driving).
  - Reasons must be clearly listed with references to internal rule IDs.

- **Review**
  - Incomplete evidence.
  - Strong inconsistencies that require human judgment.
  - Suspicious patterns that are not definitive enough for automatic rejection.

The assessment output should:

- List all **coverage_applicable** values (OwnDamage, ThirdPartyLiability, Fire, Theft, Glass, None).
- List **excluded_reasons** with concise text explanations.
- Provide **required_followups** for missing or unclear items.
- Assign **fraud_risk_level** (Low / Medium / High) based on separate fraud KB.
- Provide a **damage_summary** with main impact area and severity.
- Provide a **recommendation**:
  - Proceed_With_Claim
  - Reject_Claim
  - Escalate_To_Human

The AI should also provide an **audit_log** referencing rule IDs used in making key decisions.
