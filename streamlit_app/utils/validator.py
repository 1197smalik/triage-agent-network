# streamlit_app/utils/validator.py
import logging
import random
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


def assign_policy_tags(df):
    """
    Randomly tag policies to emulate KB-based coverage categories:
      - Thirdparty (TPL) with no add-ons
      - Comprehensive without add-ons
      - Comprehensive with ZeroDep add-on
    """
    options = [
        {"coverage_type": "TPL", "addons": []},
        {"coverage_type": "COMP", "addons": []},
        {"coverage_type": "COMP", "addons": ["ZeroDep"]},
    ]
    df2 = df.copy()
    tags = []
    for _ in range(len(df2)):
        tags.append(random.choice(options))
    df2["policy_coverage_type"] = [t["coverage_type"] for t in tags]
    df2["policy_addons"] = [t["addons"] for t in tags]
    logger.info("Assigned random policy tags to %d rows.", len(df2))
    return df2
