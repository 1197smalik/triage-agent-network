# agents/fnol_extraction_agent.py
import uuid
from datetime import datetime

def extract_fnol_from_row(row: dict) -> dict:
    # row fields are already masked tokens; we keep that token and use incident_description for NLP
    session_id = "sess-" + uuid.uuid4().hex[:8]
    # try to standardize time
    itime = row.get("incident_time")
    try:
        # attempt parse (some Excel formats)
        itime_iso = str(itime) if isinstance(itime, str) else itime.isoformat()
    except Exception:
        itime_iso = ""
    fnol = {
        "session_id": session_id,
        "policy_number": row.get("policy_number",""),
        "policy_token": row.get("policy_number",""),
        "vehicle_token": row.get("car_number",""),
        "claimant_token": row.get("claimant_name",""),
        "incident_time": itime_iso,
        "incident_description": row.get("incident_description",""),
        "incident_location": row.get("incident_location",""),
        "photos": [],
    }
    return fnol
