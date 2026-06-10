"""
01_data_overview.py — Population A data statistics.

Shows customer counts, churn rates, product distribution,
and key feature distributions read from Azure Blob Storage (Parquet cache).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.express as px
from blob_store import get_customers, get_product_holdings, get_customer_features

st.set_page_config(page_title="Data Overview — BankRetain", layout="wide")
st.title("Data Overview")
st.caption("Population A — spring/summer baseline (snapshot: 2025-04-01)")

customers = get_customers()

# ── Summary metrics ──────────────────────────────────────────────────────────

total    = len(customers)
churned  = int(customers["churned"].sum()) if "churned" in customers.columns else 0
churn_rt = churned / total * 100 if total else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("Total Customers", f"{total:,}")
col2.metric("Churned",         f"{churned:,}")
col3.metric("Churn Rate",      f"{churn_rt:.1f}%")

st.divider()

# ── Customer count by segment and region ─────────────────────────────────────

st.subheader("Customer Distribution")

col_left, col_right = st.columns(2)

with col_left:
    seg_df = (
        customers.groupby("segment", as_index=False)
        .size()
        .rename(columns={"size": "customers"})
        .sort_values("customers", ascending=False)
    )
    fig = px.bar(
        seg_df, x="segment", y="customers",
        title="Customers by Segment",
        color="segment",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(showlegend=False, xaxis_title=None)
    st.plotly_chart(fig)

with col_right:
    region_df = (
        customers.groupby("region", as_index=False)
        .size()
        .rename(columns={"size": "customers"})
        .sort_values("customers", ascending=False)
    )
    fig = px.pie(
        region_df, names="region", values="customers",
        title="Customers by Region",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    st.plotly_chart(fig)

st.divider()

# ── Churn rate by segment ─────────────────────────────────────────────────────

st.subheader("Churn Rate by Segment")

if "churned" in customers.columns:
    churn_seg = (
        customers.groupby("segment")["churned"]
        .agg(total="count", churned="sum")
        .reset_index()
    )
    churn_seg["churn_rate_pct"] = churn_seg["churned"] / churn_seg["total"] * 100
    churn_seg = churn_seg.sort_values("churn_rate_pct", ascending=False)

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
else:
    st.info("Churn labels not available in cache.")

st.divider()

# ── Product distribution ──────────────────────────────────────────────────────

st.subheader("Product Distribution")

try:
    prod_df = get_product_holdings()
    fig = px.bar(
        prod_df.sort_values("holdings", ascending=False),
        x="product_type", y="holdings",
        title="Active Product Holdings",
        color="product_type",
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_layout(showlegend=False, xaxis_title=None)
    st.plotly_chart(fig)
except Exception:
    st.info("Product holdings not yet cached — will appear after the next pipeline run.")

st.divider()

# ── Key feature distributions ─────────────────────────────────────────────────

st.subheader("Key Feature Distributions")

try:
    feat_df = get_customer_features()

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

except Exception:
    st.info("Customer feature distributions not yet cached — will appear after the next pipeline run.")
