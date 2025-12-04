# KB-EVIDENCE-VISION-GLOBAL

## Purpose

Define requirements and reasoning rules for image-based evidence and computer vision (CV) outputs used in motor claim assessment.

This KB assumes self-hosted open-source CV models (e.g. object detection, segmentation, OCR).

---

## Required Image Set from Workshop

Minimum recommended images:

1. **Overall views**
   - Front 3/4 view.
   - Rear 3/4 view.
   - Left side view.
   - Right side view.
2. **Close-ups of damage**
   - Each main impact zone: at least 3 angles.
3. **Identification images**
   - License plate close-up.
   - VIN plate close-up (where possible).
   - Odometer reading (for total loss / mileage considerations).
4. **Documents (optional via images)**
   - Estimate photo.
   - RC / registration document.
   - Driver license.
   - Police report.

If fewer than 6 distinct vehicle images are available, the AI system should request additional images.

---

## Vision Tasks (Logical)

The CV stack should support at least:

1. **Damage region detection**
   - Detect damaged regions and associate them with standard part labels:
     - Front_Bumper, Rear_Bumper, Door_FL, Door_FR, Door_RL, Door_RR, Hood, Trunk, Roof, Fender_FL, Fender_FR, etc.

2. **Damage type and severity (if feasible)**
   - Damage types: scratch, dent, crack, deformation, shatter, missing.
   - Severity: minor, moderate, severe.

3. **Identification extraction**
   - OCR for license plate.
   - OCR for VIN tag where visible.
   - OCR for odometer reading.

4. **Incident consistency support**
   - Provide a structured list of damaged parts and their sides (front/rear/left/right) to help the LLM check consistency with incident descriptions.

5. **Metadata / EXIF reading (when available)**
   - Capture date/time.
   - GPS coordinates.
   - Basic camera metadata.

---

## Narrative vs Image Consistency

The AI should compare:

- Incident impact point (Front / Rear / Left / Right / Multiple / Unknown).
- Incident type (Collision / GlassOnly / etc.).
- Detected main damaged parts from CV.

Examples:

- If impact point is **Rear**:
  - Expected damage: rear bumper, trunk, tail lights, rear quarter panels.
- If incident type is **GlassOnly**:
  - Damage should be confined to windshield or window glass.

If damage is concentrated only on the front but the narrative states a pure rear impact, this is an inconsistency and should be flagged for review.

---

## EXIF and Metadata Checks

Metadata-based checks are **soft fraud signals**, not hard rejections:

- If image capture date is much later than the incident date:
  - Mark as suspicious and include in risk analysis.
- If GPS coordinates do not match incident location meaningfully:
  - Mark as suspicious if the difference is large.
- If all EXIF is stripped:
  - Record as a weak signal. Do not auto-reject.

---

## Pre-existing Damage Signals

The AI should treat some visual patterns as indicators of possible pre-existing damage:

- Old rust around the damaged area.
- Faded or multiple layers of paint around impact.
- Multiple unrelated damage clusters (e.g. front and rear) that are not explained by a single incident.

These signals should not always cause rejection, but they can:

- Lead to **Review** status.
- Suggest that only a subset of damage should be treated as new.

---

## Minimal CV Result Schema (Logical)

CV outputs consumed by the LLM should at least provide:

- `damaged_parts`:
  - Part name (standardized).
  - Damage type.
  - Severity.
- `license_plate_ocr`:
  - Text or null.
- `vin_ocr`:
  - Text or null.
- `odometer_ocr`:
  - Numeric reading or null.
- `preexisting_damage_signals`:
  - List of short text flags.

The LLM will use these to:

- Support causality checks.
- Validate identification.
- Infer main impact area and severity.

---

## Evidence Sufficiency Logic (Images)

The AI should:

- Mark FNOL as incomplete if:
  - Fewer than 6 vehicle images.
  - No clear damage close-up is available.
  - No image shows the license plate when needed for identification.

Incompleteness should lead to:

- Status: **Review**.
- A clear list of requested additional images in the output.

---

## Interaction with Fraud and Assessment KBs

- Consistency issues between narrative and images should set a flag consumed by the fraud KB.
- Evidence sufficiency results feed into the assessment KB for:
  - Review vs Approved decision.
  - Additional information requests in the FNOL acknowledgment or follow-up.
