"""
upload_compliance.py — Upload compliance rules to Azure OpenAI file search vector store

Reads data/compliance_rules/rules.md and uploads it to the AI Services
account as a vector store for Agent 3 (Compliance Review).

Usage:
    python agents/vector_stores/upload_compliance.py \
        --base-url https://bankretain-ai-svc-dev-jrkvoy.openai.azure.com/openai/v1
"""

import argparse
import os
import time
from pathlib import Path

from openai import OpenAI

REPO_ROOT        = Path(__file__).parent.parent.parent
COMPLIANCE_FILE  = REPO_ROOT / "data" / "compliance_rules" / "rules.md"
STORE_NAME       = "bankretain-compliance-rules"


def main(args) -> None:
    oai = OpenAI(
        base_url=os.environ["AZURE_AI_ENDPOINT"],
        api_key=os.environ["AZURE_AI_KEY"],
    )

    print(f"Uploading {COMPLIANCE_FILE} ...")
    with open(COMPLIANCE_FILE, "rb") as f:
        uploaded = oai.files.create(file=(COMPLIANCE_FILE.name, f, "text/plain"), purpose="assistants")
    print(f"File uploaded: id={uploaded.id}")

    print(f"Creating vector store '{STORE_NAME}' ...")
    vs = oai.vector_stores.create(name=STORE_NAME)
    oai.vector_stores.files.create(vector_store_id=vs.id, file_id=uploaded.id)

    for _ in range(30):
        status = oai.vector_stores.retrieve(vs.id).status
        if status == "completed":
            break
        time.sleep(2)

    print(f"Vector store ready: id={vs.id}  status={status}")
    print(f"\nUse this ID for pipeline.py --compliance-store-id:")
    print(f"  {vs.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    main(args)
