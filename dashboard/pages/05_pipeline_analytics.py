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

from db import query

st.set_page_config(page_title="Pipeline Analytics — BankRetain", layout="wide")
st.title("Pipeline Analytics")
st.caption("Compliance pass rates, rule violations, and cost correlated against customer signals")


# ── 1. Pass rate by churn reason ──────────────────────────────────────────────

st.subheader("Pass rate by churn reason")

df_reason = query("""
    SELECT
        churn_reason,
        COUNT(*)                                                        AS total,
        SUM(CASE WHEN src = 'approved' THEN 1 ELSE 0 END)              AS approved,
        CAST(SUM(CASE WHEN src = 'approved' THEN 1 ELSE 0 END) AS FLOAT)
            / NULLIF(COUNT(*), 0)                                       AS pass_rate
    FROM (
        SELECT churn_reason, 'approved' AS src FROM dbo.approved_outreach
        UNION ALL
        SELECT churn_reason, 'queued'   AS src FROM dbo.compliance_review_queue
    ) combined
    WHERE churn_reason IS NOT NULL
    GROUP BY churn_reason
    ORDER BY pass_rate DESC
""")

if not df_reason.empty:
    df_reason["pass_pct"] = (df_reason["pass_rate"] * 100).round(1)
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

df_batch = query("""
    SELECT
        COALESCE(a.batch_date, r.batch_date)        AS batch_date,
        COALESCE(a.approved_count, 0)               AS approved,
        COALESCE(r.review_count,  0)                AS queued,
        CAST(COALESCE(a.approved_count, 0) AS FLOAT)
            / NULLIF(COALESCE(a.approved_count, 0) + COALESCE(r.review_count, 0), 0)
                                                    AS pass_rate
    FROM (
        SELECT batch_date, COUNT(*) AS approved_count
        FROM dbo.approved_outreach GROUP BY batch_date
    ) a
    FULL OUTER JOIN (
        SELECT batch_date, COUNT(*) AS review_count
        FROM dbo.compliance_review_queue GROUP BY batch_date
    ) r ON a.batch_date = r.batch_date
    ORDER BY batch_date
""")

if not df_batch.empty and len(df_batch) > 0:
    df_batch["batch_date"] = pd.to_datetime(df_batch["batch_date"])
    df_batch["pass_pct"]   = (df_batch["pass_rate"] * 100).round(1)
    df_batch["total"]      = df_batch["approved"] + df_batch["queued"]

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
            df_batch[["batch_date", "approved", "queued", "total", "pass_pct"]]
            .rename(columns={"batch_date": "Batch", "approved": "Approved",
                             "queued": "Queued", "total": "Total", "pass_pct": "Pass %"}),
            hide_index=True, width="stretch",
        )
else:
    st.info("No batch data yet.")


# ── 3. Churn signal count vs outcome ─────────────────────────────────────────

st.subheader("Churn signal count vs compliance outcome")
st.caption("Does higher signal count predict better or worse compliance pass rate?")

df_signals = query("""
    SELECT c.churn_signal_count, 'Pass' AS outcome, COUNT(*) AS cnt
    FROM dbo.approved_outreach ao
    JOIN dbo.customers c ON ao.customer_id = c.customer_id
    GROUP BY c.churn_signal_count

    UNION ALL

    SELECT c.churn_signal_count, 'Fail' AS outcome, COUNT(*) AS cnt
    FROM dbo.compliance_review_queue crq
    JOIN dbo.customers c ON crq.customer_id = c.customer_id
    GROUP BY c.churn_signal_count
""")

if not df_signals.empty:
    df_pivot = df_signals.pivot_table(
        index="churn_signal_count", columns="outcome", values="cnt", fill_value=0
    ).reset_index()
    if "Pass" not in df_pivot: df_pivot["Pass"] = 0
    if "Fail" not in df_pivot: df_pivot["Fail"] = 0
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


# ── 4. Rule violation heatmap ─────────────────────────────────────────────────

st.subheader("Rule violations by churn reason")

df_queue_raw = query("""
    SELECT churn_reason, violated_rules
    FROM dbo.compliance_review_queue
    WHERE violated_rules IS NOT NULL AND violated_rules != '[]'
""")

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

df_tokens = query("""
    SELECT
        churn_reason,
        COUNT(*)                                                            AS customers,
        AVG(CAST(agent1_tokens + agent2_tokens + agent3_tokens AS FLOAT))  AS avg_tokens,
        SUM(agent1_tokens + agent2_tokens + agent3_tokens)                 AS total_tokens
    FROM dbo.approved_outreach
    WHERE churn_reason IS NOT NULL
    GROUP BY churn_reason
    ORDER BY avg_tokens DESC
""")

if not df_tokens.empty:
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

df_channel = query("""
    SELECT churn_reason, channel, COUNT(*) AS cnt
    FROM (
        SELECT churn_reason, channel FROM dbo.approved_outreach
        UNION ALL
        SELECT churn_reason, channel FROM dbo.compliance_review_queue
    ) combined
    WHERE churn_reason IS NOT NULL AND channel IS NOT NULL
    GROUP BY churn_reason, channel
""")

if not df_channel.empty:
    df_ch_pivot = df_channel.pivot_table(
        index="churn_reason", columns="channel", values="cnt", fill_value=0
    ).reset_index()

    channels = [c for c in df_ch_pivot.columns if c != "churn_reason"]
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
