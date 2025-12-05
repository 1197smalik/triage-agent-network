# agents/fnol_extraction_agent.py
import logging
import uuid

logger = logging.getLogger(__name__)

def extract_fnol_from_row(row: dict) -> dict:
    # row fields are already masked tokens; we keep that token and use incident_description for NLP
    session_id = "sess-" + uuid.uuid4().hex[:8]
    logger.info("Extracting FNOL from row; session_id=%s", session_id)
    # try to standardize time
    itime = row.get("incident_time")
    try:
        # attempt parse (some Excel formats)
        if isinstance(itime, str):
            itime_iso = itime
        elif itime is None:
            itime_iso = ""
        else:
            itime_iso = itime.isoformat()
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
