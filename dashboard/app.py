"""
app.py — BankRetain Dashboard entry point.

Run with:
    source sql.env && streamlit run dashboard/app.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from blob_store import get_approved_outreach, get_review_queue

st.set_page_config(
    page_title="BankRetain",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("BankRetain — Customer Churn & Retention")
st.markdown(
    "End-to-end churn prediction and AI-driven retention campaign pipeline on Azure. "
    "Built as a portfolio project for **AI-103** (Azure AI Fundamentals) and "
    "**AI-300** (Azure AI Engineer Associate)."
)

st.divider()

# ── Live pipeline metrics ─────────────────────────────────────────────────────

try:
    approved_df = get_approved_outreach()
    queue_df    = get_review_queue()

    total_approved = len(approved_df)
    total_queued   = len(queue_df)
    total          = total_approved + total_queued
    pass_rate      = total_approved / total if total else 0.0
    tokens         = int(approved_df["total_tokens"].sum()) if "total_tokens" in approved_df.columns else 0
    has_data       = total > 0
except Exception:
    has_data = False

if has_data:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers processed",  f"{total:,}")
    c2.metric("Compliance pass rate", f"{pass_rate*100:.1f}%")
    c3.metric("Messages approved",    f"{total_approved:,}")
    c4.metric("Queued for review",    f"{total_queued:,}")
    st.divider()

# ── Architecture ──────────────────────────────────────────────────────────────

st.subheader("Architecture")

left, right = st.columns([3, 2])

with left:
    st.markdown("""
```
Azure SQL (50k synthetic customers)
        │
        ▼
Azure ML Pipeline ──► Feature Store ──► GBM Churn Model
        │                                      │
        ▼                                      ▼
  Batch Scoring                     high_risk_batch.csv
  (submit_batch_score.py)                      │
                                               ▼
                               Azure AI Search (customer profiles)
                                               │
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                          Agent 1          Agent 2          Agent 3
                       Churn Classifier  Offer Selector  Compliance Review
                       (gpt-oss-120b)    (gpt-oss-120b   (gpt-oss-120b +
                                          + inline        inline rules)
                                          catalogue)
                              └────────────────┼────────────────┘
                                               │
                              ┌────────────────┴────────────────┐
                              ▼                                  ▼
                     approved_outreach              compliance_review_queue
                       (Azure SQL)                     (Azure SQL)
                              │                                  │
                              └──────────────┬───────────────────┘
                                             ▼
                                  Azure Blob Storage
                                  (dashboard-cache/
                                   *.parquet — 5 min TTL)
                                             │
                                             ▼
                                  Streamlit Dashboard
```
""")

with right:
    st.markdown("**Data & Storage**")
    st.markdown(
        "- Azure SQL (Entra-only auth, Managed Identity)\n"
        "- Azure Blob Storage (batch CSV, Parquet dashboard cache)\n"
        "- Azure AI Search (customer profile index)\n"
        "- Azure ML Feature Store\n"
    )
    st.markdown("**ML & Training**")
    st.markdown(
        "- Azure Machine Learning (pipeline jobs)\n"
        "- MLflow experiment tracking\n"
        "- GBM churn classifier (precision-gated promotion)\n"
        "- Model registry with canary deployment\n"
    )
    st.markdown("**Agent Orchestration**")
    st.markdown(
        "- Azure AI Foundry (Responses API)\n"
        "- gpt-oss-120b — 3-agent sequential pipeline\n"
        "- Inline product catalogue + compliance rules\n"
        "- Automated compliance hard-block enforcement\n"
    )
    st.markdown("**AIOps & Infrastructure**")
    st.markdown(
        "- Bicep IaC — two resource groups (ml-rg, ai-rg)\n"
        "- GitHub Actions CI/CD (OIDC — no stored secrets)\n"
        "- User-assigned Managed Identity (zero passwords)\n"
        "- Azure Key Vault (Search key, no inline credentials)\n"
    )

st.divider()

# ── Phase status ──────────────────────────────────────────────────────────────

st.subheader("Project phases")

phases = [
    ("1 — Data Foundation",        "✅ Complete", "Synthetic population A (50k) seeded into Azure SQL; Azure ML feature store configured; batch scoring pipeline producing `high_risk_batch.csv`"),
    ("2 — ML Model & Monitoring",  "✅ Complete", "GBM churn model v1 trained (precision ≥ 0.75 gate); registered in AML model registry; MLflow experiment tracking; canary deployment structure in place"),
    ("3 — Knowledge Stores",       "✅ Complete", "AI Search index populated (61 high-risk profiles); product catalogue and compliance rules loaded inline into agent prompts"),
    ("4 — Agent Pipeline",         "✅ Complete", "3-agent pipeline (classify → offer → comply); gpt-oss-120b via Azure AI Foundry; pipeline caches results to Azure Blob as Parquet"),
    ("5 — Analytics Dashboard",    "✅ Complete", "Streamlit dashboard — 5 pages; reads from Blob Storage Parquet cache (no ODBC driver needed); compliance pass rate correlations; rule violation heatmap"),
]

for name, status, description in phases:
    with st.expander(f"**Phase {name}** &nbsp; {status}"):
        st.markdown(description)

st.divider()

# ── Navigation ────────────────────────────────────────────────────────────────

st.subheader("Dashboard pages")

c1, c2, c3 = st.columns(3)
with c1:
    st.page_link("pages/01_data_overview.py",      label="Data Overview",      icon="📊")
    st.caption("Synthetic population stats, churn signal distributions, segment breakdown")
with c2:
    st.page_link("pages/02_ml_monitoring.py",      label="ML Monitoring",      icon="🤖")
    st.caption("Model registry, MLflow experiment run history, canary traffic split")
with c3:
    st.page_link("pages/03_approved_outreach.py",  label="Approved Outreach",  icon="📬")
    st.caption("Approved retention messages — browse, filter, download by offer and channel")

c4, c5, _ = st.columns(3)
with c4:
    st.page_link("pages/04_review_queue.py",       label="Review Queue",       icon="🔍")
    st.caption("Compliance failures — violated rules, review status, human override workflow")
with c5:
    st.page_link("pages/05_pipeline_analytics.py", label="Pipeline Analytics", icon="📈")
    st.caption("Pass rate correlations, rule violation heatmap, token cost by churn reason")
