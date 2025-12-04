# streamlit_app/utils/pii_sanitizer.py
import hashlib
import logging

import pandas as pd

logger = logging.getLogger(__name__)

def _tokenize(val: str) -> str:
    if pd.isna(val) or val is None or str(val).strip()=="":
        return ""
    h = hashlib.sha256(str(val).encode()).hexdigest()[:10].upper()
    return f"TOK-{h}"

def mask_pii_df(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    for col in ["claimant_name","car_number","policy_number","incident_location"]:
        if col in df2.columns:
            df2[col] = df2[col].apply(lambda v: _tokenize(v))
            logger.info("Masked PII column: %s", col)
    return df2
