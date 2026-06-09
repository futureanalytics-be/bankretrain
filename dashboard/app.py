"""
app.py — BankRetain Dashboard entry point.

Run with:
    source sql.env && streamlit run dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="BankRetain",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("BankRetain — Customer Churn & Retention")
st.markdown(
    """
    AI-103 & AI-300 portfolio project demonstrating an end-to-end churn prediction
    and retention campaign orchestration pipeline on Azure.

    **Use the sidebar to navigate between dashboard pages.**
    """
)

st.divider()

col1, col2, col3 = st.columns(3)
col1.page_link("pages/01_data_overview.py", label="Data Overview", icon="📊")
col2.markdown("🤖 **ML Monitoring** — Phase 2")
col3.markdown("📬 **Approved Outreach** — Phase 4")
