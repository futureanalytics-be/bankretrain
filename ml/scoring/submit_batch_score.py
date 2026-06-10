"""
submit_batch_score.py — Submit BankRetain batch scoring as an AML command job

Submits batch_score.py to bankretain-cpu-cluster using the feature pipeline
managed identity for all auth (SQL, Blob, AML model registry).

One-off run (test / manual trigger):
    python ml/scoring/submit_batch_score.py \
        --subscription-id  $AZURE_SUBSCRIPTION_ID \
        --workspace-name   $AML_WORKSPACE_NAME \
        --storage-account  <storage-account-name> \
        --wait

Create / update the weekly Sunday schedule:
    python ml/scoring/submit_batch_score.py \
        --subscription-id  $AZURE_SUBSCRIPTION_ID \
        --workspace-name   $AML_WORKSPACE_NAME \
        --storage-account  <storage-account-name> \
        --schedule
"""

import argparse
import os

from azure.ai.ml import MLClient, command
from azure.ai.ml.entities import (
    BuildContext,
    CronTrigger,
    Environment,
    JobResourceConfiguration,
    JobSchedule,
)
from azure.identity import DefaultAzureCredential

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCORING_DIR  = os.path.join(REPO_ROOT, "ml", "scoring")
DOCKER_DIR   = os.path.join(REPO_ROOT, "ml", "docker")
SCHEDULE_NAME = "bankretain-weekly-batch-score"


def build_environment() -> Environment:
    return Environment(
        name="bankretain-ml-env",
        description="BankRetain ML pipeline — Python 3.10 + LightGBM + Azure SDK + ODBC Driver 18",
        build=BuildContext(path=DOCKER_DIR),
        tags={"project": "bankretain"},
    )


def build_job(args, env: Environment):
    # snapshot_date defaults to today() inside batch_score.py when omitted
    return command(
        name="batch_score",
        display_name="BankRetain Weekly Batch Scoring",
        description="Score all customers, write high-risk subset to Blob Storage",
        code=SCORING_DIR,
        command=(
            "python batch_score.py"
            f" --subscription-id {args.subscription_id}"
            f" --resource-group  {args.resource_group}"
            f" --workspace-name  {args.workspace_name}"
            f" --storage-account {args.storage_account}"
        ),
        environment=env,
        environment_variables={
            "AZURE_CLIENT_ID":       args.mi_client_id,
            "BANKRETAIN_SQL_SERVER": args.sql_server,
            "BANKRETAIN_SQL_DB":     args.sql_db,
        },
        compute=args.compute,
        resources=JobResourceConfiguration(instance_type="Standard_DS2_v2", instance_count=1),
        experiment_name="bankretain-batch-scoring",
    )


def main(args) -> None:
    client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=args.subscription_id,
        resource_group_name=args.resource_group,
        workspace_name=args.workspace_name,
    )

    env  = build_environment()
    job  = build_job(args, env)

    if args.schedule:
        schedule = JobSchedule(
            name=SCHEDULE_NAME,
            trigger=CronTrigger(expression="0 0 * * 0", start_time=None),  # Sunday 00:00 UTC
            create_job=job,
        )
        result = client.schedules.begin_create_or_update(schedule).result()
        print(f"Schedule created/updated: {result.name}")
        print(f"Cron: {result.trigger.expression} (UTC)  — runs every Sunday midnight")
    else:
        submitted = client.jobs.create_or_update(job)
        print(f"Job submitted: {submitted.name}")
        print(f"Studio URL:    {submitted.studio_url}")
        if args.wait:
            client.jobs.stream(submitted.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", dest="subscription_id", required=True)
    parser.add_argument("--resource-group",  dest="resource_group",  default="bankretain-ml-rg")
    parser.add_argument("--workspace-name",  dest="workspace_name",  required=True)
    parser.add_argument("--sql-server",      dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",          dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--mi-client-id",    dest="mi_client_id",
                        default=os.environ.get("MI_CLIENT_ID", ""))
    parser.add_argument("--storage-account", dest="storage_account", required=True)
    parser.add_argument("--compute",         default="bankretain-cpu-cluster")
    parser.add_argument("--schedule",        action="store_true",
                        help="Create/update the weekly AML schedule (Sunday 00:00 UTC)")
    parser.add_argument("--wait",            action="store_true",
                        help="Stream logs and wait for the job to complete")
    args = parser.parse_args()
    main(args)
