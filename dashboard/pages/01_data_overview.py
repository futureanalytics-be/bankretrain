"""
01_data_overview.py — Population A data statistics.

Shows customer counts, churn rates, product distribution,
and key feature distributions pulled live from Azure SQL.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.express as px
from db import query

st.set_page_config(page_title="Data Overview — BankRetain", layout="wide")
st.title("Data Overview")
st.caption("Population A — spring/summer baseline (snapshot: 2025-04-01)")

# ── Summary metrics ──────────────────────────────────────────────────────────

totals = query("""
    SELECT
        COUNT(*)                          AS total_customers,
        SUM(CAST(churned AS INT))         AS churned_count,
        AVG(CAST(churned AS FLOAT)) * 100 AS churn_rate_pct
    FROM dbo.customers
""")

col1, col2, col3 = st.columns(3)
col1.metric("Total Customers",  f"{int(totals['total_customers'][0]):,}")
col2.metric("Churned",          f"{int(totals['churned_count'][0]):,}")
col3.metric("Churn Rate",       f"{totals['churn_rate_pct'][0]:.1f}%")

st.divider()

# ── Customer count by segment and region ─────────────────────────────────────

st.subheader("Customer Distribution")

col_left, col_right = st.columns(2)

with col_left:
    seg_df = query("""
        SELECT segment, COUNT(*) AS customers
        FROM dbo.customers
        GROUP BY segment
        ORDER BY customers DESC
    """)
    fig = px.bar(
        seg_df, x="segment", y="customers",
        title="Customers by Segment",
        color="segment",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(showlegend=False, xaxis_title=None)
    st.plotly_chart(fig)

with col_right:
    region_df = query("""
        SELECT region, COUNT(*) AS customers
        FROM dbo.customers
        GROUP BY region
        ORDER BY customers DESC
    """)
    fig = px.pie(
        region_df, names="region", values="customers",
        title="Customers by Region",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    st.plotly_chart(fig)

st.divider()

# ── Churn rate by segment ─────────────────────────────────────────────────────

st.subheader("Churn Rate by Segment")

churn_seg = query("""
    SELECT
        segment,
        COUNT(*)                          AS total,
        SUM(CAST(churned AS INT))         AS churned,
        AVG(CAST(churned AS FLOAT)) * 100 AS churn_rate_pct
    FROM dbo.customers
    GROUP BY segment
    ORDER BY churn_rate_pct DESC
""")

fig = px.bar(
    churn_seg, x="segment", y="churn_rate_pct",
    title="Churn Rate % by Segment",
    color="churn_rate_pct",
    color_continuous_scale="Reds",
    text=churn_seg["churn_rate_pct"].map("{:.1f}%".format),
)
fig.update_layout(coloraxis_showscale=False, xaxis_title=None, yaxis_title="Churn Rate %")
fig.update_traces(textposition="outside")
st.plotly_chart(fig)

st.divider()

# ── Product distribution ──────────────────────────────────────────────────────

st.subheader("Product Distribution")

prod_df = query("""
    SELECT p.product_type, COUNT(*) AS holdings
    FROM dbo.customer_products cp
    JOIN dbo.products p ON cp.product_id = p.product_id
    WHERE cp.status = 'active'
    GROUP BY p.product_type
    ORDER BY holdings DESC
""")

fig = px.bar(
    prod_df, x="product_type", y="holdings",
    title="Active Product Holdings",
    color="product_type",
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
fig.update_layout(showlegend=False, xaxis_title=None)
st.plotly_chart(fig)

st.divider()

# ── Key feature distributions ─────────────────────────────────────────────────

st.subheader("Key Feature Distributions")

feat_df = query("""
    SELECT
        c.customer_id,
        c.churned,
        DATEDIFF(day, MAX(s.session_date), CAST('2025-04-01' AS DATE)) AS days_since_last_login,
        SUM(CASE WHEN t.is_competitor_transfer = 1
                  AND t.transaction_date >= DATEADD(day, -90, '2025-04-01')
                 THEN 1 ELSE 0 END) AS competitor_transfer_count,
        COUNT(DISTINCT CASE WHEN comp.status = 'open' THEN comp.complaint_id END) AS complaints_open
    FROM dbo.customers c
    LEFT JOIN dbo.app_sessions s  ON c.customer_id = s.customer_id
    LEFT JOIN dbo.transactions t  ON c.customer_id = t.customer_id
    LEFT JOIN dbo.complaints comp ON c.customer_id = comp.customer_id
    GROUP BY c.customer_id, c.churned
""")

col1, col2, col3 = st.columns(3)

with col1:
    fig = px.histogram(
        feat_df, x="days_since_last_login",
        color="churned", barmode="overlay",
        nbins=40,
        title="Days Since Last Login",
        color_discrete_map={0: "#4C9BE8", 1: "#E84C4C"},
        labels={"churned": "Churned"},
        opacity=0.7,
    )
    fig.update_layout(xaxis_title="Days", yaxis_title="Customers")
    st.plotly_chart(fig)

with col2:
    fig = px.histogram(
        feat_df[feat_df["competitor_transfer_count"] <= 20],
        x="competitor_transfer_count",
        color="churned", barmode="overlay",
        nbins=20,
        title="Competitor Transfers (90d)",
        color_discrete_map={0: "#4C9BE8", 1: "#E84C4C"},
        labels={"churned": "Churned"},
        opacity=0.7,
    )
    fig.update_layout(xaxis_title="Transfer Count", yaxis_title="Customers")
    st.plotly_chart(fig)

with col3:
    fig = px.histogram(
        feat_df, x="complaints_open",
        color="churned", barmode="overlay",
        nbins=10,
        title="Open Complaints",
        color_discrete_map={0: "#4C9BE8", 1: "#E84C4C"},
        labels={"churned": "Churned"},
        opacity=0.7,
    )
    fig.update_layout(xaxis_title="Open Complaints", yaxis_title="Customers")
    st.plotly_chart(fig)
