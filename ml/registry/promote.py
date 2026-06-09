"""
promote.py — Promote a churn model from staging to production

Updates the model registry tag status=staging → status=production for a
given model version, then updates the online endpoint canary split to
route 100% traffic to the new production version.

Triggered manually by the model owner after reviewing canary metrics in
Azure ML Studio, or called from the retrain.yml workflow after approval.

Usage:
    python ml/registry/promote.py \
        --subscription-id <sub-id> \
        --resource-group  bankretain-ml-rg \
        --workspace-name  bankretain-aml-dev-<suffix> \
        --model-version   2 \
        --endpoint-name   bankretain-churn-endpoint
"""

import argparse
import sys

from azure.ai.ml import MLClient
from azure.ai.ml.entities import ManagedOnlineDeployment, ManagedOnlineEndpoint
from azure.identity import DefaultAzureCredential

MODEL_NAME = "bankretain-churn-model"


def _get_client(subscription_id: str, resource_group: str, workspace_name: str) -> MLClient:
    return MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )


def _get_staging_version(client: MLClient) -> str:
    versions = list(client.models.list(name=MODEL_NAME))
    staging  = [v for v in versions if v.tags.get("status") == "staging"]
    if not staging:
        print("No staging model found.")
        sys.exit(1)
    latest = sorted(staging, key=lambda v: int(v.version))[-1]
    return latest.version


def promote(
    client: MLClient,
    model_version: str,
    endpoint_name: str,
) -> None:
    # ── 1. Update model tags: staging → production ────────────────────────────
    model = client.models.get(name=MODEL_NAME, version=model_version)

    # Demote any existing production model first
    existing_prod = [
        v for v in client.models.list(name=MODEL_NAME)
        if v.tags.get("status") == "production" and v.version != model_version
    ]
    for prev in existing_prod:
        prev.tags["status"] = "retired"
        client.models.create_or_update(prev)
        print(f"Retired previous production: version={prev.version}")

    model.tags["status"] = "production"
    client.models.create_or_update(model)
    print(f"Promoted {MODEL_NAME} version={model_version} → production")

    # ── 2. Update endpoint canary split to 100% new version ──────────────────
    deployment_name = f"churn-v{model_version}"
    old_deployment  = f"churn-v{int(model_version) - 1}" if int(model_version) > 1 else None

    try:
        endpoint = client.online_endpoints.get(endpoint_name)
    except Exception:
        print(f"Endpoint {endpoint_name} not found — skipping traffic update.")
        return

    traffic = {deployment_name: 100}
    if old_deployment and old_deployment in endpoint.traffic:
        traffic[old_deployment] = 0

    endpoint.traffic = traffic
    client.online_endpoints.begin_create_or_update(endpoint).result()
    print(f"Endpoint traffic updated: {traffic}")
    print(f"Promotion complete. {MODEL_NAME} v{model_version} is now serving 100% traffic.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", dest="subscription_id", required=True)
    parser.add_argument("--resource-group",  dest="resource_group",  default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",  dest="workspace_name",  required=True)
    parser.add_argument("--model-version",   dest="model_version",   default=None,
                        help="Model version to promote (defaults to latest staging version)")
    parser.add_argument("--endpoint-name",   dest="endpoint_name",
                        default="bankretain-churn-endpoint")
    args = parser.parse_args()

    client = _get_client(args.subscription_id, args.resource_group, args.workspace_name)

    version = args.model_version or _get_staging_version(client)
    print(f"Promoting {MODEL_NAME} version={version} ...")
    promote(client=client, model_version=version, endpoint_name=args.endpoint_name)
