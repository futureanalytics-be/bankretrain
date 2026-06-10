"""
evaluate.py — BankRetain churn model evaluation and registration gate

Reads metrics.json produced by train.py and exits with code 1 (failing the
pipeline) if precision < PRECISION_GATE.  On pass, registers the model in
the AML model registry with status=staging.

Usage (AML command component or local):
    python ml/training/evaluate.py \
        --model-path      ./output/model \
        --subscription-id <sub-id> \
        --workspace-name  bankretain-aml-dev-<suffix> \
        --dataset-version population_a
"""

import argparse
import json
import os
import sys

from azure.ai.ml import MLClient
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Model
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

PRECISION_GATE   = 0.75
MODEL_NAME       = "bankretain-churn-model"
SNAPSHOT_DATE    = "2025-04-01"


def _get_client(subscription_id: str, resource_group: str, workspace_name: str) -> MLClient:
    mi_client_id = os.environ.get("AZURE_CLIENT_ID")
    if mi_client_id:
        cred = ManagedIdentityCredential(client_id=mi_client_id)
    else:
        cred = DefaultAzureCredential()
    return MLClient(cred, subscription_id, resource_group, workspace_name)


def evaluate_and_register(
    model_path: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    dataset_version: str,
) -> None:
    metrics_path = os.path.join(model_path, "metrics.json")
    if not os.path.exists(metrics_path):
        print(f"metrics.json not found at {metrics_path}")
        sys.exit(1)

    with open(metrics_path) as f:
        metrics = json.load(f)

    precision = metrics["precision"]
    print(f"Training precision:   {precision:.4f}")
    print(f"Precision gate:       {PRECISION_GATE}")

    if precision < PRECISION_GATE:
        print(f"\nFAIL — precision {precision:.4f} is below gate {PRECISION_GATE}.")
        print("Pipeline stopped. Investigate training data or hyperparameters.")
        sys.exit(1)

    print(f"\nPASS — registering model as staging ...")

    client = _get_client(subscription_id, resource_group, workspace_name)

    model = Model(
        name=MODEL_NAME,
        path=model_path,
        type=AssetTypes.MLFLOW_MODEL,
        description=(
            f"LightGBM churn model trained on {dataset_version} "
            f"(snapshot {SNAPSHOT_DATE}) — registered by evaluate.py"
        ),
        tags={
            "status":              "staging",
            "dataset_version":     dataset_version,
            "snapshot_date":       SNAPSHOT_DATE,
            "precision":           str(round(precision, 4)),
            "recall":              str(round(metrics.get("recall", 0), 4)),
            "f1":                  str(round(metrics.get("f1", 0), 4)),
            "auc":                 str(round(metrics.get("auc", 0), 4)),
            "feature_set_version": "1",
        },
    )

    registered = client.models.create_or_update(model)
    print(f"Registered: {MODEL_NAME}  version={registered.version}  status=staging")
    print(f"AML model registry version: {registered.version}")

    # Write the registered version to the working dir (model_path is a read-only input mount)
    version_file = os.path.join(os.getcwd(), "registered_version.txt")
    with open(version_file, "w") as f:
        f.write(str(registered.version))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path",       required=True)
    parser.add_argument("--subscription-id",  required=True)
    parser.add_argument("--resource-group",   default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",   required=True)
    parser.add_argument("--dataset-version",  default="population_a")
    args = parser.parse_args()

    evaluate_and_register(
        model_path=args.model_path,
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        workspace_name=args.workspace_name,
        dataset_version=args.dataset_version,
    )
