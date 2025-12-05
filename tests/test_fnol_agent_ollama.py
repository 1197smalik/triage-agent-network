import json

from agents import fnol_agent_ollama


def test_generate_fnol_ollama_uses_mock_llm(monkeypatch):
    sanitized_row = {
        "policy_number": "POL123",
        "car_number": "CAR999",
        "claimant_name": "TOK-123",
        "incident_time": "2025-12-01 10:30:00",
        "incident_description": "Front collision minor",
        "incident_location": "City Center",
        "photos": [],
    }

    def fake_call(system, user_prompt, model=None, max_tokens=None):
        # return JSON with both fnol_package and claim_assessment
        payload = {
            "fnol_package": {
                "session_id": "sess-mock",
                "incident_time": "2025-12-01T10:30:00",
                "incident_location": "City Center",
                "damage_regions": ["front"],
                "photos": [],
                "severity_score": 0.3,
                "coverage_indicator": True,
                "missing_fields": [],
                "fraud_flags": [],
                "requires_manual_review": False,
                "cited_docs": [],
            },
            "claim_assessment": {
                "claim_reference_id": "sess-mock",
                "eligibility": "Approved",
                "eligibility_reason": "All good",
                "coverage_applicable": ["OwnDamage"],
                "excluded_reasons": [],
                "required_followups": [],
                "fraud_risk_level": "Low",
                "fraud_flags": [],
                "damage_summary": {"main_impact_area": "Front", "severity": "Moderate", "damaged_parts": []},
                "recommendation": {"action": "Proceed_With_Claim", "notes_for_handler": ""},
                "audit_log": []
            },
            "summary": "ok",
            "confidence": 0.9,
        }
        return json.dumps(payload), {"provider": "fake"}

    def fake_rules(fnol_obj, top_k=20):
        return [{"id": "rule1", "text": "sample rule", "meta": {}, "score": 1.0}]

    monkeypatch.setattr(fnol_agent_ollama, "call_ollama_chat", fake_call)
    monkeypatch.setattr(fnol_agent_ollama, "retrieve_rules_for_fnol", fake_rules)

    result = fnol_agent_ollama.generate_fnol_ollama(sanitized_row)
    assert "fnol_package" in result
    assert result["fnol_package"]["incident_time"]
    # coverage_indicator should be normalized to string
    assert isinstance(result["fnol_package"]["coverage_indicator"], str)
    assert result["claim_assessment"]["claim_reference_id"]
    assert result["verification"]["passed"] in (True, False)


def test_generate_fnol_backfills_missing_assessment(monkeypatch):
    sanitized_row = {
        "policy_number": "POL123",
        "car_number": "CAR999",
        "incident_time": "2025-12-01 10:30:00",
        "incident_description": "Front collision minor",
        "incident_location": "City Center",
        "photos": [],
    }

    def fake_call(system, user_prompt, model=None, max_tokens=None):
        payload = {
            "fnol_package": {"session_id": "sess-mock2", "incident_time": "2025-12-01T10:30:00"},
            "claim_assessment": {},
            "summary": "ok",
            "confidence": 0.9,
        }
        return json.dumps(payload), {"provider": "fake"}

    def fake_rules(fnol_obj, top_k=12):
        return [{"id": "rule1", "text": "sample rule", "meta": {}, "score": 1.0}]

    monkeypatch.setattr(fnol_agent_ollama, "call_ollama_chat", fake_call)
    monkeypatch.setattr(fnol_agent_ollama, "retrieve_rules_for_fnol", fake_rules)

    result = fnol_agent_ollama.generate_fnol_ollama(sanitized_row)
    ca = result["claim_assessment"]
    assert ca["claim_reference_id"]
    assert ca["fraud_risk_level"]
    assert ca["recommendation"]["action"]
