# streamlit_app/app.py
import json
import logging

import streamlit as st

from streamlit_app.utils.excel_parser import parse_excel_to_df
from streamlit_app.utils.pii_sanitizer import mask_pii_df
from agents.orchestrator_agent import orchestrate_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)
from agents.fnol_agent_ollama import generate_fnol_ollama
import traceback

st.set_page_config(page_title="FNOL Intake Assistant (POC)", layout="wide")
st.title("🚗 FNOL Intake Assistant — Streamlit POC (PII masked)")

st.markdown("Upload a synthetic Excel file (sample in /sample_data). The app will mask PII, run validators and produce a synthetic FNOL package per row.")

uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
sample_button = st.button("Load sample data")

if sample_button:
    logger.info("Sample data button clicked; preparing download.")
    with open("./sample_data/sample_claims.xlsx", "rb") as f:
        st.download_button("Download sample Excel", f.read(), file_name="sample_claims.xlsx")

if uploaded_file:
    try:
        logger.info("Uploaded file received: %s", uploaded_file.name)
        df = parse_excel_to_df(uploaded_file)
        logger.info("Excel parsed to dataframe with %d rows.", len(df))
        st.success("Excel parsed")
        st.subheader("Original (display only)")
        st.dataframe(df)

        st.subheader("Sanitized preview (tokens only)")
        masked = mask_pii_df(df)
        logger.info("PII masked; proceeding to preview and processing.")
        st.dataframe(masked)

        if st.button("Process FNOL (Ollama)"):
            logger.info("FNOL processing triggered via Ollama.")
            rows = masked.to_dict(orient="records")
            total = len(rows)
            progress = st.progress(0, text=f"Processing 0/{total}")
            status_box = st.empty()
            results_container = st.container()
            results = []

            for idx, r in enumerate(rows):
                logger.info("Processing row %d for session build.", idx)
                status_box.info(f"Processing row {idx+1} of {total}...")
                out = generate_fnol_ollama(r)
                results.append(out)

                # update UI incrementally
                with results_container:
                    if "fnol_package" in out:
                        sid = out["fnol_package"].get("session_id", "n/a")
                        st.markdown(f"### Row {idx} — session {sid}")
                        st.json(out)
                    else:
                        sid = out.get("session_id", "n/a")
                        st.markdown(f"### Row {idx} — error (session {sid})")
                        st.warning(out.get("error", "Unknown error"))
                        st.json(out)
                progress.progress((idx + 1) / total, text=f"Processing {idx+1}/{total}")

            logger.info("FNOL processing complete; %d rows.", len(results))
            st.session_state["fnol_results"] = results
            st.success("Processed via Ollama")
            st.download_button("Download results JSON", json.dumps(results, indent=2), file_name="fnol_results.json")
    except Exception as e:
        logger.exception("Failed to process file via Streamlit app.")
        st.error("⚠️ Failed to process file. Full traceback below:")
        st.code(traceback.format_exc())
else:
    st.info("Waiting for Excel upload...")
