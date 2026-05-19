import streamlit as st
import requests
import re
import json
import pandas as pd

st.set_page_config(page_title="Invoice Fraud Detection", layout="wide")

# --- Custom Styling ---
st.markdown("""
    <style>
        .report-box { background: #222; border-radius: 12px; padding: 1.5em; margin-bottom: 1em; box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
        .stMarkdown {font-size: 1.05em;}
        .stButton>button { 
            background-color: #4CAF50 !important; 
            color: white !important; 
            border-radius: 8px; 
            border: 1px solid #4CAF50; 
            font-weight: bold; 
            transition: all 0.2s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stButton>button:hover {
             background-color: #45a049 !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🧾 Multi-Agent Invoice Fraud Detection System")
st.subheader("Upload one or more invoice images for anomaly detection and fraud risk analysis.")

tab1, tab2 = st.tabs(["Upload & Analysis", "Analytics Dashboard"])

with tab1:
    # --- File Uploader ---
    uploaded_files = st.file_uploader(
        "Drag and drop invoice images (.png, .jpg, .jpeg)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

# --- Display function ---
def display_report(uploaded_file, result, label):
    """Displays invoice report and extracted information."""
    risk_json = result.get("report_json", {})

    # --- Risk Section ---
    risk_category = risk_json.get("risk_category", "N/A")
    risk_score = risk_json.get("risk_percentage", 0)

    if risk_category.lower() == "high":
        st.error("🚨 HIGH RISK DETECTED 🚨")
    elif risk_category.lower() == "medium":
        st.warning("⚠️ MEDIUM RISK DETECTED ⚠️")
    else:
        st.success("✅ LOW RISK DETECTED ✅")

    st.markdown(f"**Invoice File:** *{uploaded_file.name}*")

    # --- Visual Metrics ---
    col_metric1, col_metric2 = st.columns([1, 2])

    with col_metric1:
        st.image(uploaded_file, caption=label, width=180)

    with col_metric2:
        st.metric(label="RISK CATEGORY", value=risk_category.upper())
        st.metric(label="RISK SCORE", value=f"{float(risk_score):.1f}%")

    # --- Expandable Section: Extracted Info ---
    with st.expander("🔍 Show Extracted Data & Fraud Flags"):
        st.markdown("**OCR Extracted Fields**")
        st.json(result.get("fields", {}))
        st.markdown("**Fraud Flags (Rule-Based)**")
        st.write(result.get("flags", []))

    # --- Summary of Anomalies & Actions ---
    st.markdown("---")
    st.markdown("### 📝 Summary of Anomalies")

    summary = risk_json.get("summary_of_anomalies", "No anomalies summary available.")
    if summary and isinstance(summary, str) and summary.strip():
        st.markdown(f"- {summary}")
    else:
        st.info("No anomalies summary provided by backend.")

    st.markdown("### ⚠️ Actions Required")

    actions = risk_json.get("action_required", "No specific actions required.")
    if actions and isinstance(actions, str) and actions.strip():
        # Display actions line by line
        for act in re.split(r'[.;]\s+|\n', actions):
            if act.strip():
                st.markdown(f"- {act.strip()}")
    else:
        st.info("No actions provided by backend.")


# --- Main Button Logic ---
with tab1:
    if uploaded_files and st.button("🔍 Analyze Uploaded Invoices"):
        st.markdown("## 📊 Analysis Results")

        cols = st.columns(len(uploaded_files))

        for i, uploaded_file in enumerate(uploaded_files):
            with cols[i]:
                with st.spinner(f"Analyzing Invoice {i+1}... Please wait ⏳"):
                    uploaded_file.seek(0)
                    files = {"file": (uploaded_file.name, uploaded_file.read(), uploaded_file.type)}

                    try:
                        resp = requests.post(
                            "http://127.0.0.1:8000/analyze_invoice",
                            files=files,
                            timeout=120
                        )

                        if resp.status_code == 200:
                            result = resp.json()
                            st.markdown(f"### 🧾 Invoice {i+1} Report")
                            display_report(uploaded_file, result, f"Invoice {i+1}")

                        elif resp.status_code == 400:
                            rejection_message = resp.json().get("detail", "Document rejected: Unknown reason.")
                            st.error(f"Invoice {i+1} rejected ❌")
                            st.warning(rejection_message)

                        else:
                            error_detail = resp.json().get("detail", "Unknown server error.")
                            st.error(f"Invoice {i+1} failed (Error {resp.status_code})")
                            st.exception(error_detail)

                    except requests.exceptions.ConnectionError:
                        st.error(f"❌ Connection failed for Invoice {i+1}. Is FastAPI backend running?")
                    except Exception as e:
                        st.error(f"❌ Invoice {i+1} processing failed: {e}")

with tab2:
    st.markdown("## 📈 Fraud Analytics Dashboard")
    st.markdown("Overview of all historical invoice processing data.")
    
    if st.button("🔄 Refresh Data"):
        st.rerun()

    try:
        resp = requests.get("http://127.0.0.1:8000/stats", timeout=10)
        if resp.status_code == 200:
            stats = resp.json().get("data", {})
            
            # Key Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Invoices", stats.get("total_processed", 0))
            m2.metric("High Risk 🚨", stats.get("high_risk", 0))
            m3.metric("Medium Risk ⚠️", stats.get("medium_risk", 0))
            m4.metric("Low Risk ✅", stats.get("low_risk", 0))
            
            st.markdown("---")
            
            # Charts
            st.markdown("### Risk Distribution")
            chart_data = pd.DataFrame({
                "Risk Category": ["High", "Medium", "Low"],
                "Count": [
                    stats.get("high_risk", 0), 
                    stats.get("medium_risk", 0), 
                    stats.get("low_risk", 0)
                ]
            }).set_index("Risk Category")
            
            st.bar_chart(chart_data, color="#ff4b4b", height=350)
            
        else:
            st.error("Failed to load dashboard statistics.")
    except Exception as e:
        st.error(f"Could not connect to backend to fetch stats: {e}")

st.markdown("---")
st.caption("Powered by Streamlit ⚡ + FastAPI 🚀 + Tesseract OCR 🧠 + Gemini Vision (optional)")
        