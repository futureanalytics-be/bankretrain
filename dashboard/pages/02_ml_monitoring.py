"""
02_ml_monitoring.py — ML Model Monitoring dashboard page.

Shows:
  - Current model version in production / staging
  - MLflow experiment run history (precision, recall, F1, AUC per run)
  - Canary split view if active (v1 vs v2 metric comparison)

Drift monitoring: handled in-pipeline (submit_enrichment.py) — no AML
monitor schedule required.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config  # noqa: F401 — bootstraps os.environ from st.secrets on Community Cloud
import streamlit as st
import plotly.express as px
import pandas as pd
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential
import mlflow

st.set_page_config(page_title="ML Monitoring — BankRetain", layout="wide")
st.title("ML Monitoring")
st.caption("Churn model registry and experiment history")


# ── AML client ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _aml_client() -> MLClient:
    return MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
        resource_group_name=os.environ.get("ML_RESOURCE_GROUP", "bankretain-ml-rg"),
        workspace_name=os.environ["AML_WORKSPACE_NAME"],
    )


MODEL_NAME = "bankretain-churn-model"


# ── Model registry ────────────────────────────────────────────────────────────

st.subheader("Model Registry")

try:
    client   = _aml_client()
    versions = list(client.models.list(name=MODEL_NAME))

    if not versions:
        st.info("No registered model versions found. Run the training pipeline first.")
    else:
        registry_rows = []
        for v in sorted(versions, key=lambda x: int(x.version), reverse=True):
            tags   = v.tags or {}
            status = tags.get("status", "unknown")
            registry_rows.append({
                "Version":        v.version,
                "Status":         status,
                "Dataset":        tags.get("dataset_version", "—"),
                "Snapshot Date":  tags.get("snapshot_date", "—"),
                "Precision":      tags.get("precision", "—"),
                "Recall":         tags.get("recall", "—"),
                "F1":             tags.get("f1", "—"),
                "AUC":            tags.get("auc", "—"),
            })

        df_reg = pd.DataFrame(registry_rows)

        def _style_status(val):
            colours = {
                "production": "background-color:#d4edda;color:#155724",
                "staging":    "background-color:#fff3cd;color:#856404",
                "retired":    "background-color:#f8d7da;color:#721c24",
            }
            return colours.get(val, "")

        st.dataframe(
            df_reg.style.applymap(_style_status, subset=["Status"]),
            width="stretch",
            hide_index=True,
        )

        prod_rows    = [r for r in registry_rows if r["Status"] == "production"]
        staging_rows = [r for r in registry_rows if r["Status"] == "staging"]

        col1, col2, col3 = st.columns(3)
        col1.metric("Production Version",
                    prod_rows[0]["Version"] if prod_rows else "—")
        col2.metric("Staging Version",
                    staging_rows[0]["Version"] if staging_rows else "—")
        col3.metric("Total Versions",  len(versions))

except Exception as e:
    st.error(f"Could not load model registry: {e}")
    st.info("Set AZURE_SUBSCRIPTION_ID, AML_WORKSPACE_NAME env vars and re-run.")

st.divider()

# ── Experiment run history ─────────────────────────────────────────────────────

st.subheader("Experiment Run History")

try:
    client  = _aml_client()
    ws      = client.workspaces.get(os.environ["AML_WORKSPACE_NAME"])
    mlflow.set_tracking_uri(ws.mlflow_tracking_uri)

    runs = mlflow.search_runs(
        experiment_names=["bankretain-training"],
        order_by=["start_time DESC"],
        max_results=20,
        output_format="pandas",
    )

    if runs.empty:
        st.info("No experiment runs found. Submit the training pipeline first.")
    else:
        metric_cols = [c for c in runs.columns if c.startswith("metrics.")]
        param_cols  = ["params.dataset_version", "params.snapshot_date",
                       "params.n_estimators", "params.learning_rate"]
        param_cols  = [c for c in param_cols if c in runs.columns]

        display_cols = (
            ["run_id", "status", "start_time"]
            + [c.replace("metrics.", "") for c in metric_cols if any(
                k in c for k in ["precision", "recall", "f1", "auc"]
            )]
        )

        runs_display = runs.copy()
        for col in metric_cols:
            short = col.replace("metrics.", "")
            runs_display[short] = runs_display[col].round(4)

        display_cols_clean = (
            ["run_id", "status", "start_time"] +
            [c.replace("metrics.", "") for c in metric_cols
             if any(k in c for k in ["precision", "recall", "f1", "auc"])]
        )
        display_cols_clean = [c for c in display_cols_clean if c in runs_display.columns]

        st.dataframe(runs_display[display_cols_clean], width="stretch", hide_index=True)

        # Trend chart for key metrics
        metric_keys = [c for c in ["precision", "recall", "f1", "auc"]
                       if c in runs_display.columns]
        if metric_keys:
            runs_display["run_index"] = range(len(runs_display))
            melted = runs_display[["run_index", "start_time"] + metric_keys].melt(
                id_vars=["run_index", "start_time"],
                var_name="Metric", value_name="Value",
            )
            fig = px.line(
                melted, x="run_index", y="Value", color="Metric",
                title="Metric Trend Across Training Runs (newest = leftmost)",
                markers=True,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.add_hline(y=0.75, line_dash="dash", line_color="orange",
                          annotation_text="Precision gate (0.75)")
            fig.update_xaxes(title="Run (0 = most recent)")
            st.plotly_chart(fig)

except Exception as e:
    st.error(f"Could not load experiment runs: {e}")

st.divider()

# ── Canary split view ──────────────────────────────────────────────────────────

st.subheader("Canary Split")

try:
    client   = _aml_client()
    endpoint = client.online_endpoints.get("bankretain-churn-endpoint")
    traffic  = endpoint.traffic or {}

    if not traffic:
        st.info("No active deployments on the endpoint yet.")
    elif len(traffic) == 1:
        dep, pct = next(iter(traffic.items()))
        st.success(f"Single deployment active: **{dep}** at {pct}% traffic (stable)")
    else:
        st.warning("Canary split active — monitor metrics before promoting")
        col_data = [{"Deployment": k, "Traffic %": v} for k, v in traffic.items()]
        st.dataframe(pd.DataFrame(col_data), width="stretch", hide_index=True)

        fig = px.pie(
            pd.DataFrame(col_data),
            names="Deployment", values="Traffic %",
            title="Current Traffic Split",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig)

        st.markdown(
            "To promote the canary to 100%:\n"
            "```bash\n"
            "python ml/registry/promote.py \\\n"
            "  --subscription-id $AZURE_SUBSCRIPTION_ID \\\n"
            "  --workspace-name  $AML_WORKSPACE_NAME\n"
            "```"
        )

except Exception as e:
    st.info(
        f"Endpoint not yet deployed or not accessible: {e}\n\n"
        "Deploy via Bicep (`infra/ml-rg/endpoint.bicep`) first."
    )
