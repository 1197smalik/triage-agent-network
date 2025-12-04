# streamlit_app/app.py
import json
import logging
import base64
from schemas.claims import default_claim_assessment

import streamlit as st

from streamlit_app.utils.excel_parser import parse_excel_to_df
from streamlit_app.utils.pii_sanitizer import mask_pii_df
from streamlit_app.utils.validator import assign_policy_tags
from datetime import datetime, date


def _json_default(o):
    try:
        import pandas as pd
    except Exception:
        pd = None
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if pd and isinstance(o, pd.Timestamp):
        return o.isoformat()
    return str(o)
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
        masked = assign_policy_tags(masked)
        logger.info("PII masked; proceeding to preview and processing.")
        st.dataframe(masked)

        if st.button("Process FNOL (Ollama)"):
            logger.info("FNOL processing triggered via Ollama.")
            rows = masked.to_dict(orient="records")
            total = len(rows)
            progress = st.progress(0, text=f"Processed 0/{total}")
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
                    fnol_data = out.get("fnol_package") or {}
                    if fnol_data:
                        sid = fnol_data.get("session_id", "n/a")
                        ca = out.get("claim_assessment") or default_claim_assessment(sid).to_dict()
                        claim_ref = ca.get("claim_reference_id", sid)
                        eligibility = ca.get("eligibility", "?")
                        fraud_risk = ca.get("fraud_risk_level", "?")
                        severity_val = (ca.get("damage_summary") or {}).get("severity", "")
                        severity = severity_val.lower() if isinstance(severity_val, str) else ""
                        color_map = {
                            "high": "red",
                            "severe": "red",
                            "medium": "darkorange",
                            "moderate": "darkorange",
                            "low": "gold"
                        }
                        sev_color = color_map.get(severity, "inherit")
                        severity_text = f"<span style='color:{sev_color}; font-weight:600'>{severity.title() if severity else 'Unknown'}</span>"

                        process_ready = (
                            ca.get("eligibility") == "Approved"
                            and not ca.get("required_followups")
                            and not fnol_data.get("requires_manual_review")
                            and out.get("verification", {}).get("passed", False)
                        )

                        summary_label = f"Row {idx} — Ref {claim_ref} | Eligibility: {eligibility} | Fraud: {fraud_risk} | Severity: {severity.title() if severity else 'Unknown'}"
                        row_container = st.container()
                        if process_ready:
                            row_container.markdown("<div style='background-color:#e8f5e9; padding:8px; border-radius:6px;'>", unsafe_allow_html=True)
                        with row_container.expander(summary_label, expanded=False):
                            st.markdown(f"Severity: {severity_text}", unsafe_allow_html=True)
                            def _stringify_list(val):
                                if not val:
                                    return ["None"]
                                if isinstance(val, (str, bool)):
                                    return [str(val)]
                                try:
                                    return [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in val]
                                except TypeError:
                                    return [str(val)]
                            st.write(f"Required followups: {', '.join(_stringify_list(ca.get('required_followups')))}")
                            st.write(f"Fraud flags: {', '.join(_stringify_list(ca.get('fraud_flags')))}")
                            st.write(f"Coverage applicable: {', '.join(_stringify_list(ca.get('coverage_applicable')))}")
                            st.write(f"Excluded reasons: {', '.join(_stringify_list(ca.get('excluded_reasons')))}")
                            st.write(f"Recommendation: {ca.get('recommendation', {}).get('action', 'n/a')} — {ca.get('recommendation', {}).get('notes_for_handler', '')}")
                            # FNOL JSON link
                            json_str = json.dumps(out, indent=2)
                            b64 = base64.b64encode(json_str.encode()).decode()
                            href = f'<a href="data:application/json;base64,{b64}" target="_blank" rel="noopener">View FNOL JSON</a>'
                            st.markdown(href, unsafe_allow_html=True)
                            # Show JSON inline without interrupting processing
                            st.json(out)
                        if process_ready:
                            row_container.markdown("</div>", unsafe_allow_html=True)
                    else:
                        sid = out.get("session_id", "n/a")
                        st.markdown(f"### Row {idx} — error (session {sid})")
                        st.warning(out.get("error", "Unknown error"))
                        st.json(out)
                progress.progress((idx + 1) / total, text=f"Processing {idx+1}/{total}")

            logger.info("FNOL processing complete; %d rows.", len(results))
            st.session_state["fnol_results"] = results
            st.success("Processed via Ollama")
            st.download_button("Download results JSON", json.dumps(results, indent=2, default=_json_default), file_name="fnol_results.json")
    except Exception as e:
        logger.exception("Failed to process file via Streamlit app.")
        st.error("⚠️ Failed to process file. Full traceback below:")
        st.code(traceback.format_exc())
else:
    st.info("Waiting for Excel upload...")
