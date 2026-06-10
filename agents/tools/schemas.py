"""
schemas.py — JSON schemas for inter-agent contracts

Agent 1 → Agent 2 → Agent 3 data contracts.
Used by the orchestration pipeline for validation at each step.
"""

from typing import Literal, Optional

# ── Agent 1 output ────────────────────────────────────────────────────────────

AGENT1_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["customer_id", "churn_score", "churn_reason", "confidence", "supporting_signals"],
    "properties": {
        "customer_id":        {"type": "string"},
        "churn_score":        {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "churn_reason":       {
            "type": "string",
            "enum": ["price_sensitivity", "service_dissatisfaction",
                     "product_lifecycle", "inactivity", "unknown"]
        },
        "confidence":         {"type": "string", "enum": ["high", "medium", "low"]},
        "supporting_signals": {"type": "array", "items": {"type": "string"}, "minItems": 0},
        "error":              {"type": "string"},
    },
    "additionalProperties": False,
}

# ── Agent 2 output ────────────────────────────────────────────────────────────

AGENT2_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["customer_id", "offer_id", "channel", "message_draft", "rationale"],
    "properties": {
        "customer_id":    {"type": "string"},
        "offer_id":       {"type": ["string", "null"]},
        "channel":        {"type": "string", "enum": ["email", "call"]},
        "message_draft":  {"type": "string", "minLength": 50},
        "rationale":      {"type": "string"},
    },
    "additionalProperties": False,
}

# ── Agent 3 output ────────────────────────────────────────────────────────────

AGENT3_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["status", "violated_rules", "message_draft", "review_notes"],
    "properties": {
        "status":         {"type": "string", "enum": ["pass", "fail"]},
        "violated_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule_id", "severity", "finding"],
                "properties": {
                    "rule_id":  {"type": "string"},
                    "severity": {"type": "string", "enum": ["hard_block", "flag_for_review"]},
                    "finding":  {"type": "string"},
                },
            },
        },
        "message_draft":  {"type": "string"},
        "review_notes":   {"type": "string"},
    },
    "additionalProperties": False,
}

# ── get_customer_profile tool definition (for Foundry agent tool registration) ─

GET_CUSTOMER_PROFILE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_customer_profile",
        "description": (
            "Retrieve the full churn risk profile for a given customer from the "
            "BankRetain Azure AI Search index. Returns numeric risk signals and "
            "narrative summaries (products, engagement, complaints, transactions)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The BankRetain customer identifier, e.g. 'C014590'.",
                }
            },
            "required": ["customer_id"],
        },
    },
}
