# streamlit_app/utils/validator.py
from datetime import datetime

def validate_row(row: dict):
    issues = []
    # incident_time parse
    try:
        if row.get("incident_time"):
            datetime.fromisoformat(str(row["incident_time"]))
    except Exception:
        issues.append("incident_time_unparsable")
    # required fields
    if not row.get("policy_number"):
        issues.append("missing_policy_number")
    if not row.get("incident_description"):
        issues.append("missing_description")
    return issues
