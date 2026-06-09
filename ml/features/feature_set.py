"""
feature_set.py — Register the BankRetain customer churn feature entity and
feature set with the Azure ML managed feature store.

Run once to bootstrap, or re-run to bump the spec version.

Usage:
    python ml/features/feature_set.py \
        --subscription-id <sub-id> \
        --resource-group  bankretain-ml-rg \
        --feature-store   bankretain-fs-dev-<suffix>
"""

import argparse
import os

from azure.ai.ml import MLClient
from azure.ai.ml.entities import FeatureStoreEntity, FeatureSet, FeatureSetSpecification
from azure.identity import DefaultAzureCredential

ENTITY_NAME       = "customer"
ENTITY_VERSION    = "1"
FEATURE_SET_NAME  = "customer_churn_features"
FEATURE_SET_VERSION = "1"
SNAPSHOT_DATE     = "2025-04-01"


def _fs_client(subscription_id: str, resource_group: str, feature_store: str) -> MLClient:
    return MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=feature_store,
    )


def register_entity(client: MLClient) -> None:
    entity = FeatureStoreEntity(
        name=ENTITY_NAME,
        version=ENTITY_VERSION,
        index_columns=[{"name": "customer_id", "type": "string"}],
        description="Bank customer — primary key for churn feature lookup",
        tags={"project": "bankretain"},
    )
    client.feature_store_entities.begin_create_or_update(entity).result()
    print(f"Entity registered: {ENTITY_NAME}:{ENTITY_VERSION}")


def register_feature_set(client: MLClient) -> None:
    spec_path = os.path.join(os.path.dirname(__file__), "feature_spec")
    feature_set = FeatureSet(
        name=FEATURE_SET_NAME,
        version=FEATURE_SET_VERSION,
        description=(
            "10 churn-predictive features derived from SQL transaction, session, "
            "complaint, NPS and product tables — snapshot 2025-04-01 (Population A)"
        ),
        entities=[f"azureml:{ENTITY_NAME}:{ENTITY_VERSION}"],
        specification=FeatureSetSpecification(path=spec_path),
        tags={
            "project":          "bankretain",
            "snapshot_date":    SNAPSHOT_DATE,
            "dataset_version":  "population_a",
            "feature_set_version": FEATURE_SET_VERSION,
        },
    )
    client.feature_sets.begin_create_or_update(feature_set).result()
    print(f"Feature set registered: {FEATURE_SET_NAME}:{FEATURE_SET_VERSION}")


def trigger_materialization(client: MLClient) -> None:
    """
    Kick off offline materialization for the registered feature set.
    This stores the features in the feature store's backing Blob container
    so that training and batch scoring can retrieve a consistent snapshot.
    """
    poller = client.feature_sets.begin_backfill(
        name=FEATURE_SET_NAME,
        version=FEATURE_SET_VERSION,
        feature_window_start_time="2025-04-01T00:00:00Z",
        feature_window_end_time="2025-04-01T23:59:59Z",
    )
    result = poller.result()
    print(f"Materialization job: {result.job_id} — status: {result.status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group",  default="bankretain-ml-rg")
    parser.add_argument("--feature-store",   required=True)
    parser.add_argument("--materialize",     action="store_true",
                        help="Trigger offline materialization after registration")
    args = parser.parse_args()

    client = _fs_client(args.subscription_id, args.resource_group, args.feature_store)
    register_entity(client)
    register_feature_set(client)

    if args.materialize:
        trigger_materialization(client)

    print("Feature store registration complete.")
