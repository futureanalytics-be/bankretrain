"""
search_tool.py — get_customer_profile tool implementation

Retrieves a customer's churn risk profile from the Azure AI Search
customer-profiles index.  Called by the orchestration pipeline to handle
Agent 1's function tool call.

Auth: API key retrieved from Key Vault using DefaultAzureCredential / MI.
The key is cached at module load time — one Key Vault round-trip per process.
"""

import json
import os
from functools import lru_cache
from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient

INDEX_NAME        = "customer-profiles"
SEARCH_KEY_SECRET = "search-admin-key"


def _credential(mi_client_id: Optional[str] = None):
    if mi_client_id:
        return ManagedIdentityCredential(client_id=mi_client_id)
    return DefaultAzureCredential()


@lru_cache(maxsize=1)
def _get_search_api_key(keyvault_name: str, mi_client_id: Optional[str]) -> str:
    cred = _credential(mi_client_id)
    kv_url = f"https://{keyvault_name}.vault.azure.net"
    client = SecretClient(vault_url=kv_url, credential=cred)
    return client.get_secret(SEARCH_KEY_SECRET).value


def build_search_client(search_endpoint: str, keyvault_name: str,
                        mi_client_id: Optional[str] = None) -> SearchClient:
    api_key = _get_search_api_key(keyvault_name, mi_client_id)
    return SearchClient(
        endpoint=search_endpoint,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(api_key),
    )


def get_customer_profile(customer_id: str, search_client: SearchClient) -> dict:
    """
    Retrieve the customer-profiles document for a given customer_id.
    Returns the profile dict, or {"error": "not_found"} if absent.
    """
    results = list(
        search_client.search(
            search_text="*",
            filter=f"customer_id eq '{customer_id}'",
            top=1,
        )
    )
    if not results:
        return {"error": "not_found", "customer_id": customer_id}

    doc = dict(results[0])
    # Remove internal Search metadata fields
    doc.pop("@search.score", None)
    doc.pop("@search.highlights", None)
    return doc


def handle_tool_call(tool_call_arguments: str, search_client: SearchClient) -> str:
    """
    Entry point called by the orchestration pipeline when Agent 1 issues a
    get_customer_profile function tool call.

    Args:
        tool_call_arguments: JSON string from the tool call, e.g. '{"customer_id": "C014590"}'
        search_client: pre-built SearchClient

    Returns:
        JSON string to submit as the tool result.
    """
    try:
        args = json.loads(tool_call_arguments)
        customer_id = args.get("customer_id", "")
        result = get_customer_profile(customer_id, search_client)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})
