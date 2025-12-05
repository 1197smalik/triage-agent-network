from schemas.claims import (
    fnol_from_row,
    default_claim_assessment,
    validate_claim_assessment_dict,
)


def test_fnol_from_row_maps_fields():
    row = {
        "policy_number": "POL123",
        "car_number": "CAR999",
        "incident_time": "2025-12-01 10:30:00",
        "incident_location": "City Center",
        "incident_description": "Rear end collision",
        "photos": ["a.jpg", "b.jpg"],
        "policy_coverage_type": "COMP",
        "policy_addons": ["ZeroDep"],
    }
    fnol = fnol_from_row(row, "sess-abc")
    data = fnol.to_dict()

    assert data["policy"]["policy_id"] == "POL123"
    assert data["policy"]["coverage_type"] == "COMP"
    assert "ZeroDep" in data["policy"]["addons"]
    assert data["vehicle"]["registration_number"] == "CAR999"
    assert data["incident"]["date"] == "2025-12-01"
    assert data["incident"]["time"] == "10:30:00"
    assert data["incident"]["description"] == "Rear end collision"
    assert data["documents"]["photos_count"] == 2


def test_default_claim_assessment_and_validation():
    ca = default_claim_assessment("sess-xyz").to_dict()
    assert ca["claim_reference_id"] == "sess-xyz"
    errs = validate_claim_assessment_dict(ca)
    assert errs == []

    bad = {"claim_reference_id": "id-only"}
    errs_bad = validate_claim_assessment_dict(bad)
    assert "missing_eligibility" in errs_bad
