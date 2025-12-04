# streamlit_app/utils/validator.py
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def validate_row(row: dict):
    issues = []
    # incident_time parse
    try:
        if row.get("incident_time"):
            datetime.fromisoformat(str(row["incident_time"]))
    except Exception:
        issues.append("incident_time_unparsable")
        logger.warning("incident_time unparsable for row: %s", row.get("incident_time"))
    # required fields
    if not row.get("policy_number"):
        issues.append("missing_policy_number")
        logger.warning("policy_number missing.")
    if not row.get("incident_description"):
        issues.append("missing_description")
        logger.warning("incident_description missing.")
    return issues
