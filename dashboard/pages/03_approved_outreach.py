"""
03_approved_outreach.py — Approved outreach messages dashboard page.

Shows this week's agent-approved retention messages.
Filters by channel, churn reason, and batch date.
Full message viewer per row.
CSV download for campaign execution.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import streamlit as st

from state.queue_store import get_approved_message, get_approved_outreach, get_batch_summary

st.set_page_config(page_title="Approved Outreach — BankRetain", layout="wide")
st.title("Approved Outreach")
st.caption("Agent-approved retention messages ready for campaign execution")

# ── Batch summary ─────────────────────────────────────────────────────────────

try:
    summary_df = get_batch_summary()
except Exception as e:
    st.error(f"Could not load batch summary: {e}")
    st.stop()

if summary_df.empty:
    st.info("No approved outreach yet. Run the agent pipeline first.")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)

with col1:
    batch_dates = ["All"] + sorted(summary_df["batch_date"].astype(str).tolist(), reverse=True)
    selected_date = st.selectbox("Batch date", batch_dates)

with col2:
    channel_filter = st.selectbox("Channel", ["All", "email", "call"])

with col3:
    reason_filter = st.selectbox(
        "Churn reason",
        ["All", "price_sensitivity", "service_dissatisfaction",
         "product_lifecycle", "inactivity", "unknown"],
    )

# ── Load data ─────────────────────────────────────────────────────────────────

try:
    date_arg = None if selected_date == "All" else selected_date
    df = get_approved_outreach(batch_date=date_arg)
except Exception as e:
    st.error(f"Could not load approved outreach: {e}")
    st.stop()

if channel_filter != "All":
    df = df[df["channel"] == channel_filter]
if reason_filter != "All":
    df = df[df["churn_reason"] == reason_filter]

# ── KPI row ───────────────────────────────────────────────────────────────────

st.divider()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total approved", len(df))
k2.metric("Email", len(df[df["channel"] == "email"]) if "channel" in df.columns else 0)
k3.metric("Call scripts", len(df[df["channel"] == "call"]) if "channel" in df.columns else 0)

if "total_tokens" in df.columns and len(df):
    avg_tokens = int(df["total_tokens"].mean())
    k4.metric("Avg tokens / customer", f"{avg_tokens:,}")

st.divider()

if df.empty:
    st.info("No messages match the current filters.")
    st.stop()

# ── Churn reason breakdown ────────────────────────────────────────────────────

if "churn_reason" in df.columns:
    reason_counts = df["churn_reason"].value_counts().reset_index()
    reason_counts.columns = ["churn_reason", "count"]

    import plotly.express as px

    col_chart, col_conf = st.columns(2)
    with col_chart:
        fig = px.bar(
            reason_counts, x="churn_reason", y="count",
            color="churn_reason",
            color_discrete_map={
                "price_sensitivity":      "#3b82f6",
                "service_dissatisfaction": "#ef4444",
                "product_lifecycle":      "#f59e0b",
                "inactivity":             "#8b5cf6",
                "unknown":                "#6b7280",
            },
            labels={"churn_reason": "Churn Reason", "count": "Messages"},
            title="Messages by churn reason",
        )
        fig.update_layout(showlegend=False, height=250, margin=dict(t=40, b=0))
        st.plotly_chart(fig)

    with col_conf:
        if "confidence" in df.columns:
            conf_counts = df["confidence"].value_counts().reset_index()
            conf_counts.columns = ["confidence", "count"]
            fig2 = px.pie(
                conf_counts, values="count", names="confidence",
                color="confidence",
                color_discrete_map={"high": "#22c55e", "medium": "#f59e0b", "low": "#ef4444"},
                title="Agent 1 confidence distribution",
                hole=0.4,
            )
            fig2.update_layout(height=250, margin=dict(t=40, b=0))
            st.plotly_chart(fig2)

# ── Message table ─────────────────────────────────────────────────────────────

st.subheader("Messages")

display_cols = ["customer_id", "batch_date", "offer_id", "channel",
                "churn_reason", "confidence", "message_preview"]
display_cols = [c for c in display_cols if c in df.columns]

st.dataframe(
    df[display_cols].rename(columns={"message_preview": "message (first 500 chars)"}),
    width="stretch",
    height=400,
)

# ── Full message viewer ───────────────────────────────────────────────────────

st.divider()
st.subheader("Full message viewer")

if "customer_id" in df.columns and "batch_date" in df.columns:
    selected_id = st.selectbox(
        "Select customer",
        options=df["customer_id"].tolist(),
        format_func=lambda cid: f"{cid} — {df[df['customer_id']==cid]['churn_reason'].values[0] if len(df[df['customer_id']==cid]) else ''}",
    )

    if selected_id:
        row = df[df["customer_id"] == selected_id].iloc[0]
        batch_date_val = str(row["batch_date"])

        col_meta, col_msg = st.columns([1, 2])
        with col_meta:
            st.markdown(f"**Customer:** {selected_id}")
            st.markdown(f"**Offer:** {row.get('offer_id', '—')}")
            st.markdown(f"**Channel:** {row.get('channel', '—')}")
            st.markdown(f"**Churn reason:** {row.get('churn_reason', '—')}")
            st.markdown(f"**Confidence:** {row.get('confidence', '—')}")
            st.markdown(f"**Batch:** {batch_date_val}")

        with col_msg:
            try:
                full_msg = get_approved_message(selected_id, batch_date_val)
                st.text_area("Full message", value=full_msg or "(not found)", height=350,
                             disabled=True, label_visibility="collapsed")
            except Exception as e:
                st.warning(f"Could not load full message: {e}")

# ── CSV download ──────────────────────────────────────────────────────────────

st.divider()

download_cols = ["customer_id", "batch_date", "offer_id", "channel",
                 "churn_reason", "confidence", "approved_at"]
download_cols = [c for c in download_cols if c in df.columns]

csv_bytes = df[download_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    label=f"Download {len(df)} messages as CSV",
    data=csv_bytes,
    file_name=f"approved_outreach_{selected_date}.csv",
    mime="text/csv",
)
