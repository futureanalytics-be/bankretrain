"""
generate.py — BankRetain synthetic data generation entry point

Orchestrates generation of Population A and Population B, computes
churn labels, and seeds Azure SQL. Run this script once to produce
all synthetic data before running the feature pipeline.

Usage:
    python generate.py --population a --seed-sql
    python generate.py --population b              # keep locally, seed later
    python generate.py --population both --seed-sql

Environment variables required (set via .env or Key Vault locally):
    BANKRETAIN_SQL_SERVER   e.g. bankretain-sql.database.windows.net
    BANKRETAIN_SQL_DB       e.g. bankretain-db
    BANKRETAIN_SQL_USER     e.g. bankretain-app
    BANKRETAIN_SQL_PASSWORD (dev only — in production, managed identity is used)
"""

import argparse
import logging
import os
from pathlib import Path

from population_a import generate_population_a
from population_b import generate_population_b
from label_generator import compute_churn_labels
from seed_sql import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def run(population: str, seed_sql: bool) -> None:
    populations = ["a", "b"] if population == "both" else [population]

    for pop in populations:
        log.info("=" * 60)
        log.info(f"Generating Population {pop.upper()}")
        log.info("=" * 60)

        if pop == "a":
            data = generate_population_a(n_customers=50_000, random_seed=42)
        else:
            data = generate_population_b(n_customers=50_000, random_seed=99)

        log.info("Computing churn labels from 60-day forward window...")
        data = compute_churn_labels(data)

        # Summarise label distribution
        churn_rate = data["customers"]["churned"].mean()
        log.info(f"Population {pop.upper()} churn rate: {churn_rate:.1%}")

        # Write parquet locally — feature pipeline reads from SQL,
        # but local copies are useful for debugging
        for table_name, df in data.items():
            out_path = OUTPUT_DIR / f"population_{pop}_{table_name}.parquet"
            df.to_parquet(out_path, index=False)
            log.info(f"  Wrote {len(df):,} rows → {out_path.name}")

        if seed_sql:
            log.info(f"Seeding Population {pop.upper()} into Azure SQL...")
            seed_database(data, population=pop)
            log.info(f"Population {pop.upper()} seeded successfully.")
        else:
            log.info(
                f"Population {pop.upper()} saved locally. "
                "Run with --seed-sql to load into Azure SQL."
            )

    log.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BankRetain synthetic data generator")
    parser.add_argument(
        "--population",
        choices=["a", "b", "both"],
        default="a",
        help="Which population to generate (default: a)",
    )
    parser.add_argument(
        "--seed-sql",
        action="store_true",
        help="Load generated data into Azure SQL after generation",
    )
    args = parser.parse_args()
    run(population=args.population, seed_sql=args.seed_sql)
