# KB-COVERAGE-GLOBAL

## Purpose

Define global, insurer-neutral rules for motor insurance coverage types and core exclusions.

---

## Coverage Types

Supported logical coverage types:

- **TPL** – Third-Party Liability Only
  - Covers damage or injury to third parties.
  - Does not cover own vehicle damage.

- **OD** – Own Damage Only
  - Covers damage to insured vehicle from insured perils.
  - Does not cover third-party liability.

- **COMP** – Comprehensive
  - Combines TPL + OD.
  - Often includes broader protection, including some fire, theft, and natural perils.

- **FT** – Fire & Theft Only
  - Covers fire loss and theft loss for the insured vehicle.

- **GC** – Glass Cover Only
  - Covers only glass / windshield damage as configured by policy.

---

## Policy State

Policy-level conditions:

- Policy must be **Active** at the time of the incident.
- Incident date must be **within** the policy start and end dates.
- If policy status is Expired or Suspended at loss date, the claim should be rejected on policy grounds.

---

## Core Coverage Mapping

### Own Damage (OD / COMP)

OD-related events can be covered only if:

- Policy coverage type is **OD** or **COMP**, and
- No exclusion of OD is present at policy level, and
- The driver and vehicle usage are compliant with policy conditions.

Typical OD perils:

- Collision with another vehicle or object.
- Overturning.
- Accidental impact from external causes.

### Third-Party Liability (TPL / COMP)

Third-party liability can be triggered when:

- Coverage type is **TPL** or **COMP**, and
- Third-party involvement is indicated, and
- Incident implies possible damage to another person or property.

---

## Fire / Theft / Natural Disaster

- If coverage type is **FT** or **COMP**, the policy can respond to:
  - Fire
  - Theft
  - Certain specified natural perils (flood, storm, hail etc., depending on insurer configuration).

If coverage type is only **TPL** or **OD**, fire and theft may not be covered unless explicitly added.

---

## Glass Cover

If glass cover is enabled either as:

- coverage type **GC**, or
- an add-on under **COMP / OD**,

then:

- Claims limited to windshield or side windows can be considered under glass cover rules.

---

## Add-ons (Logical Layer)

Common logical add-ons:

- **ZeroDep**
  - Removes or reduces depreciation on replacement parts.

- **EngineProtect**
  - Extends cover to engine damage from water ingress or lubricating oil leakage (e.g. flood situations) subject to conditions.

- **Consumables**
  - Covers consumables (like oils, nuts, bolts) as per policy.

- **Towing**
  - Covers towing or recovery charges up to specified limits.

The presence or absence of an add-on should modify the calculation but not basic eligibility.

---

## Global Exclusions (High-Level)

The following are typical global exclusions:

- Driver under the influence of alcohol or drugs beyond legal limit.
- Driver does not hold a valid and appropriate driving license.
- Vehicle used for a purpose not allowed by the policy:
  - e.g. commercial use when policy specifies private only.
- Participation in racing, speed testing, or illegal activities.
- Deliberate / intentional damage caused by the insured or driver.
- Use of vehicle in excluded geographies if specified by policy.

When a critical exclusion applies, the claim is rejected for the impacted coverage portion. For example:

- Unlicensed driver: OD portion rejected, TPL handling may follow local law and insurer policy.

---

## Conditional Scenarios

Some scenarios require additional checks instead of automatic rejection:

- Late FNOL: FNOL reported with significant delay after the incident. May be allowed when justified (e.g. hospitalization).
- Missing documentation at FNOL: the claim can remain in **Review** state, with follow-up requests for missing documents.

The AI system should distinguish between **hard policy exclusions** and **missing or incomplete information**.
