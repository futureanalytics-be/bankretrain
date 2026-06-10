"""
pipeline.py — BankRetain AML training pipeline orchestrator

Defines and submits a three-step AML pipeline:
  1. feature_extraction — SQL → parquet (uses feature pipeline MI)
  2. train             — LightGBM training + MLflow logging
  3. evaluate          — precision gate + model registry write

Run after the feature store registration (feature_set.py) and before
starting Phase 2.3 (online endpoint + batch scoring).

Usage:
    python ml/training/pipeline.py \
        --subscription-id  <sub-id> \
        --resource-group   bankretain-ml-rg \
        --workspace-name   bankretain-aml-dev-<suffix> \
        --sql-server       bankretain-sql-dev-<suffix>.database.windows.net \
        --mi-client-id     <feature-pipeline-mi-client-id> \
        --snapshot-date    2025-04-01 \
        --dataset-version  population_a
"""

import argparse
import os

from azure.ai.ml import Input, MLClient, Output, command
from azure.ai.ml.dsl import pipeline
from azure.ai.ml.entities import BuildContext, Environment, JobResourceConfiguration
from azure.identity import DefaultAzureCredential

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FEATURES_DIR = os.path.join(REPO_ROOT, "ml", "features")
TRAINING_DIR = os.path.join(REPO_ROOT, "ml", "training")
DOCKER_DIR   = os.path.join(REPO_ROOT, "ml", "docker")


def build_environment() -> Environment:
    return Environment(
        name="bankretain-ml-env",
        description="BankRetain ML pipeline — Python 3.10 + LightGBM + Azure SDK + ODBC Driver 18",
        build=BuildContext(path=DOCKER_DIR),
        tags={"project": "bankretain"},
    )


def build_pipeline(args, env: Environment):
    # ── Step 1: Feature extraction (SQL → parquet) ────────────────────────────
    feature_step = command(
        name="feature_extraction",
        display_name="Feature Extraction — SQL → Parquet",
        code=FEATURES_DIR,
        command=(
            "python feature_pipeline.py --local "
            "--snapshot-date ${{inputs.snapshot_date}} "
            "--dataset-version ${{inputs.dataset_version}} "
            "--output-path ${{outputs.features_output}}"
        ),
        environment=env,
        inputs={
            "snapshot_date":   Input(type="string"),
            "dataset_version": Input(type="string"),
        },
        outputs={"features_output": Output(type="uri_folder")},
        environment_variables={
            "BANKRETAIN_SQL_SERVER": args.sql_server,
            "BANKRETAIN_SQL_DB":     args.sql_db,
            "AZURE_CLIENT_ID":       args.mi_client_id,
        },
        compute=args.compute,
        resources=JobResourceConfiguration(instance_type="Standard_DS2_v2", instance_count=1),
    )

    # ── Step 2: Training (parquet → model + metrics.json) ─────────────────────
    train_step = command(
        name="train",
        display_name="Train LightGBM Churn Model",
        code=TRAINING_DIR,
        command=(
            "python train.py "
            "--features-path ${{inputs.features_path}} "
            "--model-output ${{outputs.model_output}}"
        ),
        environment=env,
        environment_variables={
            "DATASET_VERSION": args.dataset_version,
            "AZURE_CLIENT_ID": args.mi_client_id,
        },
        inputs={"features_path": Input(type="uri_folder")},
        outputs={"model_output": Output(type="uri_folder")},
        compute=args.compute,
        resources=JobResourceConfiguration(instance_type="Standard_DS2_v2", instance_count=1),
    )

    # ── Step 3: Evaluate + register ───────────────────────────────────────────
    evaluate_step = command(
        name="evaluate",
        display_name="Evaluate and Register Model",
        code=TRAINING_DIR,
        command=(
            "python evaluate.py "
            "--model-path ${{inputs.model_path}} "
            f"--subscription-id {args.subscription_id} "
            f"--resource-group {args.resource_group} "
            f"--workspace-name {args.workspace_name} "
            "--dataset-version ${{inputs.dataset_version}}"
        ),
        environment=env,
        environment_variables={"AZURE_CLIENT_ID": args.mi_client_id},
        inputs={
            "model_path":      Input(type="uri_folder"),
            "dataset_version": Input(type="string"),
        },
        compute=args.compute,
        resources=JobResourceConfiguration(instance_type="Standard_DS2_v2", instance_count=1),
    )

    @pipeline(
        name="bankretain_training_pipeline",
        description="Feature extraction → LightGBM training → evaluation + registration",
        tags={
            "project":         "bankretain",
            "dataset_version": args.dataset_version,
            "snapshot_date":   args.snapshot_date,
        },
    )
    def training_pipeline(snapshot_date: str, dataset_version: str):
        feat = feature_step(
            snapshot_date=snapshot_date,
            dataset_version=dataset_version,
        )
        trained = train_step(features_path=feat.outputs.features_output)
        evaluate_step(
            model_path=trained.outputs.model_output,
            dataset_version=dataset_version,
        )

    return training_pipeline(
        snapshot_date=args.snapshot_date,
        dataset_version=args.dataset_version,
    )


def main(args) -> None:
    client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=args.subscription_id,
        resource_group_name=args.resource_group,
        workspace_name=args.workspace_name,
    )

    env = build_environment()
    pipeline_job = build_pipeline(args, env)
    pipeline_job.experiment_name = "bankretain-training"

    submitted = client.jobs.create_or_update(pipeline_job)
    print(f"Pipeline submitted: {submitted.name}")
    print(f"Studio URL:         {submitted.studio_url}")

    if args.wait:
        client.jobs.stream(submitted.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id",  dest="subscription_id", required=True)
    parser.add_argument("--resource-group",   dest="resource_group",  default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",   dest="workspace_name",  required=True)
    parser.add_argument("--sql-server",       dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",           dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--mi-client-id",     dest="mi_client_id",
                        default=os.environ.get("AZURE_CLIENT_ID", ""))
    parser.add_argument("--snapshot-date",    dest="snapshot_date",   default="2025-04-01")
    parser.add_argument("--dataset-version",  dest="dataset_version", default="population_a")
    parser.add_argument("--compute",          default="serverless",
                        help="AML compute name, or 'serverless'")
    parser.add_argument("--wait",             action="store_true",
                        help="Stream logs and wait for the pipeline to complete")
    args = parser.parse_args()
    main(args)
