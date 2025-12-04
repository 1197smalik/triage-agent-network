# streamlit_app/app.py
import streamlit as st
from streamlit_app.utils.excel_parser import parse_excel_to_df
from streamlit_app.utils.pii_sanitizer import mask_pii_df
from agents.orchestrator_agent import orchestrate_batch
import json

st.set_page_config(page_title="FNOL Intake Assistant (POC)", layout="wide")
st.title("🚗 FNOL Intake Assistant — Streamlit POC (PII masked)")

st.markdown("Upload a synthetic Excel file (sample in /sample_data). The app will mask PII, run validators and produce a synthetic FNOL package per row.")

uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
sample_button = st.button("Load sample data")

if sample_button:
    with open("./sample_data/sample_claims.xlsx", "rb") as f:
        st.download_button("Download sample Excel", f.read(), file_name="sample_claims.xlsx")

if uploaded_file:
    try:
        df = parse_excel_to_df(uploaded_file)
        st.success("Excel parsed")
        st.subheader("Original (display only)")
        st.dataframe(df)

        st.subheader("Sanitized preview (tokens only)")
        masked = mask_pii_df(df)
        st.dataframe(masked)

        if st.button("Process FNOL (batch)"):
            with st.spinner("Running orchestration..."):
                results = orchestrate_batch(masked.to_dict(orient="records"))
            st.success(f"Processed {len(results)} rows")
            for i, r in enumerate(results):
                st.markdown(f"### Row {i} → session_id: `{r['fnol_package']['session_id']}`")
                st.json(r)
            st.download_button("Download results JSON", json.dumps(results, indent=2), file_name="fnol_results.json")
    except Exception as e:
        st.error(f"Failed to process file: {e}")
else:
    st.info("Waiting for Excel upload...")
