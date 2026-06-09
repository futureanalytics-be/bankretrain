"""
alerts.py — Event Grid subscription for AML drift/quality alerts

Wires an Azure Event Grid subscription so that when the Azure ML Model
Monitor fires a drift or precision alert, it calls the GitHub Actions
webhook for the retrain.yml workflow.

The subscription filters on:
  - eventType: Microsoft.MachineLearningServices.RunCompleted
  - subject contains: bankretain-churn-monitor

Prerequisites:
  - drift_monitor.py has been run and the monitor schedule exists
  - A GitHub personal access token (or Actions webhook URL) is stored in
    Key Vault under the secret name 'github-retrain-webhook-url'

Usage:
    python ml/monitoring/alerts.py \
        --subscription-id <sub-id> \
        --resource-group  bankretain-ml-rg \
        --workspace-name  bankretain-aml-dev-<suffix> \
        --keyvault-name   bankretain-kv-ml-<suffix>
"""

import argparse

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.mgmt.eventgrid import EventGridManagementClient
from azure.mgmt.eventgrid.models import (
    EventSubscription,
    EventSubscriptionFilter,
    WebHookEventSubscriptionDestination,
)

MONITOR_NAME          = "bankretain-churn-monitor"
SUBSCRIPTION_NAME     = "bankretain-drift-retrain-trigger"
GITHUB_SECRET_NAME    = "github-retrain-webhook-url"


def _get_webhook_url(keyvault_name: str, cred) -> str:
    kv_url = f"https://{keyvault_name}.vault.azure.net"
    kv_client = SecretClient(vault_url=kv_url, credential=cred)
    secret = kv_client.get_secret(GITHUB_SECRET_NAME)
    return secret.value


def create_event_subscription(
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    webhook_url: str,
) -> None:
    cred = DefaultAzureCredential()
    eg_client = EventGridManagementClient(cred, subscription_id)

    # The AML workspace is the event source
    aml_resource_id = (
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}"
        f"/providers/Microsoft.MachineLearningServices"
        f"/workspaces/{workspace_name}"
    )

    subscription = EventSubscription(
        destination=WebHookEventSubscriptionDestination(
            endpoint_url=webhook_url,
        ),
        filter=EventSubscriptionFilter(
            included_event_types=[
                "Microsoft.MachineLearningServices.RunCompleted",
            ],
            subject_begins_with=f"/schedules/{MONITOR_NAME}",
            is_subject_case_sensitive=False,
        ),
        event_delivery_schema="EventGridSchema",
        retry_policy={
            "max_delivery_attempts": 5,
            "event_time_to_live_in_minutes": 1440,
        },
    )

    poller = eg_client.event_subscriptions.begin_create_or_update(
        scope=aml_resource_id,
        event_subscription_name=SUBSCRIPTION_NAME,
        event_subscription_info=subscription,
    )
    result = poller.result()
    print(f"Event Grid subscription created: {result.name}")
    print(f"  Source:      {aml_resource_id}")
    print(f"  Filter:      subject starts with /schedules/{MONITOR_NAME}")
    print(f"  Destination: GitHub Actions webhook (retrain.yml)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", dest="subscription_id", required=True)
    parser.add_argument("--resource-group",  dest="resource_group",  default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",  dest="workspace_name",  required=True)
    parser.add_argument("--keyvault-name",   dest="keyvault_name",   required=True)
    args = parser.parse_args()

    cred = DefaultAzureCredential()
    webhook_url = _get_webhook_url(args.keyvault_name, cred)
    create_event_subscription(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        workspace_name=args.workspace_name,
        webhook_url=webhook_url,
    )
