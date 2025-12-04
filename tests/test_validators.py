from agents.validators import run_basic_checks


def test_run_basic_checks_passes_valid_fnol():
    fnol = {
        "session_id": "sess-1",
        "incident_time": "2025-12-01T10:00:00",
        "incident_location": "City",
        "damage_regions": ["front"],
        "photos": [],
        "severity_score": 0.4,
        "coverage_indicator": "covered",
        "missing_fields": [],
        "fraud_flags": [],
        "requires_manual_review": False,
        "cited_docs": [],
    }
    claim = {"incident_description": "Front bump"}
    result = run_basic_checks(fnol, claim, [], claim_assessment={"claim_reference_id": "x", "eligibility": "Approved", "eligibility_reason": "ok", "fraud_risk_level": "Low", "recommendation": {"action": "Proceed_With_Claim", "notes_for_handler": ""}})
    assert result["passed"] is True
    assert result["issues"] == []


def test_run_basic_checks_flags_missing_incident_time():
    fnol = {
        "session_id": "sess-2",
        "incident_location": "City",
        "damage_regions": ["front"],
        "photos": [],
        "severity_score": 0.4,
        "coverage_indicator": "covered",
        "missing_fields": [],
        "fraud_flags": [],
        "requires_manual_review": False,
        "cited_docs": [],
    }
    claim = {"incident_description": ""}
    result = run_basic_checks(fnol, claim, [], claim_assessment={"claim_reference_id": "x", "eligibility": "Approved", "eligibility_reason": "ok", "fraud_risk_level": "Low", "recommendation": {"action": "Proceed_With_Claim", "notes_for_handler": ""}})
    assert result["passed"] is False
    assert "incident_time_unparsable" in result["issues"] or "coverage_missing" in result["issues"]
