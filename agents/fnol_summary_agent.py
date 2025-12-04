# agents/fnol_summary_agent.py
def summarize_fnol(fnol: dict, retrieved: list) -> str:
    # simple templated summary using retrieved doc titles
    docs = ", ".join([d.get("id") for d in retrieved[:2]])
    summary = f"FNOL {fnol['session_id']}: incident at {fnol.get('incident_location','[redacted]')}. Severity {fnol.get('severity_score')}. Coverage: {fnol.get('coverage_indicator')}. Sources: {docs}."
    return summary
