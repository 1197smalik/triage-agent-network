# streamlit_app/utils/excel_parser.py
import logging
from io import BytesIO

import pandas as pd

logger = logging.getLogger(__name__)

def parse_excel_to_df(uploaded_file) -> pd.DataFrame:
    # uploaded_file is an UploadedFile from Streamlit
    df = pd.read_excel(BytesIO(uploaded_file.read()), engine='openpyxl')
    # normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    # ensure expected columns exist - fill missing with empty strings
    expected = ["claimant_name","car_number","policy_number","incident_time","incident_description","incident_location"]
    for c in expected:
        if c not in df.columns:
            df[c] = ""
            logger.warning("Missing expected column '%s' in upload; defaulting to empty.", c)
    logger.info("Parsed Excel with normalized columns: %s", list(df.columns))
    return df[expected]
