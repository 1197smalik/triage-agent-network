# validators.py
import logging
from jsonschema import validate, ValidationError
from typing import Dict, Any, List, Optional
from schemas.claims import validate_claim_assessment_dict

logger = logging.getLogger(__name__)

FNOL_SCHEMA = {
  "type": "object",
  "properties": {
    "session_id": {"type": "string"},
    "incident_time": {"type": "string"},
    "incident_location": {"type": "string"},
    "damage_regions": {"type": "array"},
    "photos": {"type": "array"},
    "severity_score": {"type": "number"},
    "coverage_indicator": {"type": "string"},
    "missing_fields": {"type": "array"},
    "fraud_flags": {"type": "array"},
    "requires_manual_review": {"type": "boolean"},
    "cited_docs": {"type": "array"}
  },
  "required": ["session_id", "incident_time", "damage_regions", "severity_score", "coverage_indicator"]
}

def validate_fnol_schema(fnol_dict):
    try:
        validate(instance=fnol_dict, schema=FNOL_SCHEMA)
        return True, None
    except ValidationError as e:
        logger.warning("FNOL schema validation failed: %s", e)
        return False, str(e)

def run_basic_checks(fnol: dict, claim: dict, retrieved_snips: list, claim_assessment: Optional[Dict[str, Any]] = None):
    issues: List[str] = []
    passed = True
    # incident_time parse
    try:
        if fnol.get("incident_time"):
            from datetime import datetime
            datetime.fromisoformat(fnol["incident_time"])
    except Exception:
        issues.append("incident_time_unparsable")
        passed = False
    # missing fields
    if "incident_description" in claim and not claim["incident_description"]:
        issues.append("missing_description")
        passed = False
    # coverage missing => manual review recommended
    if fnol.get("coverage_indicator") is None:
        issues.append("coverage_missing")
        passed = False
    # schema validation (only for legacy flat FNOL)
    if not any(k in fnol for k in ("incident", "policy", "vehicle")):
        schema_ok, schema_err = validate_fnol_schema(fnol)
        if not schema_ok:
            issues.append(f"schema_error: {schema_err}")
            passed = False
    # claim assessment validation
    if claim_assessment:
        ca_errors = validate_claim_assessment_dict(claim_assessment)
        if ca_errors:
            issues.extend([f"assessment_{e}" for e in ca_errors])
            passed = False
    logger.info("Basic checks completed; passed=%s issues=%s", passed, issues)
    return {"issues": issues, "passed": passed}
