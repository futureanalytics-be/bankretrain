"""
05_pipeline_analytics.py — Pipeline Analytics & Correlation dashboard

Correlates agent pipeline outcomes against customer signals:
  - Compliance pass rate by churn reason
  - Pass rate trend across batches
  - Churn signal count vs pass/fail outcome
  - Rule violation heatmap (rule × churn reason)
  - Token cost by churn reason
  - Channel selection by churn reason
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from blob_store import (
    get_approved_outreach,
    get_review_queue,
    get_batch_summary,
    get_customers,
)

st.set_page_config(page_title="Pipeline Analytics — BankRetain", layout="wide")
st.title("Pipeline Analytics")
st.caption("Compliance pass rates, rule violations, and cost correlated against customer signals")

approved = get_approved_outreach()
queue    = get_review_queue()


# ── 1. Pass rate by churn reason ──────────────────────────────────────────────

st.subheader("Pass rate by churn reason")

if not approved.empty or not queue.empty:
    _a = approved[["churn_reason"]].copy(); _a["src"] = "approved"
    _q = queue[["churn_reason"]].copy();    _q["src"] = "queued"
    combined = pd.concat([_a, _q], ignore_index=True)
    combined = combined[combined["churn_reason"].notna()]

    df_reason = (
        combined.groupby("churn_reason")["src"]
        .agg(total="count", approved=lambda x: (x == "approved").sum())
        .reset_index()
    )
    df_reason["pass_rate"] = df_reason["approved"] / df_reason["total"]
    df_reason["pass_pct"]  = (df_reason["pass_rate"] * 100).round(1)

    fig = px.bar(
        df_reason.sort_values("pass_pct"),
        x="pass_pct", y="churn_reason",
        orientation="h",
        text="pass_pct",
        color="pass_pct",
        color_continuous_scale="RdYlGn",
        range_color=[0, 100],
        labels={"pass_pct": "Pass rate (%)", "churn_reason": "Churn reason"},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(coloraxis_showscale=False, height=max(300, len(df_reason) * 32 + 80))
    st.plotly_chart(fig)
else:
    st.info("No pipeline data yet.")


# ── 2. Pass rate trend by batch ───────────────────────────────────────────────

st.subheader("Compliance pass rate by batch")

df_batch = get_batch_summary()

if not df_batch.empty:
    df_batch = df_batch.copy()
    df_batch["batch_date"] = pd.to_datetime(df_batch["batch_date"])
    df_batch["pass_pct"]   = (df_batch["pass_rate"] * 100).round(1)
    df_batch["total"]      = df_batch["approved_count"] + df_batch["review_count"]
    df_batch = df_batch.sort_values("batch_date")

    col1, col2 = st.columns([2, 1])
    with col1:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df_batch["batch_date"], y=df_batch["pass_pct"],
            mode="lines+markers+text",
            text=df_batch["pass_pct"].astype(str) + "%",
            textposition="top center",
            line=dict(color="#2196F3", width=2),
            marker=dict(size=8),
            name="Pass rate",
        ))
        fig2.update_layout(
            yaxis=dict(range=[0, 105], title="Pass rate (%)"),
            xaxis_title="Batch date",
            height=300,
        )
        st.plotly_chart(fig2)
    with col2:
        st.dataframe(
            df_batch[["batch_date", "approved_count", "review_count", "total", "pass_pct"]]
            .rename(columns={"batch_date": "Batch", "approved_count": "Approved",
                             "review_count": "Queued", "total": "Total", "pass_pct": "Pass %"}),
            hide_index=True, width="stretch",
        )
else:
    st.info("No batch data yet.")


# ── 3. Churn signal count vs outcome ─────────────────────────────────────────

st.subheader("Churn signal count vs compliance outcome")
st.caption("Does higher signal count predict better or worse compliance pass rate?")

customers = get_customers()

if "churn_signal_count" in customers.columns and (not approved.empty or not queue.empty):
    cust_sig = customers[["customer_id", "churn_signal_count"]]

    _ap = approved[["customer_id"]].copy(); _ap["outcome"] = "Pass"
    _qu = queue[["customer_id"]].copy();    _qu["outcome"] = "Fail"
    outcomes = pd.concat([_ap, _qu], ignore_index=True)
    outcomes = outcomes.merge(cust_sig, on="customer_id", how="left")
    outcomes = outcomes[outcomes["churn_signal_count"].notna()]

    df_signals = (
        outcomes.groupby(["churn_signal_count", "outcome"])
        .size().reset_index(name="cnt")
    )

    if not df_signals.empty:
        df_pivot = df_signals.pivot_table(
            index="churn_signal_count", columns="outcome", values="cnt", fill_value=0
        ).reset_index()
        if "Pass" not in df_pivot.columns: df_pivot["Pass"] = 0
        if "Fail" not in df_pivot.columns: df_pivot["Fail"] = 0
        df_pivot["total"]    = df_pivot["Pass"] + df_pivot["Fail"]
        df_pivot["pass_pct"] = (df_pivot["Pass"] / df_pivot["total"] * 100).round(1)

        col1, col2 = st.columns(2)
        with col1:
            fig3 = px.bar(
                df_pivot, x="churn_signal_count", y=["Pass", "Fail"],
                barmode="group",
                color_discrete_map={"Pass": "#4CAF50", "Fail": "#F44336"},
                labels={"churn_signal_count": "Churn signals (count)", "value": "Customers"},
            )
            fig3.update_layout(height=300, legend_title="Outcome")
            st.plotly_chart(fig3)
        with col2:
            fig4 = px.line(
                df_pivot, x="churn_signal_count", y="pass_pct",
                markers=True,
                labels={"churn_signal_count": "Churn signals (count)", "pass_pct": "Pass rate (%)"},
            )
            fig4.update_traces(line_color="#2196F3", marker_size=8)
            fig4.update_layout(yaxis=dict(range=[0, 105]), height=300)
            st.plotly_chart(fig4)
    else:
        st.info("No joined signal data available.")
else:
    st.info("Customer signal data not yet cached — will appear after the next pipeline run.")


# ── 4. Rule violation heatmap ─────────────────────────────────────────────────

st.subheader("Rule violations by churn reason")

df_queue_raw = queue[queue["violated_rules"].notna() & (queue["violated_rules"] != "[]")]

if not df_queue_raw.empty:
    records = []
    for _, row in df_queue_raw.iterrows():
        try:
            rules = json.loads(row["violated_rules"])
            for r in rules:
                rule_id = r.get("rule_id") if isinstance(r, dict) else str(r)
                records.append({"churn_reason": row["churn_reason"], "rule_id": rule_id})
        except (json.JSONDecodeError, TypeError):
            pass

    if records:
        df_rules = pd.DataFrame(records)
        df_heat = (
            df_rules.groupby(["churn_reason", "rule_id"])
            .size().reset_index(name="count")
            .pivot(index="churn_reason", columns="rule_id", values="count")
            .fillna(0).astype(int)
        )
        fig5 = px.imshow(
            df_heat,
            color_continuous_scale="Reds",
            text_auto=True,
            aspect="auto",
            labels={"x": "Rule", "y": "Churn reason", "color": "Violations"},
        )
        fig5.update_layout(height=max(300, len(df_heat) * 40 + 100))
        st.plotly_chart(fig5)
    else:
        st.info("Could not parse rule violations.")
else:
    st.info("No rule violations recorded yet.")


# ── 5. Token cost by churn reason ────────────────────────────────────────────

st.subheader("Avg token cost by churn reason")
st.caption("Approved messages only — total tokens across all 3 agents per customer")

if not approved.empty and "total_tokens" in approved.columns:
    df_tokens = (
        approved[approved["churn_reason"].notna()]
        .groupby("churn_reason")
        .agg(
            customers=("total_tokens", "count"),
            avg_tokens=("total_tokens", "mean"),
            total_tokens=("total_tokens", "sum"),
        )
        .reset_index()
        .sort_values("avg_tokens", ascending=False)
    )
    df_tokens["avg_tokens"] = df_tokens["avg_tokens"].round(0).astype(int)

    col1, col2 = st.columns([2, 1])
    with col1:
        fig6 = px.bar(
            df_tokens.sort_values("avg_tokens"),
            x="avg_tokens", y="churn_reason",
            orientation="h",
            text="avg_tokens",
            color="avg_tokens",
            color_continuous_scale="Blues",
            labels={"avg_tokens": "Avg tokens / customer", "churn_reason": "Churn reason"},
        )
        fig6.update_traces(textposition="outside")
        fig6.update_layout(coloraxis_showscale=False, height=max(300, len(df_tokens) * 32 + 80))
        st.plotly_chart(fig6)
    with col2:
        st.dataframe(
            df_tokens[["churn_reason", "customers", "avg_tokens", "total_tokens"]]
            .rename(columns={"churn_reason": "Churn reason", "customers": "Customers",
                             "avg_tokens": "Avg tokens", "total_tokens": "Total tokens"}),
            hide_index=True, width="stretch",
        )
else:
    st.info("No token data available.")


# ── 6. Channel split by churn reason ─────────────────────────────────────────

st.subheader("Channel selection by churn reason")

if not approved.empty or not queue.empty:
    _a = approved[["churn_reason", "channel"]].copy() if not approved.empty else pd.DataFrame(columns=["churn_reason", "channel"])
    _q = queue[["churn_reason", "channel"]].copy() if not queue.empty else pd.DataFrame(columns=["churn_reason", "channel"])
    df_channel = (
        pd.concat([_a, _q], ignore_index=True)
        .query("churn_reason.notna() and channel.notna()")
        .groupby(["churn_reason", "channel"])
        .size().reset_index(name="cnt")
    )

    if not df_channel.empty:
        df_ch_pivot = df_channel.pivot_table(
            index="churn_reason", columns="channel", values="cnt", fill_value=0
        ).reset_index()

        channels  = [c for c in df_ch_pivot.columns if c != "churn_reason"]
        color_map = {"email": "#2196F3", "call": "#FF9800"}

        fig7 = px.bar(
            df_ch_pivot,
            x="churn_reason", y=channels,
            barmode="stack",
            color_discrete_map=color_map,
            labels={"churn_reason": "Churn reason", "value": "Customers", "variable": "Channel"},
        )
        fig7.update_layout(height=350, xaxis_tickangle=-30)
        st.plotly_chart(fig7)
    else:
        st.info("No channel data available.")
else:
    st.info("No pipeline data yet.")
