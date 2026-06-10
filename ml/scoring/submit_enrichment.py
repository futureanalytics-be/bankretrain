"""
submit_enrichment.py — Submit BankRetain enrichment pipeline as an AML command job

Submits enrichment.py to bankretain-cpu-cluster.  Reads high_risk_batch.csv from
Blob Storage, queries Azure SQL for customer context, and upserts to AI Search.

One-off run:
    python ml/scoring/submit_enrichment.py \
        --subscription-id  $AZURE_SUBSCRIPTION_ID \
        --workspace-name   $AML_WORKSPACE_NAME \
        --storage-account  <storage-account-name> \
        --keyvault-name    <keyvault-name> \
        --search-endpoint  https://<search-service>.search.windows.net \
        --wait

Create / update weekly schedule (Sunday 01:00 UTC, after batch scoring):
    python ml/scoring/submit_enrichment.py \
        ... (same args) \
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

REPO_ROOT     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCORING_DIR   = os.path.join(REPO_ROOT, "ml", "scoring")
DOCKER_DIR    = os.path.join(REPO_ROOT, "ml", "docker")
SCHEDULE_NAME = "bankretain-weekly-enrichment"


def build_environment() -> Environment:
    return Environment(
        name="bankretain-ml-env",
        description="BankRetain ML pipeline — Python 3.10 + LightGBM + Azure SDK + ODBC Driver 18",
        build=BuildContext(path=DOCKER_DIR),
        tags={"project": "bankretain"},
    )


def build_job(args, env: Environment):
    return command(
        display_name="BankRetain Weekly AI Search Enrichment",
        description="Enrich high-risk customer profiles in Azure AI Search from Blob + SQL",
        code=SCORING_DIR,
        command=(
            "python enrichment.py"
            f" --storage-account {args.storage_account}"
            f" --keyvault-name    {args.keyvault_name}"
            f" --search-endpoint  {args.search_endpoint}"
        ),
        environment=env,
        environment_variables={
            "AZURE_CLIENT_ID":       args.mi_client_id,
            "BANKRETAIN_SQL_SERVER": args.sql_server,
            "BANKRETAIN_SQL_DB":     args.sql_db,
        },
        compute=args.compute,
        resources=JobResourceConfiguration(instance_type="Standard_DS2_v2", instance_count=1),
        experiment_name="bankretain-enrichment",
    )


def main(args) -> None:
    client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=args.subscription_id,
        resource_group_name=args.resource_group,
        workspace_name=args.workspace_name,
    )

    env = build_environment()
    job = build_job(args, env)

    if args.schedule:
        schedule = JobSchedule(
            name=SCHEDULE_NAME,
            trigger=CronTrigger(expression="0 1 * * 0", start_time=None),  # Sunday 01:00 UTC
            create_job=job,
        )
        result = client.schedules.begin_create_or_update(schedule).result()
        print(f"Schedule created/updated: {result.name}")
        print(f"Cron: {result.trigger.expression} (UTC)  — runs every Sunday 01:00")
    else:
        submitted = client.jobs.create_or_update(job)
        print(f"Job submitted: {submitted.name}")
        print(f"Studio URL:    {submitted.studio_url}")
        if args.wait:
            client.jobs.stream(submitted.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription-id", dest="subscription_id", required=True)
    parser.add_argument("--resource-group",  dest="resource_group",  default="bankretain-ai-rg")
    parser.add_argument("--workspace-name",  dest="workspace_name",  required=True)
    parser.add_argument("--storage-account", dest="storage_account", required=True)
    parser.add_argument("--keyvault-name",   dest="keyvault_name",   required=True)
    parser.add_argument("--search-endpoint", dest="search_endpoint", required=True)
    parser.add_argument("--sql-server",      dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",          dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--mi-client-id",    dest="mi_client_id",
                        default=os.environ.get("MI_CLIENT_ID", ""))
    parser.add_argument("--compute",         default="bankretain-cpu-cluster")
    parser.add_argument("--schedule",        action="store_true",
                        help="Create/update the weekly AML schedule (Sunday 01:00 UTC)")
    parser.add_argument("--wait",            action="store_true",
                        help="Stream logs and wait for the job to complete")
    args = parser.parse_args()
    main(args)
