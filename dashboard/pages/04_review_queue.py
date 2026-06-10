"""
04_review_queue.py — Compliance review queue dashboard page (interactive).

Shows messages that failed Agent 3's compliance check.
Per-message actions: Approve with justification / Edit message / Reject.
Write-back via queue_store.py on action.
Audit log: reviewer identity + timestamp + decision recorded.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import pandas as pd
import streamlit as st

from state.queue_store import get_batch_summary, get_queue_message, get_review_queue, update_queue_item

st.set_page_config(page_title="Compliance Review Queue — BankRetain", layout="wide")
st.title("Compliance Review Queue")
st.caption("Messages that failed Agent 3 compliance check — pending human review")

# ── Reviewer identity ─────────────────────────────────────────────────────────

reviewer = st.sidebar.text_input(
    "Reviewer name / email",
    value=st.session_state.get("reviewer", ""),
    help="Your identity is recorded in the audit log for every decision you make.",
)
if reviewer:
    st.session_state["reviewer"] = reviewer

if not reviewer:
    st.warning("Enter your name or email in the sidebar before reviewing messages.")

# ── Filters ───────────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)

try:
    summary_df = get_batch_summary()
except Exception as e:
    st.error(f"Could not connect to database: {e}")
    st.stop()

with col1:
    batch_dates = ["All"] + sorted(summary_df["batch_date"].astype(str).tolist(), reverse=True)
    selected_date = st.selectbox("Batch date", batch_dates)

with col2:
    status_options = ["pending", "approved", "rejected", "All"]
    status_filter  = st.selectbox("Status", status_options)

with col3:
    reason_filter = st.selectbox(
        "Churn reason",
        ["All", "price_sensitivity", "service_dissatisfaction",
         "product_lifecycle", "inactivity", "unknown"],
    )

# ── Load queue ────────────────────────────────────────────────────────────────

try:
    date_arg   = None if selected_date == "All" else selected_date
    status_arg = None if status_filter == "All" else status_filter
    queue_df   = get_review_queue(batch_date=date_arg, status_filter=status_arg)
except Exception as e:
    st.error(f"Could not load review queue: {e}")
    st.stop()

if reason_filter != "All" and "churn_reason" in queue_df.columns:
    queue_df = queue_df[queue_df["churn_reason"] == reason_filter]

# ── KPIs ──────────────────────────────────────────────────────────────────────

st.divider()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total in queue", len(queue_df))
if "status" in queue_df.columns:
    k2.metric("Pending",  len(queue_df[queue_df["status"] == "pending"]))
    k3.metric("Approved", len(queue_df[queue_df["status"] == "approved"]))
    k4.metric("Rejected", len(queue_df[queue_df["status"] == "rejected"]))
st.divider()

if queue_df.empty:
    st.info("No items match the current filters.")
    st.stop()

# ── Violated rules frequency ──────────────────────────────────────────────────

if "violated_rules" in queue_df.columns:
    rule_counts: dict = {}
    for raw in queue_df["violated_rules"].dropna():
        try:
            rules = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(rules, list):
                for r in rules:
                    rid = r.get("rule_id", "unknown") if isinstance(r, dict) else str(r)
                    rule_counts[rid] = rule_counts.get(rid, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    if rule_counts:
        import plotly.express as px

        rule_df = pd.DataFrame(
            sorted(rule_counts.items(), key=lambda x: -x[1]),
            columns=["rule_id", "violations"],
        )
        fig = px.bar(
            rule_df.head(10), x="violations", y="rule_id", orientation="h",
            color="violations", color_continuous_scale="Reds",
            title="Most frequent rule violations (top 10)",
            labels={"violations": "Count", "rule_id": "Rule"},
        )
        fig.update_layout(height=300, margin=dict(t=40, b=0),
                          coloraxis_showscale=False, yaxis={"autorange": "reversed"})
        st.plotly_chart(fig, width="stretch")

# ── Queue table ───────────────────────────────────────────────────────────────

st.subheader("Queue items")

display_cols = ["id", "customer_id", "batch_date", "channel", "churn_reason",
                "violated_rules", "status", "reviewed_by", "created_at"]
display_cols = [c for c in display_cols if c in queue_df.columns]

st.dataframe(queue_df[display_cols], width="stretch", height=350)

# ── Per-message review panel ──────────────────────────────────────────────────

st.divider()
st.subheader("Review a message")

if "id" not in queue_df.columns or queue_df.empty:
    st.info("No items to review.")
    st.stop()

pending = queue_df[queue_df["status"] == "pending"] if "status" in queue_df.columns else queue_df
if pending.empty:
    st.success("All items in the current filter have been reviewed.")
    st.stop()

selected_id = st.selectbox(
    "Select queue item to review",
    options=pending["id"].tolist(),
    format_func=lambda qid: (
        f"#{qid} — {pending[pending['id']==qid]['customer_id'].values[0]} "
        f"({pending[pending['id']==qid]['churn_reason'].values[0] if 'churn_reason' in pending.columns else ''})"
    ),
)

try:
    item = get_queue_message(selected_id)
except Exception as e:
    st.error(f"Could not load message: {e}")
    st.stop()

if not item:
    st.warning("Item not found.")
    st.stop()

# Metadata + violated rules
meta_col, rules_col = st.columns([1, 1])

with meta_col:
    st.markdown(f"**Customer:** {item['customer_id']}")
    st.markdown(f"**Offer:** {item.get('offer_id', '—')}")
    st.markdown(f"**Channel:** {item.get('channel', '—')}")
    st.markdown(f"**Churn reason:** {item.get('churn_reason', '—')}")
    st.markdown(f"**Batch:** {item.get('batch_date', '—')}")
    st.markdown(f"**Current status:** `{item.get('status', '—')}`")
    if item.get("review_notes"):
        st.markdown("**Agent 3 notes:**")
        st.info(item["review_notes"])

with rules_col:
    violated = item.get("violated_rules", [])
    if violated:
        st.markdown("**Violated rules:**")
        for rule in violated:
            if isinstance(rule, dict):
                severity = rule.get("severity", "")
                rule_id  = rule.get("rule_id", "?")
                finding  = rule.get("finding", "")
                colour   = "🔴" if severity == "hard_block" else "🟡"
                st.markdown(f"{colour} **{rule_id}** ({severity}): {finding}")
    else:
        st.success("No rule violations recorded.")

# Message editor
st.markdown("**Message draft:**")
edited_draft = st.text_area(
    "Edit the message below before approving (optional)",
    value=item.get("message_draft", ""),
    height=300,
    key=f"draft_{selected_id}",
)

draft_changed = edited_draft.strip() != (item.get("message_draft") or "").strip()
if draft_changed:
    st.warning("You have edited the message draft. The edited version will be saved on approval.")

# Action buttons
st.divider()
action_col1, action_col2, action_col3 = st.columns(3)

with action_col1:
    if st.button("✅ Approve", type="primary", disabled=not reviewer):
        try:
            update_queue_item(
                selected_id, "approved", reviewer,
                edited_draft=edited_draft if draft_changed else None,
            )
            st.success(f"Approved by {reviewer}. Message moved to approved_outreach.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to approve: {e}")

with action_col2:
    if st.button("✏️ Approve edited draft", disabled=not reviewer or not draft_changed):
        try:
            update_queue_item(selected_id, "approved", reviewer, edited_draft=edited_draft)
            st.success(f"Edited draft approved by {reviewer}.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to approve: {e}")

with action_col3:
    if st.button("❌ Reject", disabled=not reviewer):
        try:
            update_queue_item(selected_id, "rejected", reviewer)
            st.info(f"Rejected by {reviewer}. Message will not be dispatched.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to reject: {e}")

if not reviewer:
    st.caption("Enter your name or email in the sidebar to enable review actions.")
