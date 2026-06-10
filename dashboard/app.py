"""
app.py — BankRetain Dashboard entry point.

Run with:
    source sql.env && streamlit run dashboard/app.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from db import query

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
    df = query("""
        SELECT
            SUM(total)      AS total_processed,
            SUM(approved)   AS total_approved,
            SUM(queued)     AS total_queued,
            CAST(SUM(approved) AS FLOAT) / NULLIF(SUM(total), 0) AS pass_rate,
            SUM(tokens)     AS total_tokens
        FROM (
            SELECT COUNT(*) AS total, COUNT(*) AS approved, 0 AS queued,
                   SUM(agent1_tokens + agent2_tokens + agent3_tokens) AS tokens
            FROM dbo.approved_outreach
            UNION ALL
            SELECT COUNT(*), 0, COUNT(*), 0
            FROM dbo.compliance_review_queue
        ) x
    """)
    row = df.iloc[0]
    total     = int(row["total_processed"] or 0)
    approved  = int(row["total_approved"]  or 0)
    queued    = int(row["total_queued"]    or 0)
    pass_rate = float(row["pass_rate"]     or 0)
    tokens    = int(row["total_tokens"]    or 0)
    has_data  = total > 0
except Exception:
    has_data = False

if has_data:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers processed", f"{total:,}")
    c2.metric("Compliance pass rate", f"{pass_rate*100:.1f}%")
    c3.metric("Messages approved", f"{approved:,}")
    c4.metric("Queued for review", f"{queued:,}")
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
                       (gpt-4.1)         (gpt-4.1 +      (gpt-4.1 +
                                          file search)     file search)
                              └────────────────┼────────────────┘
                                               │
                              ┌────────────────┴────────────────┐
                              ▼                                  ▼
                     approved_outreach              compliance_review_queue
                       (Azure SQL)                     (Azure SQL)
                              │
                              ▼
                     Streamlit Dashboard
```
""")

with right:
    st.markdown("**Data & Storage**")
    st.markdown(
        "- Azure SQL (Entra-only auth, Managed Identity)\n"
        "- Azure Blob Storage (batch CSV, feature snapshots)\n"
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
        "- GPT-4.1 — 3-agent sequential pipeline\n"
        "- Vector store file search (products + compliance)\n"
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
    ("3 — Knowledge Stores",       "✅ Complete", "AI Search index populated (61 high-risk profiles); product catalogue and compliance rules uploaded to Foundry vector stores"),
    ("4 — Agent Pipeline",         "✅ Complete", "3-agent pipeline (classify → offer → comply); Azure AI Responses API; 88 % compliance pass rate; results written to Azure SQL"),
    ("5 — Analytics Dashboard",    "✅ Complete", "Streamlit dashboard — 5 pages; compliance pass rate correlations; rule violation heatmap; token cost; canary split view"),
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
