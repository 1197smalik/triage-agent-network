# KB-SOP-FNOL-Global

## Purpose

Define how an AI system should process workshop-submitted FNOL (First Notice of Loss) for motor insurance claims, via email, and convert it into a structured claim request.

This SOP is global and insurer-neutral.

---

## FNOL Source and Channel

- FNOL is raised by an **authorized repair workshop**.
- Submission channel: **registered workshop email** only.
- Each FNOL email should refer to **one vehicle / one incident**.

---

## Required FNOL Content (High-Level)

Minimum structured content:

1. **Workshop details**
   - Workshop ID / code
   - Workshop name
   - Contact email and phone
2. **Policy details**
   - Policy number
   - Insured name (if available)
   - Coverage type if known (TPL / OD / COMP / FT / GC)
3. **Vehicle details**
   - Registration number
   - VIN (if available)
   - Make, model, year
4. **Incident details**
   - Date and time of loss
   - Location of incident
   - Type of incident (Collision / Theft / Fire / Flood / GlassOnly / Vandalism / Other)
   - Brief description of what happened
   - Impact point (Front / Rear / Left / Right / Multiple / Unknown)
   - Third-party involvement (yes / no / unknown)
5. **Evidence and documents**
   - Photos count
   - Estimate attached (yes / no)
   - Police report (where required)
   - Driver license copy
   - RC / registration document

---

## Required Attachments (Workshop)

Minimum recommended:

- Overall vehicle:
  - Front 3/4 view
  - Rear 3/4 view
  - Left side
  - Right side
- Close-ups:
  - Each main damage area (minimum 3 angles per main area)
- Identification:
  - License plate close-up
  - VIN plate (if visible)
  - Odometer reading (for total loss / mileage checks)
- Documents:
  - Repair estimate (PDF or image)
  - Driver license (if available)
  - RC / registration document
  - Police report where legally required

If fewer than 6 distinct vehicle images are present, the system should request additional images.

---

## FNOL Processing Lifecycle (AI System)

1. **Ingestion**
   - Receive FNOL email and attachments.
   - Extract plain text body.
   - Classify email as FNOL vs non-FNOL.

2. **Parsing and Normalization**
   - Parse workshop details, policy number, vehicle number, incident details.
   - Normalize into a structured FNOL JSON object.
   - Count and categorize attachments (vehicle photos, documents).

3. **Validation**
   - Check presence of mandatory core fields (policy id or vehicle id, incident date, description).
   - Check minimal photo requirements.
   - Check whether estimate is attached.
   - Check if incident type suggests a police report is required.

4. **Coverage Pre-check**
   - If policy metadata is available, validate policy period and status.
   - Identify coverage type (TPL / OD / COMP / FT / GC / Unknown).

5. **Damage and Consistency Pre-check**
   - Forward images to computer vision components for damage and part detection.
   - Identify main impact area based on detected damage.
   - Perform a basic narrative vs damage consistency check.

6. **Risk / Fraud Pre-check (Light)**
   - Mark obvious conflicts (e.g. no damage visible, no incident description).
   - Do not auto-reject on weak signals; instead mark for review.

7. **Acknowledgment**
   - Generate a claim reference ID.
   - Send an acknowledgment email to the workshop including:
     - Claim reference ID
     - High-level status (Received / Incomplete)
     - Missing or unclear elements to be supplied, if any.

---

## Escalation Triggers

- No incident date or description.
- Photos missing or less than minimum required views.
- Estimate not attached for repairable damage.
- Theft / third-party / injury indicated without any police report or authority document.
- Severe inconsistencies between narrative and visually detected damage.

Escalation should result in **Review** status, not an automatic rejection.
