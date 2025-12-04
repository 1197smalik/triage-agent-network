# agents/fnol_validation_agent.py
import logging
from streamlit_app.utils.validator import validate_row

logger = logging.getLogger(__name__)

def validate_fnol_package(fnol: dict, retrieved: list) -> dict:
    # minimal validation: required fields + doc-grounded coverage flag (synthetic)
    issues = validate_row(fnol)
    fnol["missing_fields"] = issues
    # synthetic coverage decision using retrieved docs keywords
    coverage = "unknown"
    for d in retrieved:
        if "collision" in d.get("text","").lower():
            coverage = "likely_in_coverage"
    fnol["coverage_indicator"] = coverage
    fnol["requires_manual_review"] = True if issues or coverage=="unknown" else False
    # add synthetic severity
    desc = fnol.get("incident_description","").lower()
    severity = 0.5
    if "minor" in desc or "scratch" in desc: severity = 0.2
    if "collision" in desc or "airbag" in desc: severity = 0.7
    fnol["severity_score"] = round(severity,2)
    logger.info("Validation agent completed; coverage=%s severity=%.2f issues=%s", coverage, severity, issues)
    return fnol
