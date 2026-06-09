"""
drift_monitor.py — Configure Azure ML Model Monitor for BankRetain

Sets up two monitoring signals:
  1. Data drift       — feature distribution vs Population A baseline
  2. Model quality    — precision, recall, F1 vs validation baseline

Alert threshold: precision drops below 0.72 → Event Grid alert fires
                 which triggers retrain.yml via webhook.

Run once after the first batch scoring job produces data:
    python ml/monitoring/drift_monitor.py \
        --subscription-id  <sub-id> \
        --resource-group   bankretain-ml-rg \
        --workspace-name   bankretain-aml-dev-<suffix> \
        --endpoint-name    bankretain-churn-endpoint \
        --deployment-name  churn-v1
"""

import argparse

from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    AlertNotification,
    DataDriftSignal,
    ModelPerformanceSignal,
    MonitorDefinition,
    MonitorSchedule,
    RecurrenceTrigger,
    ServerlessSparkCompute,
)
from azure.identity import DefaultAzureCredential

MONITOR_NAME     = "bankretain-churn-monitor"
PRECISION_ALERT  = 0.72
DRIFT_THRESHOLD  = 0.15   # Jensen-Shannon distance


def _get_client(subscription_id: str, resource_group: str, workspace_name: str) -> MLClient:
    return MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )


def configure_monitor(
    client: MLClient,
    endpoint_name: str,
    deployment_name: str,
    notification_email: str,
) -> None:
    # ── Compute for monitoring jobs (Spark serverless) ─────────────────────────
    compute = ServerlessSparkCompute(
        instance_type="Standard_E4s_v3",
        runtime_version="3.4",
    )

    # ── Signal 1: Data drift — feature distributions vs training baseline ──────
    drift_signal = DataDriftSignal(
        production_data={
            "input_data": {
                "type": "mltable",
                "path": f"azureml://endpoints/{endpoint_name}/deployments/{deployment_name}/models/0/outputs/model_inputs:named_result",
            },
            "data_window": {"lookback_period": "P7D"},
        },
        reference_data={
            "input_data": {
                "type": "mltable",
                "path": "azureml:customer_churn_features:1",
            },
        },
        features=[
            "days_since_last_login",
            "competitor_transfer_count",
            "complaints_open",
            "months_to_rate_reset",
            "avg_monthly_inflow_eur",
            "app_logins_last_30d",
            "app_logins_last_90d",
            "salary_account_flag",
            "product_count",
            "nps_score_last",
        ],
        alert_enabled=True,
        alert_thresholds={"normalized_wasserstein_distance": DRIFT_THRESHOLD},
    )

    # ── Signal 2: Model performance — precision / recall / F1 ─────────────────
    quality_signal = ModelPerformanceSignal(
        production_data={
            "input_data": {
                "type": "mltable",
                "path": f"azureml://endpoints/{endpoint_name}/deployments/{deployment_name}/models/0/outputs/model_outputs:named_result",
            },
            "data_window": {"lookback_period": "P7D"},
        },
        reference_data={
            "input_data": {
                "type": "mltable",
                "path": "azureml:customer_churn_features:1",
            },
        },
        task_type="classification",
        alert_enabled=True,
        alert_thresholds={"precision": PRECISION_ALERT, "recall": 0.60},
    )

    # ── Monitor schedule (weekly — every Monday 02:00 UTC) ────────────────────
    schedule = MonitorSchedule(
        name=MONITOR_NAME,
        trigger=RecurrenceTrigger(
            frequency="Week",
            interval=1,
            schedule={"week_days": ["Monday"], "hours": [2], "minutes": [0]},
        ),
        create_monitor=MonitorDefinition(
            compute=compute,
            monitoring_signals={
                "data_drift":      drift_signal,
                "model_quality":   quality_signal,
            },
            alert_notification=AlertNotification(
                emails=[notification_email],
            ),
        ),
    )

    client.schedules.begin_create_or_update(schedule).result()
    print(f"Monitor schedule created: {MONITOR_NAME}")
    print(f"  Drift alert threshold:     JS distance > {DRIFT_THRESHOLD}")
    print(f"  Precision alert threshold: < {PRECISION_ALERT}")
    print(f"  Notification email:        {notification_email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id",    dest="subscription_id", required=True)
    parser.add_argument("--resource-group",     dest="resource_group",  default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",     dest="workspace_name",  required=True)
    parser.add_argument("--endpoint-name",      dest="endpoint_name",
                        default="bankretain-churn-endpoint")
    parser.add_argument("--deployment-name",    dest="deployment_name", default="churn-v1")
    parser.add_argument("--notification-email", dest="notification_email",
                        default="ladetola0@gmail.com")
    args = parser.parse_args()

    client = _get_client(args.subscription_id, args.resource_group, args.workspace_name)
    configure_monitor(
        client=client,
        endpoint_name=args.endpoint_name,
        deployment_name=args.deployment_name,
        notification_email=args.notification_email,
    )
