"""
agents/orchestration/pipeline.py — BankRetain sequential agent pipeline

Processes every customer in high_risk_batch.csv through three OpenAI Assistants
in sequence:

  Agent 1 (Churn Classifier)  → classify churn reason via AI Search profile
  Agent 2 (Offer Selection)   → select offer + draft outreach message
  Agent 3 (Compliance Review) → approve or reject the draft

Approved messages → approved_outreach table (Azure SQL)
Rejected messages → compliance_review_queue table (Azure SQL)

Prerequisites:
  - Azure AI Services account endpoint (openai/v1 format)
  - Products and compliance vector stores uploaded (run upload_products.py / upload_compliance.py)
  - AI Search index populated (run enrichment.py)

Usage:
    source sql.env && python agents/orchestration/pipeline.py \
        --base-url              https://bankretain-ai-svc-dev-jrkvoy.openai.azure.com/openai/v1 \
        --search-endpoint       https://bankretain-search-dev-jrkvoygp.search.windows.net \
        --keyvault-name         bankretain-kv-ai-jrkvoy \
        --storage-account       bankretainstdevmqi4i4pj \
        --products-store-id     <vector-store-id> \
        --compliance-store-id   <vector-store-id> \
        --batch-size            20
"""

import argparse
import io
import json
import os
import re
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import pyodbc
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient
from openai import OpenAI

REPO_ROOT   = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
PROMPTS_DIR = REPO_ROOT / "agents" / "prompts"

AGENT1_PROMPT = (PROMPTS_DIR / "agent1_system.md").read_text()
AGENT2_PROMPT = (PROMPTS_DIR / "agent2_system.md").read_text()
AGENT3_PROMPT = (PROMPTS_DIR / "agent3_system.md").read_text()

DEPLOYMENT_NAME = os.environ.get("AZURE_AI_DEPLOYMENT", "gpt-oss-120b")
BATCH_CSV_NAME  = "high_risk_batch.csv"
BATCH_CONTAINER = "bankretain-batch"


# ── Auth ──────────────────────────────────────────────────────────────────────

def _credential(mi_client_id: Optional[str] = None):
    if mi_client_id:
        return ManagedIdentityCredential(client_id=mi_client_id)
    return DefaultAzureCredential()


def _openai_client(cred) -> OpenAI:
    return OpenAI(
        base_url=os.environ["AZURE_AI_ENDPOINT"],
        api_key=os.environ["AZURE_AI_KEY"],
    )


# ── Blob ──────────────────────────────────────────────────────────────────────

def load_batch(storage_account: str, cred) -> pd.DataFrame:
    url    = f"https://{storage_account}.blob.core.windows.net"
    client = BlobServiceClient(account_url=url, credential=cred)
    blob   = client.get_blob_client(container=BATCH_CONTAINER, blob=BATCH_CSV_NAME)
    data   = blob.download_blob().readall()
    df     = pd.read_csv(io.BytesIO(data))
    print(f"Loaded {len(df):,} customers from {BATCH_CSV_NAME}")
    return df


# ── SQL ───────────────────────────────────────────────────────────────────────

def _sql_connect(sql_server: str, sql_db: str, cred) -> pyodbc.Connection:
    token        = cred.get_token("https://database.windows.net/.default")
    token_bytes  = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={sql_server};Database={sql_db};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    for attempt in range(1, 4):
        try:
            return pyodbc.connect(conn_str, attrs_before={1256: token_struct},
                                  timeout=60, autocommit=True)
        except pyodbc.Error as e:
            if "40613" in str(e) and attempt < 3:
                print(f"DB auto-pause, retrying in 20s (attempt {attempt}/3)...")
                time.sleep(20)
            else:
                raise


def ensure_tables(conn: pyodbc.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects
                       WHERE object_id = OBJECT_ID(N'dbo.approved_outreach') AND type='U')
        CREATE TABLE dbo.approved_outreach (
            id              INT IDENTITY(1,1) PRIMARY KEY,
            customer_id     NVARCHAR(10)  NOT NULL,
            batch_date      DATE          NOT NULL,
            offer_id        NVARCHAR(10),
            channel         NVARCHAR(10),
            churn_reason    NVARCHAR(50),
            confidence      NVARCHAR(10),
            message_draft   NVARCHAR(MAX),
            agent1_tokens   INT,
            agent2_tokens   INT,
            agent3_tokens   INT,
            approved_at     DATETIME2 DEFAULT GETUTCDATE()
        )
    """)
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.objects
                       WHERE object_id = OBJECT_ID(N'dbo.compliance_review_queue') AND type='U')
        CREATE TABLE dbo.compliance_review_queue (
            id              INT IDENTITY(1,1) PRIMARY KEY,
            customer_id     NVARCHAR(10)  NOT NULL,
            batch_date      DATE          NOT NULL,
            offer_id        NVARCHAR(10),
            channel         NVARCHAR(10),
            churn_reason    NVARCHAR(50),
            message_draft   NVARCHAR(MAX),
            violated_rules  NVARCHAR(MAX),
            review_notes    NVARCHAR(MAX),
            status          NVARCHAR(20)  DEFAULT 'pending',
            reviewed_by     NVARCHAR(100),
            reviewed_at     DATETIME2,
            created_at      DATETIME2 DEFAULT GETUTCDATE()
        )
    """)
    cursor.close()


def write_approved(conn: pyodbc.Connection, batch_date: str, row: dict) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dbo.approved_outreach
            (customer_id, batch_date, offer_id, channel, churn_reason, confidence,
             message_draft, agent1_tokens, agent2_tokens, agent3_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        row["customer_id"], batch_date,
        row.get("offer_id"), row.get("channel"), row.get("churn_reason"),
        row.get("confidence"), _sanitize(row.get("message_draft")),
        row.get("agent1_tokens", 0), row.get("agent2_tokens", 0), row.get("agent3_tokens", 0),
    )
    cursor.close()


def write_rejected(conn: pyodbc.Connection, batch_date: str, row: dict) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO dbo.compliance_review_queue
            (customer_id, batch_date, offer_id, channel, churn_reason,
             message_draft, violated_rules, review_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        row["customer_id"], batch_date,
        row.get("offer_id"), row.get("channel"), row.get("churn_reason"),
        _sanitize(row.get("message_draft")),
        json.dumps(row.get("violated_rules", [])),
        _sanitize(row.get("review_notes", "")),
    )
    cursor.close()


# ── Text helpers ─────────────────────────────────────────────────────────────

_VALID_CHURN_REASONS = frozenset({
    "price_sensitivity", "service_dissatisfaction",
    "product_lifecycle", "inactivity", "unknown",
})

# Keyword fallback order matters — more specific reasons first.
_CHURN_REASON_KEYWORDS = [
    ("service_dissatisfaction", ["complaint", "incident", "nps"]),
    ("product_lifecycle",       ["lifecycle", "rate_reset", "rate reset", "mortgage"]),
    ("price_sensitivity",       ["price", "competitor", "fee", "salary"]),
    ("inactivity",              ["inactiv", "dormant", "dormancy", "disengag", "engagement"]),
]


def _normalize_churn_reason(raw) -> str:
    if not raw:
        return "unknown"
    if isinstance(raw, list):
        raw = raw[0] if raw else None
        if not raw:
            return "unknown"
    clean = str(raw).strip()
    if clean.lower() in _VALID_CHURN_REASONS:
        return clean.lower()
    lower = clean.lower()
    for reason, keywords in _CHURN_REASON_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return reason
    return "unknown"


_UNICODE_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u00a0": " ",
    # Belt-and-suspenders: control-char low bytes in case of pre-fix DB data
    "\x18": "'", "\x19": "'",
    "\x1c": '"', "\x1d": '"',
    "\x13": "-", "\x14": "-", "\x15": "",
})


def _sanitize(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return text.translate(_UNICODE_MAP)


# ── JSON extraction ───────────────────────────────────────────────────────────

def extract_json(text: str) -> Optional[dict]:
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


# ── Responses API runner ──────────────────────────────────────────────────────

GET_CUSTOMER_PROFILE_TOOL = {
    "type": "function",
    "name": "get_customer_profile",
    "description": "Retrieve the churn risk profile for a customer from Azure AI Search.",
    "parameters": {
        "type": "object",
        "properties": {"customer_id": {"type": "string"}},
        "required": ["customer_id"],
    },
}


def _create_response_with_retry(oai: OpenAI, **kwargs):
    for attempt in range(5):
        try:
            return oai.responses.create(**kwargs)
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                wait = 20 * (attempt + 1)
                print(f" [rate limit, waiting {wait}s]", end="", flush=True)
                time.sleep(wait)
            else:
                raise


def run_response(oai: OpenAI, instructions: str, user_input: str,
                 tools: list = None, tool_handler=None) -> tuple[Optional[dict], int]:
    kwargs = {
        "model": DEPLOYMENT_NAME,
        "instructions": instructions,
        "input": user_input + " Respond with JSON.",
        "text": {"format": {"type": "json_object"}},
    }
    if tools:
        kwargs["tools"] = tools

    response = _create_response_with_retry(oai, **kwargs)

    # Handle a single round of function tool calls if needed
    if tool_handler and response.output:
        fn_calls = [item for item in response.output if item.type == "function_call"]
        if fn_calls:
            tool_results = [
                {
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": tool_handler(fc.name, fc.arguments),
                }
                for fc in fn_calls
            ]
            response = _create_response_with_retry(
                oai,
                model=DEPLOYMENT_NAME,
                previous_response_id=response.id,
                input=tool_results,
            )

    tokens = 0
    if response.usage:
        tokens = (response.usage.input_tokens or 0) + (response.usage.output_tokens or 0)

    return extract_json(response.output_text), tokens


# ── Main pipeline ─────────────────────────────────────────────────────────────

def process_customer(customer_id: str, oai: OpenAI, search_client,
                     products_store_id: str, compliance_store_id: str) -> dict:
    from agents.tools.search_tool import handle_tool_call

    result = {"customer_id": customer_id,
              "agent1_tokens": 0, "agent2_tokens": 0, "agent3_tokens": 0}

    def tool_handler(fn_name: str, fn_args: str) -> str:
        if fn_name == "get_customer_profile":
            return handle_tool_call(fn_args, search_client)
        return json.dumps({"error": f"unknown tool: {fn_name}"})

    # Agent 1 — classify churn reason
    a1_output, a1_tokens = run_response(
        oai, AGENT1_PROMPT,
        f"Classify the churn reason for customer_id: {customer_id}",
        tools=[GET_CUSTOMER_PROFILE_TOOL],
        tool_handler=tool_handler,
    )
    result["agent1_tokens"] = a1_tokens
    if not a1_output or "error" in a1_output:
        result["error"] = f"agent1 failed: {a1_output}"
        return result
    result["churn_reason"] = _normalize_churn_reason(a1_output.get("churn_reason"))
    result["confidence"]   = (
        a1_output.get("confidence")
        or a1_output.get("confidence_level")
        or a1_output.get("confidence_score")
        or "medium"
    )

    # Agent 2 — offer selection + draft
    a2_output, a2_tokens = run_response(
        oai, AGENT2_PROMPT,
        json.dumps(a1_output),
        tools=[{"type": "file_search", "vector_store_ids": [products_store_id]}],
    )
    result["agent2_tokens"] = a2_tokens
    if not a2_output:
        result["error"] = "agent2 failed"
        return result
    result["offer_id"]      = a2_output.get("offer_id")
    result["channel"]       = a2_output.get("channel")
    result["message_draft"] = a2_output.get("message_draft", "")

    # Agent 3 — compliance review
    a3_output, a3_tokens = run_response(
        oai, AGENT3_PROMPT,
        json.dumps({
            "customer_context": a1_output,
            "offer_id":         a2_output.get("offer_id"),
            "channel":          a2_output.get("channel"),
            "message_draft":    a2_output.get("message_draft"),
        }),
        tools=[{"type": "file_search", "vector_store_ids": [compliance_store_id]}],
    )
    result["agent3_tokens"] = a3_tokens
    if not a3_output:
        result["error"] = "agent3 failed"
        return result
    result["status"]         = a3_output.get("status", "fail")
    result["violated_rules"] = a3_output.get("violated_rules", [])
    result["review_notes"]   = a3_output.get("review_notes", "")
    if a3_output.get("message_draft"):
        result["message_draft"] = a3_output["message_draft"]

    return result


def main(args) -> None:
    cred = _credential(os.environ.get("AZURE_CLIENT_ID"))
    oai  = _openai_client(cred)

    from agents.tools.search_tool import build_search_client
    search_client = build_search_client(
        args.search_endpoint, args.keyvault_name,
        os.environ.get("AZURE_CLIENT_ID"),
    )

    batch_df   = load_batch(args.storage_account, cred)
    batch_date = datetime.now(timezone.utc).date().isoformat()
    if args.batch_size:
        batch_df = batch_df.head(args.batch_size)
        print(f"Processing {len(batch_df)} customers (--batch-size limit)")

    conn = _sql_connect(
        os.environ.get("BANKRETAIN_SQL_SERVER", args.sql_server),
        os.environ.get("BANKRETAIN_SQL_DB", args.sql_db),
        cred,
    )
    ensure_tables(conn)

    approved = rejected = errors = 0
    for i, customer_id in enumerate(batch_df["customer_id"].tolist(), 1):
        print(f"[{i}/{len(batch_df)}] {customer_id} ...", end=" ", flush=True)
        try:
            result = process_customer(
                customer_id, oai, search_client,
                args.products_store_id, args.compliance_store_id,
            )
            if "error" in result:
                print(f"ERROR — {result['error']}")
                errors += 1
            elif result.get("status") == "pass":
                write_approved(conn, batch_date, result)
                approved += 1
                print(f"PASS ({result.get('churn_reason')}/{result.get('channel')})")
            else:
                write_rejected(conn, batch_date, result)
                rejected += 1
                rules = [r["rule_id"] for r in result.get("violated_rules", [])]
                print(f"FAIL ({', '.join(rules) or 'no rules listed'})")
        except Exception as e:
            print(f"EXCEPTION — {e}")
            errors += 1
        time.sleep(5)

    conn.close()
    print(f"\n{'─'*50}")
    print(f"Batch complete: {approved} approved, {rejected} queued for review, {errors} errors")
    print(f"Batch date: {batch_date}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--search-endpoint",     dest="search_endpoint",      required=True)
    parser.add_argument("--keyvault-name",       dest="keyvault_name",        required=True)
    parser.add_argument("--storage-account",     dest="storage_account",      required=True)
    parser.add_argument("--products-store-id",   dest="products_store_id",    required=True)
    parser.add_argument("--compliance-store-id", dest="compliance_store_id",  required=True)
    parser.add_argument("--sql-server",  dest="sql_server",
                        default=os.environ.get("BANKRETAIN_SQL_SERVER", ""))
    parser.add_argument("--sql-db",      dest="sql_db",
                        default=os.environ.get("BANKRETAIN_SQL_DB", "bankretaindb"))
    parser.add_argument("--batch-size",  dest="batch_size", type=int, default=0)
    args = parser.parse_args()
    main(args)
