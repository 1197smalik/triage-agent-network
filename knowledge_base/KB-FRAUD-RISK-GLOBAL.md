# KB-FRAUD-RISK-GLOBAL

## Purpose

Provide global, evidence-based rules for identifying fraud and anomaly risk signals in motor insurance claims.

This KB does not use blacklists or personal profiling; it is based purely on behaviour and evidence.

---

## Fraud vs Anomaly

- **Fraud risk**: patterns that suggest deliberate misrepresentation or abuse.
- **Anomaly risk**: data or evidence issues that deviate from expectations but may be explainable.

The AI should:

- Assign an overall **fraud_risk_level**: Low / Medium / High.
- Produce a list of **fraud_flags** (short text).
- Never auto-reject solely on weak, metadata-only signals.

---

## Common Fraud / Anomaly Indicators

1. **Narrative vs images inconsistency**
   - Incident description and impact point do not match detected damage.

2. **Repeated claims on the same part**
   - Multiple claims within a short time period for the same vehicle part.

3. **Pre-existing damage mixed into new claim**
   - Visual evidence of rust, old paint, or older damage around the claimed fresh damage.

4. **Policy not active at incident time**
   - Policy expired or suspended on the incident date.

5. **Inflated estimates vs visible damage**
   - Repair estimate amount is significantly higher than typical for the severity indicated by images.

6. **Suspicious metadata patterns**
   - Image capture date far from incident date.
   - Image GPS far from incident location.
   - All EXIF stripped from all photos without obvious reason.

---

## Risk Level Logic (High-Level)

Suggested approach:

- **Low risk**
  - At most one minor flag.
  - No critical policy or driver issues.

- **Medium risk**
  - Multiple moderate anomaly indicators.
  - No confirmed critical exclusion.

- **High risk**
  - Any critical exclusion (policy inactive, confirmed drunk driving, explicit admission).
  - Several strong inconsistencies (narrative vs damage, repeated suspicious claims).

High risk should result in **Review** status or **Rejection** when based on clear critical exclusion.

---

## Integration with Other KBs

- This fraud KB consumes:
  - Consistency flags from evidence/vision KB.
  - Policy state and driver legality checks from coverage and assessment KBs.
  - Claim history where available (recent claims on same part).
- Outputs:
  - `fraud_risk_level`.
  - `fraud_flags`.
  - Entries in the final assessment `audit_log` referencing fraud-related rule IDs.

---

## Behaviour for the AI System

The AI should:

- Prefer **Review** over **Reject** when evidence is incomplete or ambiguous.
- Use **Reject** when:
  - Policy clearly does not apply.
  - Driver or usage breach is a hard exclusion as per coverage rules.
- Clearly communicate fraud-related reasons in a neutral, factual tone for human adjusters.

The intent is to support human decision-makers, not to make unexplainable or opaque automated rejections.
